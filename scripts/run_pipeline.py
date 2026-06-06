#!/usr/bin/env python3
"""
run_pipeline.py — End-to-end: scrape → brief → frontend JSON.
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.scraper import run as run_scraper
from pipeline.brief import generate_brief
from pipeline.storage import assemble_latest


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )
    base = Path(__file__).parent.parent

    # 1) Scrape
    log.info("=" * 60)
    log.info("STEP 1/3 — Scrape")
    log.info("=" * 60)
    articles_data = run_scraper(
        sources_path=base / "sources.yaml",
        out_path=base / "output" / "articles.json",
    )
    if not articles_data.get("articles"):
        log.error("No articles scraped — aborting.")
        return 1

    # 2) Brief
    log.info("=" * 60)
    log.info("STEP 2/3 — Generate brief (LLM)")
    log.info("=" * 60)
    brief = generate_brief(
        articles_path=base / "output" / "articles.json",
        out_path=base / "output" / "brief.json",
    )
    log.info(f"Brief headline: {brief.get('headline', '?')[:80]}")

    # 3) Assemble frontend payload
    log.info("=" * 60)
    log.info("STEP 3/3 — Assemble frontend JSON")
    log.info("=" * 60)
    assemble_latest(
        articles_path=base / "output" / "articles.json",
        brief_path=base / "output" / "brief.json",
        out_path=base / "web" / "data" / "latest.json",
    )

    log.info("=" * 60)
    log.info("PIPELINE OK — frontend at web/index.html, data at web/data/latest.json")
    log.info("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
