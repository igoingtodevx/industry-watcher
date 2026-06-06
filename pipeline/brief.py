"""
brief.py — Takes scraped articles, calls LLM, produces a structured weekly brief.
"""
from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import re
from openai import OpenAI

log = logging.getLogger("brief")

SYSTEM_PROMPT = """Du bist ein Senior-Strategieberater für deutsche Mittelständler, die im Bereich Digitalisierung und KI-Transformation aktiv sind. Du erstellst wöchentliche Intelligence-Briefings.

DEIN OUTPUT-STIL:
- Klar, prägnant, geschäftlich relevant
- Keine Floskeln, keine Wiederholungen
- Konjunktiv-Indikativ wo passend, sonst Aktiv
- Englische Fachbegriffe wenn Standard, deutsche Übersetzung in Klammern beim ersten Auftauchen
- Konkrete Zahlen, Namen, Daten — keine Allgemeinplätze

DEIN BRIEF-AUFBAU (HTML-Fragmente, kein komplettes HTML-Dokument):
1. **headline** — Eine Zeile, max 100 Zeichen, der eigentliche Insight der Woche
2. **subheadline** — Max 200 Zeichen, Kontext
3. **executive_summary** — 3-4 Sätze als <p>...</p>, was diese Woche wirklich wichtig war
4. **trends** — 3-5 Trends, jeder als:
   <div class="trend">
     <h3>Trend-Titel</h3>
     <p>Was passiert (1-2 Sätze)</p>
     <p><strong>Warum relevant für Mittelstand:</strong> ...</p>
     <p><strong>Signal-Stärke:</strong> niedrig/mittel/hoch — basierend auf Anzahl Quellen + Konsistenz</p>
   </div>
5. **opportunities** — 3-5 Opportunities, jede als:
   <div class="opportunity">
     <h3>Opportunity-Titel</h3>
     <p><strong>Was:</strong> Konkreter Bedarf/Gap den ich gesehen habe (1-2 Sätze)</p>
     <p><strong>Wer würde zahlen:</strong> Zielgruppe (1 Satz)</p>
     <p><strong>Wie umsetzbar:</strong> niedrig/mittel/hoch — kann ein Solopreneur/Freelancer das in Tagen oder Wochen bauen?</p>
     <p><strong>Realistischer Preis:</strong> Range in EUR (z.B. 1.500-5.000€ Setup + 200-500€/Monat Retainer)</p>
   </div>
6. **top_articles** — Top 8 Artikel der Woche, jeder als:
   <div class="article">
     <h4><a href="URL">Titel</a></h4>
     <p class="meta">Quelle · Datum · 1-2 Schlagwörter</p>
     <p>Warum das wichtig ist (1-2 Sätze)</p>
   </div>
7. **action_items** — 3-5 konkrete Dinge, die ein KI-Automation-Freelancer DIESE WOCHE tun sollte:
   <ul><li>...</li></ul>

REGELN:
- Nutze NUR die bereitgestellten Artikel als Quellen. Keine externen Fakten erfinden.
- Wenn du etwas nicht aus den Artikeln belegen kannst, schreib "Signal aus X Artikel" oder lass es weg.
- Keine Clickbait-Überschriften. Kein "Sie werden nicht glauben...".
- Preise/Range: ehrlich und basierend auf typischen KMU-SaaS/Automation-Märkten.
- Antworte als reines JSON-Objekt, kein Markdown-Wrapper, kein Code-Block. Felder: headline, subheadline, executive_summary, trends (Array), opportunities (Array), top_articles (Array), action_items (Array).

JSON-FORMAT EXAKT:
{
  "headline": "...",
  "subheadline": "...",
  "executive_summary": "...",
  "trends": [{"title":"...","what":"...","why":"...","signal":"hoch|mittel|niedrig"}],
  "opportunities": [{"title":"...","what":"...","who":"...","how":"hoch|mittel|niedrig","price":"..."}],
  "top_articles": [{"title":"...","url":"...","source":"...","date":"YYYY-MM-DD","why":"...","tags":["..."]}],
  "action_items": ["...","..."]
}
"""


def build_user_prompt(articles: list[dict], vertical: str, n_articles: int = 25) -> str:
    """Build the user prompt with the actual articles."""
    sample = articles[:n_articles]
    items = []
    for i, a in enumerate(sample, 1):
        kw = ", ".join(a.get("keywords", [])[:5])
        items.append(
            f"{i}. [{a['source']} | {a['lang']} | {a['published'][:10]}] {a['title']}\n"
            f"   URL: {a['url']}\n"
            f"   KW: {kw}\n"
            f"   Zusammenfassung: {a.get('summary', '')[:400]}"
        )
    body = "\n\n".join(items)
    return f"""VERTICAL: {vertical}

ARTIKEL DIESE WOCHE ({len(sample)} von {len(articles)} insgesamt, sortiert nach Score):

{body}

Erstelle jetzt den Wochen-Brief im exakt spezifizierten JSON-Format. Achte auf:
- Trends MÜSSEN quer durch mehrere Quellen sichtbar sein, sonst sind sie kein Trend
- Opportunities MÜSSEN einen echten Bedarf adressieren, nicht "man könnte mal"
- Top-Articles sollten die mit höchstem Score sein, kuratiere auf max 8
- Action-Items müssen KONKRET und INNERHALB von 7 Tagen umsetzbar sein"""


def generate_brief(articles_path: Path, out_path: Path, model: str = "gpt-4o-mini") -> dict:
    """Read articles.json, call LLM, write brief.json."""
    with articles_path.open() as f:
        data = json.load(f)

    articles = data.get("articles", [])
    vertical = data.get("vertical", "")
    if not articles:
        raise ValueError("No articles in input — run scraper first.")

    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    user_prompt = build_user_prompt(articles, vertical)
    log.info(f"Calling {model} for brief (articles={len(articles)}, prompt={len(user_prompt)} chars)")

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
        max_tokens=4500,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content
    log.info(f"LLM returned {len(raw)} chars, tokens used: {resp.usage.total_tokens if resp.usage else '?'}")

    # Parse JSON (model is told to output JSON, with response_format json_object it should be clean)
    try:
        brief = json.loads(raw)
    except json.JSONDecodeError as e:
        # Try to recover by extracting first {...} block
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            brief = json.loads(m.group(0))
        else:
            log.error(f"Could not parse LLM output: {raw[:500]}")
            raise

    # Enrich with metadata
    brief["_meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "vertical": vertical,
        "input_articles": len(articles),
        "input_sources": data.get("source_count"),
        "tokens_used": resp.usage.total_tokens if resp.usage else None,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(brief, f, indent=2, ensure_ascii=False)
    log.info(f"Wrote {out_path}")
    return brief


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    base = Path(__file__).parent.parent
    generate_brief(base / "output" / "articles.json", base / "output" / "brief.json")
