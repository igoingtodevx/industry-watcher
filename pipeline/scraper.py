"""
scraper.py — Pulls articles from RSS sources, normalizes, dedupes, scores.
"""
from __future__ import annotations
import socket
# Set global socket timeout BEFORE importing feedparser (uses urllib internally)
socket.setdefaulttimeout(8)

import feedparser
import hashlib
import re
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import yaml

# feedparser reads this env for the user-agent
import os
os.environ.setdefault("HTTP_USER_AGENT", "Mozilla/5.0 (compatible; AIIndustryWatcher/1.0)")

log = logging.getLogger("scraper")

STOPWORDS = {
    "der", "die", "das", "und", "mit", "von", "für", "aus", "auf", "ein",
    "eine", "einer", "eines", "ist", "sind", "war", "hat", "have", "the",
    "and", "for", "with", "from", "this", "that", "was", "were", "bei",
    "nach", "wie", "was", "wer", "wo", "wann", "über", "einem", "einen",
}


@dataclass
class Article:
    id: str
    title: str
    url: str
    source: str
    source_category: str
    lang: str
    weight: int
    published: str          # ISO8601
    published_dt: datetime
    summary: str
    content: str            # full text if available
    score: float = 0.0
    keywords: list[str] = field(default_factory=list)
    fetched_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("published_dt", None)
        return d


def load_sources(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def _strip_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _extract_keywords(title: str, content: str, n: int = 6) -> list[str]:
    text = f"{title} {content}".lower()
    text = re.sub(r"[^a-z0-9äöüß\s\-]", " ", text)
    tokens = [t for t in text.split() if len(t) > 3 and t not in STOPWORDS]
    from collections import Counter
    c = Counter(tokens)
    return [w for w, _ in c.most_common(n)]


def _parse_date(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        v = entry.get(key)
        if v:
            try:
                return datetime(*v[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    for key in ("published", "updated"):
        v = entry.get(key)
        if v:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(v)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                continue
    return None


def _id_from(url: str, title: str) -> str:
    h = hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:12]
    return h


def _matches_keywords(text: str, kws: list[str]) -> bool:
    if not kws:
        return True
    t = text.lower()
    return any(kw.lower() in t for kw in kws)


def fetch_one(source: dict, lookback: timedelta) -> list[Article]:
    """Fetch one RSS source, return list of Articles (may be empty)."""
    log.info(f"Fetching {source['name']} ({source['url']})")
    try:
        parsed = feedparser.parse(source["url"])
    except Exception as e:
        log.warning(f"  fetch exception: {e}")
        return []
    if not parsed.entries:
        log.warning(f"  no entries (bozo={parsed.get('bozo_exception')})")
        return []

    now = datetime.now(timezone.utc)
    cutoff = now - lookback
    arts: list[Article] = []
    kws = source.get("keywords", [])
    skipped_filter = 0

    for entry in parsed.entries[: source.get("max_per_source", 30)]:
        published_dt = _parse_date(entry)
        if not published_dt:
            continue
        if published_dt < cutoff:
            continue

        title = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not title or not url:
            continue

        # Keyword filter (for big general feeds)
        if kws and not _matches_keywords(f"{title}", kws):
            skipped_filter += 1
            continue

        # summary candidates
        content_field = entry.get("content", "")
        if isinstance(content_field, list) and content_field:
            content_field = content_field[0].get("value", "")
        summary = _strip_html(
            entry.get("summary")
            or entry.get("description")
            or content_field
            or ""
        )
        summary = (summary or "")[:600]

        article = Article(
            id=_id_from(url, title),
            title=title,
            url=url,
            source=source["name"],
            source_category=source.get("category", ""),
            lang=source.get("lang", "de"),
            weight=int(source.get("weight", 3)),
            published=published_dt.isoformat(),
            published_dt=published_dt,
            summary=summary,
            content=summary,
            fetched_at=now.isoformat(),
        )
        article.keywords = _extract_keywords(title, summary)
        arts.append(article)

    if kws:
        log.info(f"  kept={len(arts)}, filter-skipped={skipped_filter}")
    return arts


def score(arts: list[Article], cfg: dict) -> list[Article]:
    """Score by recency * weight. Then sort desc, cap to max."""
    now = datetime.now(timezone.utc)
    half_life = float(cfg.get("recency_half_life_hours", 48))
    max_total = int(cfg.get("max_articles_total", 60))
    min_total = int(cfg.get("min_articles_total", 0))

    for a in arts:
        age_h = (now - a.published_dt).total_seconds() / 3600.0
        # Exponential decay
        recency = 0.5 ** (age_h / max(half_life, 1))
        # Bonus for keyword density
        kw_bonus = min(0.2, 0.03 * len(a.keywords))
        a.score = round((a.weight * recency) + kw_bonus, 4)

    arts.sort(key=lambda a: a.score, reverse=True)
    return arts[:max_total] if len(arts) > max_total else arts


def dedupe(arts: list[Article]) -> list[Article]:
    """Dedupe by URL exact + title-similarity (first 8 words)."""
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    out: list[Article] = []
    for a in arts:
        if a.url in seen_urls:
            continue
        # title key = first 8 lowercase words
        key = " ".join(a.title.lower().split()[:8])
        if key in seen_titles:
            continue
        seen_urls.add(a.url)
        seen_titles.add(key)
        out.append(a)
    return out


def run(sources_path: Path, out_path: Path) -> dict:
    cfg = load_sources(sources_path)
    sources = cfg["sources"]
    scoring = cfg.get("scoring", {})
    lookback = timedelta(hours=int(scoring.get("lookback_hours", 168)))
    max_per_source = int(scoring.get("max_articles_per_source", 15))

    all_arts: list[Article] = []
    for s in sources:
        s["max_per_source"] = max_per_source
        is_optional = bool(s.get("optional", False))
        try:
            arts = fetch_one(s, lookback)
            if not arts and is_optional:
                log.debug(f"  skipping optional empty: {s['name']}")
                continue
            all_arts.extend(arts)
        except Exception as e:
            if is_optional:
                log.debug(f"  optional {s['name']} failed: {e}")
                continue
            log.error(f"  failed {s['name']}: {e}")

    log.info(f"Raw articles fetched: {len(all_arts)}")
    all_arts = dedupe(all_arts)
    log.info(f"After dedupe: {len(all_arts)}")
    all_arts = score(all_arts, scoring)
    log.info(f"After scoring/cap: {len(all_arts)}")

    # Write JSON
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vertical": "German Mittelstand Digital & KI-Automation",
        "source_count": len(sources),
        "article_count": len(all_arts),
        "articles": [a.to_dict() for a in all_arts],
    }
    with out_path.open("w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log.info(f"Wrote {out_path}")
    return payload


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    base = Path(__file__).parent.parent
    run(base / "sources.yaml", base / "output" / "articles.json")
