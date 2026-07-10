#!/usr/bin/env python3
"""
backfill_days.py — Generate one edition per day from the deep-scrape
article pool (output/articles_deep.json).

For each day with ≥ N articles (default 5), produces a JSON file at
web/data/archive/YYYY-MM-DD.json and updates the index. The current
latest.json is also rewritten to match the most recent day's data,
so the live site shows today's content first and the archive drawer
grows one entry per day.

This is real content: every article is a real, scraped article from
the configured RSS sources, not synthesised or fabricated.
"""
from __future__ import annotations
import argparse
import datetime
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

log = logging.getLogger("backfill-days")

DEFAULT_BASE = Path(__file__).parent.parent
MIN_ARTICLES_PER_DAY = 3  # don't generate an edition for a day with 0-2 articles


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--min-articles", type=int, default=MIN_ARTICLES_PER_DAY)
    parser.add_argument("--max-articles", type=int, default=80,
                        help="Cap articles per day edition (top by score)")
    args = parser.parse_args()

    base = args.base
    deep_path = base / "output" / "articles_deep.json"
    archive_dir = base / "web" / "data" / "archive"
    latest_path = base / "web" / "data" / "latest.json"
    index_path = archive_dir / "index.json"

    if not deep_path.exists():
        log.error(f"{deep_path} not found — run scripts/deep_scrape.py first")
        return 1

    with deep_path.open() as f:
        data = json.load(f)

    articles = data.get("articles", [])
    if not articles:
        log.error("No articles in deep scrape output")
        return 1

    # Group by date
    by_date: dict[str, list[dict]] = defaultdict(list)
    for a in articles:
        pub = a.get("published", "")
        if not pub:
            continue
        try:
            dt = datetime.datetime.fromisoformat(pub.replace("Z", "+00:00"))
            day_key = dt.date().isoformat()
            by_date[day_key].append(a)
        except (ValueError, AttributeError):
            continue

    log.info(f"Found articles in {len(by_date)} distinct days")
    log.info(f"Date range: {min(by_date)} → {max(by_date)}")

    archive_dir.mkdir(parents=True, exist_ok=True)

    editions = []
    for day_key in sorted(by_date.keys()):
        day_articles = by_date[day_key]
        if len(day_articles) < args.min_articles:
            log.info(f"  {day_key}: {len(day_articles)} articles — skip (<{args.min_articles})")
            continue

        # Sort by score (or weight as fallback), cap to max_articles
        day_articles.sort(key=lambda a: a.get("score", a.get("weight", 0)), reverse=True)
        day_articles = day_articles[:args.max_articles]

        edition = build_edition_for_day(day_key, day_articles)
        edition_path = archive_dir / f"{day_key}.json"
        with edition_path.open("w") as f:
            json.dump(edition, f, indent=2, ensure_ascii=False)
        log.info(f"  {day_key}: wrote {edition_path} ({len(day_articles)} articles)")
        editions.append({
            "day": day_key,
            "path": edition_path,
            "article_count": len(day_articles),
        })

    # Today's edition is the latest — overwrite web/data/latest.json
    if editions:
        today_key = max(e["day"] for e in editions)
        today_path = archive_dir / f"{today_key}.json"
        with today_path.open() as f:
            today_data = json.load(f)
        # Strip archive-specific fields, keep the brief/raw_articles shape
        latest_payload = {
            "generated_at": today_data["generated_at"],
            "brief": today_data["brief"],
            "raw_articles": today_data["raw_articles"],
        }
        with latest_path.open("w") as f:
            json.dump(latest_payload, f, indent=2, ensure_ascii=False)
        log.info(f"Updated latest.json from {today_key}")

    # Build the index — all days, newest first
    index = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "edition_count": len(editions),
        "editions": [
            {
                "id": e["day"],
                "date": e["day"],
                "article_count": e["article_count"],
                "headline": json.load(open(e["path"]))["brief"]["headline"],
                "path": f"archive/{e['day']}.json",
            }
            for e in sorted(editions, key=lambda x: x["day"], reverse=True)
        ],
    }
    with index_path.open("w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    log.info(f"Wrote {index_path} ({len(editions)} editions)")

    return 0


def build_edition_for_day(day_key: str, articles: list[dict]) -> dict:
    """Build a daily-edition JSON for one day.

    No LLM call — honest content from the actual articles, with a short
    headline synthesised from the day's top themes.
    """
    # Top themes = most common keywords (filtered to length > 3)
    kw_counter: Counter = Counter()
    for a in articles:
        for kw in a.get("keywords", [])[:3]:
            if len(kw) > 3:
                kw_counter[kw] += 1
    top_kws = [w for w, _ in kw_counter.most_common(3)]
    theme = " · ".join(top_kws[:2]) if top_kws else "Branchen-Update"

    # Headline: combine date + theme
    dt = datetime.datetime.fromisoformat(day_key)
    date_str = dt.strftime("%d.%m.%Y")
    headline = f"{date_str}: {theme}"
    subheadline = (
        f"Tageszusammenfassung mit {len(articles)} Artikeln aus "
        f"{len({a['source'] for a in articles})} Quellen."
    )

    # Executive summary: short, factual
    exec_summary = (
        f"<p>Am {date_str} wurden {len(articles)} relevante Branchen-Meldungen aus "
        f"{len({a['source'] for a in articles})} Quellen erfasst. "
        f"Die thematischen Schwerpunkte lagen bei {theme}.</p>"
        f"<p>Die wichtigsten Meldungen des Tages sind nachfolgend kuratiert — "
        f"sortiert nach Recency und Quellen-Autorität. "
        f"Vollständige Artikel-Liste unten.</p>"
    )

    # Trends: top 6 articles as trend-style items
    trends = []
    for a in articles[:6]:
        trends.append({
            "title": a["title"][:120],
            "what": (a.get("summary") or "")[:300],
            "why": f"Gemeldet von {a['source']} am {a['published'][:10]}.",
            "signal": "mittel",
        })

    # Top articles: top 10 with full details
    top_articles = [
        {
            "title": a["title"],
            "url": a["url"],
            "source": a["source"],
            "date": a["published"][:10],
            "why": (a.get("summary") or "")[:200],
            "tags": (a.get("keywords") or [])[:5],
        }
        for a in articles[:10]
    ]

    # Slim raw articles (capped at 30)
    raw_articles = [
        {
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "source": a.get("source", ""),
            "lang": a.get("lang", "de"),
            "published": a.get("published", ""),
            "summary": (a.get("summary") or "")[:600],
            "keywords": (a.get("keywords") or [])[:6],
        }
        for a in articles[:30]
    ]

    # The day's "evening" timestamp (18:00 UTC) as the issue time
    issue_dt = datetime.datetime.fromisoformat(f"{day_key}T18:00:00+00:00")

    return {
        "generated_at": issue_dt.isoformat(),
        "edition_id": day_key,
        "date": day_key,
        "brief": {
            "headline": headline,
            "subheadline": subheadline,
            "executive_summary": exec_summary,
            "trends": trends,
            "opportunities": [],
            "top_articles": top_articles,
            "action_items": [],
        },
        "raw_articles": raw_articles,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )
    raise SystemExit(main())
