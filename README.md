# Industry Watcher — German Mittelstand Digital & KI

Wöchentliches Intelligence-Briefing für deutsche Mittelständler. Liest 9+ RSS-Quellen, gewichtet nach Recency × Source-Authority, schickt das Beste an GPT-4o-mini, das einen strukturierten Wochen-Brief generiert (Trends, Opportunities, Top-Artikel, Action Items).

Live-Demo: siehe Vercel-Deployment URL nach `vercel --prod`.

## Architektur

```
sources.yaml          # 9 RSS-Quellen mit Gewichtung + Keyword-Filter
pipeline/
  scraper.py          # feedparser → normalize → dedupe → score
  brief.py            # OpenAI-Call mit strukturiertem Prompt → JSON
  storage.py          # Aggregiert zu web/data/latest.json
scripts/
  run_pipeline.py     # End-to-End-Runner
web/
  index.html          # Editorial-Style Frontend (Monochrome Japanese)
  app.js              # Fetches latest.json, rendert
  data/latest.json    # Generierter Brief (committed)
.github/workflows/
  weekly-brief.yml    # GitHub Actions Cron (Mo 06:00 UTC)
vercel.json           # Static-Site Config
```

## Setup

```bash
# Python 3.12, venv optional
pip install -r requirements.txt

# Env-Vars (siehe .env.example)
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://api.openai.com/v1
```

## Nutzung

```bash
# Einmaliger Run
python scripts/run_pipeline.py

# Resultate
cat output/articles.json | head -50
cat output/brief.json | head -50
cat web/data/latest.json | head -10

# Frontend lokal
cd web && python3 -m http.server 8080
# → http://localhost:8080
```

## Deploy

```bash
vercel --prod --yes
# Output: https://ai-industry-watcher-[hash].vercel.app
```

## Recurring

**Option A: GitHub Actions** (siehe `.github/workflows/weekly-brief.yml`)
- Pushe Repo zu GitHub
- Setze Secrets: `OPENAI_API_KEY`, `OPENAI_BASE_URL`
- Cron läuft Mo 06:00 UTC, committet `web/data/latest.json`
- Vercel auto-redeployt bei neuem Commit

**Option B: VPS-Cron**
```bash
# In /etc/cron.d/ai-industry-watcher
0 6 * * 1 deploy cd /home/deploy/workspace/ai-industry-watcher && /home/deploy/workspace/.venv/bin/python3 scripts/run_pipeline.py
```

## Sources

Aktuelle 9 Quellen (siehe `sources.yaml`):
- Heise Online (gefiltert auf KI/Digital) — weight 5
- Golem.de (gefiltert) — weight 4
- The Decoder — weight 5
- t3n Digital Pioneers — weight 4
- Elektroniknet — weight 3
- Ingenieur.de — weight 3
- Bitkom (try) — weight 4, optional
- Industrie 4.0 Magazin — weight 3, optional
- Hacker News AI — weight 3, optional

Quellen mit `optional: true` werden übersprungen wenn leer/fehlerhaft.

## Customization

- **Andere Branche:** `sources.yaml` editieren (URLs + Keywords anpassen)
- **Anderes Model:** `OPENAI_MODEL` env var oder `--model` Flag
- **Anderer Look:** `web/index.html` Tokens anpassen (CSS Custom Properties)
- **Output-Format:** `pipeline/brief.py` `SYSTEM_PROMPT` editieren

## Kosten

Pro Run: ~7.000 GPT-4o-mini Tokens (~$0.01 bei OpenAI-Standard-Pricing).

Wöchentlicher Run: ~$0.50/Monat. Selbst gehostet = quasi kostenlos.
