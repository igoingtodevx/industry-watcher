"""
storage.py — Aggregates latest run into the web/data/latest.json shape
that the static frontend can fetch directly.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("storage")


def assemble_latest(articles_path: Path, brief_path: Path, out_path: Path) -> dict:
    """Combine articles + brief into the single file the frontend loads."""
    with articles_path.open() as f:
        articles_data = json.load(f)
    with brief_path.open() as f:
        brief = json.load(f)

    # Take top 30 articles for the frontend (don't ship 150 to the browser)
    top_articles = articles_data.get("articles", [])[:30]
    # Strip full content — keep summary only, no giant blobs
    top_articles_slim = []
    for a in top_articles:
        top_articles_slim.append({
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "source": a.get("source", ""),
            "lang": a.get("lang", "de"),
            "published": a.get("published", ""),
            "summary": (a.get("summary", "") or "")[:600],
            "keywords": (a.get("keywords", []) or [])[:6],
        })

    payload = {
        "generated_at": brief.get("_meta", {}).get("generated_at")
            or datetime.now(timezone.utc).isoformat(),
        "vertical": articles_data.get("vertical", ""),
        "model": brief.get("_meta", {}).get("model", "?"),
        "tokens_used": brief.get("_meta", {}).get("tokens_used"),
        "input_articles": brief.get("_meta", {}).get("input_articles"),
        "input_sources": brief.get("_meta", {}).get("input_sources"),
        "brief": {
            "headline": brief.get("headline", ""),
            "subheadline": brief.get("subheadline", ""),
            "executive_summary": brief.get("executive_summary", ""),
            "trends": brief.get("trends", []),
            "opportunities": brief.get("opportunities", []),
            "top_articles": brief.get("top_articles", []),
            "action_items": brief.get("action_items", []),
        },
        "raw_articles": top_articles_slim,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log.info(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
    return payload


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    base = Path(__file__).parent.parent
    assemble_latest(
        base / "output" / "articles.json",
        base / "output" / "brief.json",
        base / "web" / "data" / "latest.json",
    )
