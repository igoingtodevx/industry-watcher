#!/usr/bin/env python3
"""
deep_scrape.py — Multi-page RSS scraper for historical backfill.

The standard scraper.py uses a single feed URL with a lookback window.
This script tries multiple pagination strategies per source and merges
all unique articles within a configurable historical window.

Used only for backfill — the daily brief uses scraper.py (single page,
recent articles only).
"""
from __future__ import annotations
import json
import logging
import os
import socket
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Set timeout before feedparser import
socket.setdefaulttimeout(10)

import feedparser
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.scraper import Article, _parse_date, _id_from, _strip_html, _extract_keywords  # noqa

log = logging.getLogger("deep-scrape")

# Pagination strategies to try per source (URL template with {n})
# When {n} is 1, that's the default URL (no pagination param)
PAGINATION_TEMPLATES = [
    "{base}",                           # no pagination
    "{base}?paged={n}",                 # WordPress default
    "{base}?page={n}",                  # generic
    "{base}?seite={n}",                 # Heise family
    "{base}?p={n}",                     # alt generic
    "{base}/page/{n}/",                 # path-based
    "{base}/feed/?paged={n}",           # explicit path
    "{base}&page={n}",                  # query append (assumes base has ?)
]


def is_paginated_url(base: str) -> bool:
    return any(p in base for p in ["paged", "seite", "page=", "p="])


def try_paginate(base: str, n: int) -> str:
    """Build a paginated URL for a given base and page number.

    For a base URL that already has pagination params, increment them.
    Otherwise, try ?paged=N first.
    """
    if "paged=" in base:
        return base.replace("paged=", f"paged=").split("paged=")[0] + f"paged={n}"
    if "seite=" in base:
        return base.split("seite=")[0] + f"seite={n}"
    if "page=" in base:
        return base.split("page=")[0] + f"page={n}"
    if "p=" in base and "?" in base:
        return base.split("p=")[0] + f"p={n}"
    if "?" in base:
        return f"{base}&paged={n}"
    return f"{base}?paged={n}"


def deep_fetch(source: dict, lookback: timedelta, max_pages: int = 10) -> list[Article]:
    """Fetch from one source, paginating until we see a page with no new
    articles older than what we already have, or we hit max_pages.
    """
    base = source["url"]
    name = source["name"]
    arts: list[Article] = []
    seen_ids: set[str] = set()
    newest_dt_seen: datetime | None = None
    cutoff = datetime.now(timezone.utc) - lookback

    for page in range(1, max_pages + 1):
        url = try_paginate(base, page) if page > 1 else base
        log.info(f"  {name} page {page}: {url}")
        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            log.warning(f"    fetch exception: {e}")
            break
        if not parsed.entries:
            log.info(f"    page empty — stopping")
            break

        page_arts: list[Article] = []
        page_newest: datetime | None = None
        page_oldest: datetime | None = None

        for entry in parsed.entries[: source.get("max_per_source", 30)]:
            published_dt = _parse_date(entry)
            if not published_dt:
                continue
            if published_dt < cutoff:
                continue
            if page_newest is None or published_dt > page_newest:
                page_newest = published_dt
            if page_oldest is None or published_dt < page_oldest:
                page_oldest = published_dt

            title = (entry.get("title") or "").strip()
            url_e = (entry.get("link") or "").strip()
            if not title or not url_e:
                continue

            content_field = entry.get("content", "")
            if isinstance(content_field, list) and content_field:
                content_field = content_field[0].get("value", "")
            summary = _strip_html(
                entry.get("summary")
                or entry.get("description")
                or content_field
                or ""
            )[:600]

            aid = _id_from(url_e, title)
            if aid in seen_ids:
                continue
            seen_ids.add(aid)

            article = Article(
                id=aid,
                title=title,
                url=url_e,
                source=name,
                source_category=source.get("category", ""),
                lang=source.get("lang", "de"),
                weight=int(source.get("weight", 3)),
                published=published_dt.isoformat(),
                published_dt=published_dt,
                summary=summary,
                content=summary,
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )
            article.keywords = _extract_keywords(title, summary)
            page_arts.append(article)

        if not page_arts:
            log.info(f"    page {page} yielded no new articles — stopping")
            break

        # If this page's oldest article is >= the newest we've seen,
        # we're seeing the same window over and over (no real pagination).
        if page > 1 and page_oldest and newest_dt_seen and page_oldest >= newest_dt_seen:
            log.info(f"    page {page} no newer than page 1 — stopping (no real pagination)")
            break

        arts.extend(page_arts)
        if page_newest and (newest_dt_seen is None or page_newest > newest_dt_seen):
            newest_dt_seen = page_newest

        # Safety: if page has < 5 entries, we're probably at the end
        if len(parsed.entries) < 5:
            log.info(f"    page {page} has only {len(parsed.entries)} entries — at end")
            break

    return arts


def main():
    base = Path(__file__).parent.parent
    sources_path = base / "sources.yaml"
    out_path = base / "output" / "articles_deep.json"

    with sources_path.open() as f:
        cfg = yaml.safe_load(f)
    sources = cfg["sources"]
    lookback = timedelta(days=int(os.environ.get("DEEP_LOOKBACK_DAYS", "30")))
    max_pages = int(os.environ.get("DEEP_MAX_PAGES", "10"))

    log.info(f"Deep scrape: lookback={lookback.days} days, max_pages={max_pages}")

    all_arts: list[Article] = []
    for s in sources:
        if s.get("type") != "rss":
            continue
        is_optional = bool(s.get("optional", False))
        try:
            arts = deep_fetch(s, lookback, max_pages)
            log.info(f"  {s['name']}: {len(arts)} articles from {1 if not is_paginated_url(s['url']) else 'multi'} page(s)")
            all_arts.extend(arts)
        except Exception as e:
            log.error(f"  failed {s['name']}: {e}")

    # Dedupe by URL
    seen = set()
    deduped = []
    for a in all_arts:
        if a.url in seen:
            continue
        seen.add(a.url)
        deduped.append(a)
    log.info(f"After URL-dedupe: {len(deduped)}")

    # Date distribution
    from collections import Counter
    days = Counter()
    for a in deduped:
        d = a.published_dt.date().isoformat()
        days[d] += 1
    log.info("Per-day distribution:")
    for d in sorted(days.keys()):
        log.info(f"  {d}: {days[d]}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback.days,
        "article_count": len(deduped),
        "articles": [
            {**asdict(a), "published_dt": a.published_dt.isoformat()}
            for a in deduped
        ],
    }
    # Convert datetime back to string for JSON
    import dataclasses
    for a in payload["articles"]:
        del a["published_dt"]  # already in 'published' as string

    with out_path.open("w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log.info(f"Wrote {out_path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )
    main()
