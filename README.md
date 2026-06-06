# Industry Watcher

> Wöchentliches KI-Intelligence-Briefing für deutsche Mittelständler.
> Liest 9 kuratierte RSS-Quellen, gewichtet nach Recency × Source-Authority,
> destilliert mit GPT-4o-mini einen strukturierten Wochen-Brief (Trends,
> Opportunities, Top-Artikel, Action Items) und publisht ihn als statische Page.

**🌐 Live-Demo:** [ai-industry-watcher.vercel.app](https://ai-industry-watcher.vercel.app)
**📂 GitHub:** [github.com/igoingtodevx/industry-watcher](https://github.com/igoingtodevx/industry-watcher)

---

## Inhaltsverzeichnis

1. [Was ist das?](#was-ist-das)
2. [Demo](#demo)
3. [Wie funktioniert es?](#wie-funktioniert-es)
4. [Architektur](#architektur)
5. [Sources — alle 9 im Detail](#sources--alle-9-im-detail)
6. [Scoring & Filter](#scoring--filter)
7. [LLM: GPT-4o-mini im Detail](#llm-gpt-4o-mini-im-detail)
8. [Frontend — Editorial Design System](#frontend--editorial-design-system)
9. [Setup lokal](#setup-lokal)
10. [Deployment — Vercel](#deployment--vercel)
11. [Recurring — Cron](#recurring--cron)
12. [Custom Domain — Namecheap → Vercel](#custom-domain--namecheap--vercel)
13. [Anpassen: andere Branche, anderes Model, anderes Design](#anpassen-andere-branche-anderes-model-anderes-design)
14. [Kosten](#kosten)
15. [Limitationen & Roadmap](#limitationen--roadmap)
16. [Troubleshooting](#troubleshooting)

---

## Was ist das?

**Das Problem:** Wer ein deutsches KMU in den Bereichen Digitalisierung / KI-Automation berät (oder bedient), muss jede Woche dutzende Branchen-Quellen lesen, um zu wissen: was bewegt sich, was wird gekauft, was kommt regulatorisch, wo entstehen neue Pain-Points? Das ist manuell 3-5 Stunden pro Woche.

**Die Lösung:** Eine Pipeline, die
- jede Woche 9 kuratierte RSS-Quellen pulled,
- nach Recency × Source-Authority scored (50-60 Artikel pro Woche bleiben übrig),
- die Top 25 an GPT-4o-mini schickt mit einem strukturierten Prompt,
- einen JSON-formatierten Brief zurückbekommt mit 3-5 Trends, 3-5 Opportunities, 8 Top-Artikeln, 3-5 Action Items,
- und das Ganze als editorial-style statische Webpage rendert.

**Use Case:** Sales-Pitch für Freelancer/Dienstleister ("Schau, das ist was ich diese Woche für dich tun kann"), internes Intelligence-Dashboard für jede beliebige Vertical, Demo-Produkt für ein SaaS-Spin-off.

**Vertical dieser Instanz:** German Mittelstand · Digital & KI-Automation.
Kann in 5 Minuten umkonfiguriert werden auf jede andere Branche (siehe [Anpassen](#anpassen-andere-branche-anderes-model-anderes-design)).

---

## Demo

| Was | URL |
|---|---|
| Live-Page | https://ai-industry-watcher.vercel.app |
| Daten-JSON | https://ai-industry-watcher.vercel.app/data/latest.json |
| GitHub-Repo | https://github.com/igoingtodevx/industry-watcher |

Die Page lädt eine einzelne JSON-Datei (`web/data/latest.json`) und rendert client-side. Kein Backend im Live-Betrieb, kein Server, keine Datenbank. Reine statische Site auf Vercel.

---

## Wie funktioniert es?

```
┌─────────────────────────────────────────────────────────────┐
│  CRON (Mo 06:00 UTC) — GitHub Actions oder VPS-Cron        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1 — SCRAPER (pipeline/scraper.py)                   │
│  • 9 RSS-Feeds via feedparser (8s Timeout pro Source)       │
│  • Lookback 7 Tage, max 20 Artikel pro Source              │
│  • Keyword-Filter auf Heise/Golem (General-Feeds)          │
│  • Dedup auf URL + Titel-Prefix                             │
│  • Scoring: weight × expDecay(age, 48h half-life)          │
│  • → output/articles.json (50-60 Artikel)                  │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STAGE 2 — LLM BRIEF (pipeline/brief.py)                   │
│  • OpenAI-Call, Model: gpt-4o-mini                         │
│  • response_format=json_object                              │
│  • Top 25 Artikel als User-Prompt (15K chars)              │
│  • System-Prompt definiert exaktes Output-Schema            │
│  • → output/brief.json                                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STAGE 3 — STORAGE (pipeline/storage.py)                   │
│  • Nimmt articles + brief,                                  │
│  • schneidet raw_articles auf top 15 (Frontend-Größe),     │
│  • merged alles in web/data/latest.json (~25KB)            │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND (web/index.html + app.js)                        │
│  • Vanilla HTML+CSS+JS (kein Framework)                    │
│  • Fetcht latest.json (no-cache Header)                    │
│  • Rendert 5 Sektionen: Headline, Trends, Opportunities,   │
│    Top Articles, Action Items                               │
│  • Editorial Design (Monochrome Japanese, Noto Serif JP)   │
└─────────────────────────────────────────────────────────────┘
```

**End-to-end Zeit:** ~30 Sekunden (Scraper 9s + LLM-Call 25s)
**End-to-end Kosten:** ~$0.01 pro Run (gpt-4o-mini, 7K Tokens)

---

## Architektur

```
ai-industry-watcher/
├── README.md                          ← diese Datei
├── sources.yaml                       ← 9 RSS-Quellen + Scoring-Params
├── requirements.txt                   ← Python-Dependencies
├── vercel.json                        ← Static-Site Config für Vercel
├── .env.example                       ← OPENAI_API_KEY, OPENAI_BASE_URL
├── .gitignore
│
├── pipeline/                          ← Python-Backend
│   ├── __init__.py
│   ├── scraper.py                     ← feedparser + Score + Dedupe
│   ├── brief.py                       ← OpenAI Call + JSON-Parse
│   └── storage.py                     ← Merge zu web/data/latest.json
│
├── scripts/
│   └── run_pipeline.py                ← End-to-End-Runner
│
├── .github/workflows/
│   └── weekly-brief.yml               ← GH-Actions Cron (manuell hochladen)
│
├── web/                               ← Static Frontend (Vercel-Root)
│   ├── index.html                     ← Monochrome Japanese Editorial
│   ├── app.js                         ← Fetch + Render
│   └── data/
│       └── latest.json                ← Generated brief (committed via -f)
│
└── output/                            ← Intermediate, nicht committed
    ├── articles.json
    └── brief.json
```

### File-by-File

| File | Zweck | Output |
|---|---|---|
| `sources.yaml` | Single source of truth für alle RSS-Quellen, Gewichtungen, Keyword-Filter, Scoring-Params | YAML |
| `pipeline/scraper.py` | Pulled RSS, normalisiert Titel/Datum/Content, dedupliziert, scored | `output/articles.json` |
| `pipeline/brief.py` | Lädt articles, baut Prompt, ruft gpt-4o-mini, parst JSON-Response | `output/brief.json` |
| `pipeline/storage.py` | Aggregiert articles + brief zu Frontend-Payload, kürzt raw-articles | `web/data/latest.json` |
| `scripts/run_pipeline.py` | Orchestrator: ruft alle 3 Stages in Folge auf | Exit-Code |
| `web/index.html` | Statisches HTML mit Design Tokens (CSS Custom Properties) | HTML |
| `web/app.js` | Fetcht `data/latest.json`, rendert 5 Sektionen | DOM |
| `vercel.json` | Static-Site Config (output: web), Cache-Control für JSON | JSON |

---

## Sources — alle 9 im Detail

Konfiguriert in `sources.yaml`. Jede Quelle hat:
- `name` (Anzeige in der Page)
- `url` (RSS-Feed)
- `type` (immer `rss` aktuell, später `atom`/`web_scrape` möglich)
- `weight` (1-5, höher = stärker gewichtet im Scoring)
- `lang` (`de` oder `en`)
- `category` (für Gruppierung in zukünftigen Filtern)
- `keywords` (optional, Filter auf Titel — nur für General-Feeds)
- `optional` (wenn `true`, soft-fail — leerer Feed wird übersprungen statt Error)

### Aktive Quellen (gewichtet)

| # | Source | URL | Weight | Lang | Cat | Filter |
|---|---|---|---|---|---|---|
| 1 | **Heise Online (Hauptfeed, gefiltert)** | `heise.de/rss/heise-atom.xml` | 5 | de | tech-press | ja, 19 Keywords |
| 2 | **Golem.de (Hauptfeed, gefiltert)** | `rss.golem.de/rss.php?feed=RSS2.0` | 4 | de | tech-press | ja, 14 Keywords |
| 3 | **The Decoder** | `the-decoder.de/feed/` | 5 | de | ai-research | nein |
| 4 | **t3n Digital Pioneers** | `t3n.de/rss.xml` | 4 | de | digital-business | nein |
| 5 | **Elektroniknet** | `elektroniknet.de/rss/` | 3 | de | manufacturing | nein |
| 6 | **Ingenieur.de** | `ingenieur.de/feed/` | 3 | de | manufacturing | nein |
| 7 | **Bitkom Presse** *(optional)* | `bitkom.org/Presse/Presseinformation.rss` | 4 | de | industry-association | nein |
| 8 | **Industrie 4.0 Magazin** *(optional)* | `industrie40-magazin.de/feed/` | 3 | de | manufacturing | nein |
| 9 | **Hacker News (AI only)** *(optional)* | `hnrss.org/newest?q=AI+OR+agent+OR+automation&count=40` | 3 | en | tech-press | nein |

### Filter-Keywords für Heise/Golem

```yaml
keywords: [ki, künstlich, ai, agent, automatisierung, automation, llm, gpt, claude, openai, anthropic, digital, mittelstand, smb, saas, workflow, api, business, digitalisierung]
```

Ein Artikel wird **nur übernommen** wenn mindestens eines dieser Wörter im Titel vorkommt. Das schlägt die General-Feeds auf das relevante Subset runter — Heise-Atom hat 100+ Einträge/Tag, mit Filter bleiben 3-8.

### Eigene Quellen hinzufügen

1. URL testen: `curl -I <url>` → muss 200 + `application/rss+xml` oder `application/atom+xml` zurückgeben
2. In `sources.yaml` neuen Eintrag anlegen
3. Weight wählen: 5 = Top-Quelle, 4 = wichtig, 3 = nützlich, 2 = nice-to-have, 1 = experimentell
4. Für General-Feeds: `keywords` Liste definieren
5. Wenn Feed oft leer/kaputt: `optional: true` setzen

**Bekannte tote/gebrochene URLs (Stand Juni 2026):**
- `rss.golem.de/rss.php?tp=ki` → 404 (alte Subdomain)
- `bitkom.org/SiteGlobals/Functions/Feed/RSS/rss.xml` → 404 (Pfad geändert)
- `industrie40-magazin.de/feed/` → SSL-Error (Cert Mismatch)
- `mittelstand-digital.de/rss.xml` → 301 ohne Ziel
- `marketing-boerse.de/news/feed` → 404

→ Diese NICHT in `sources.yaml` aufnehmen.

---

## Scoring & Filter

`pipeline/scraper.py` macht vier Dinge in Folge:

### 1. Fetch
```python
socket.setdefaulttimeout(8)  # Global timeout
feedparser.parse(url)
```
8 Sekunden pro Feed, danach Skip. Verhindert dass ein hängender Feed den ganzen Run blockiert.

### 2. Date Filter
Nur Artikel der letzten `lookback_hours` (default: 168 = 7 Tage). Ältere Artikel werden verworfen, weil der Brief "diese Woche" abbildet.

### 3. Keyword Filter
Nur für Quellen mit `keywords`-Liste. Ein Artikel muss mindestens ein Keyword im **Titel** matchen.

### 4. Dedupe
- Exact URL dedup
- Title-Key dedup (erste 8 lowercase-Wörter des Titels)

Viele Quellen syndizieren die gleiche Heise-Meldung. Ohne Dedupe würde der gleiche Artikel 3-4x gewichtet.

### 5. Score
```
score = (weight × recency) + kw_bonus

recency = 0.5 ^ (age_hours / 48)   # 50% Verlust pro 48h
kw_bonus = min(0.2, 0.03 × len(keywords))
```

→ Ein 1-Tage-alter Heise-Artikel mit 5 Keywords: `5 × 0.96 + 0.15 = 4.95`
→ Ein 5-Tage-alter Golem-Artikel mit 3 Keywords: `4 × 0.74 + 0.09 = 3.05`
→ Ein 7-Tage-alter Bitkom-Artikel mit 2 Keywords: `4 × 0.5 + 0.06 = 2.06`

### 6. Cap
Nach Score sortiert, Top `max_articles_total` (default 50) bleiben. Rest fliegt raus.

---

## LLM: GPT-4o-mini im Detail

### Model-Wahl

`gpt-4o-mini` ist gewählt weil:
- **Preis:** $0.15 / 1M Input-Tokens, $0.60 / 1M Output-Tokens (Stand Juni 2026, OpenAI Standard)
- **Speed:** ~25 Sekunden für 7K Tokens
- **JSON-Mode:** Native `response_format: {type: "json_object"}` Unterstützung
- **Quality:** Mehr als ausreichend für strukturierte Briefing-Extraktion

**Alternativen (per ENV var `OPENAI_MODEL`):**
- `gpt-4o` — 10x teurer, marginal besser, nicht nötig
- `claude-3-5-sonnet` via OpenRouter — besseres Deutsch, ~3x teurer
- `llama-3.3-70b` via OpenRouter — kostenlos, aber JSON-Mode unzuverlässig
- Lokale Models (Ollama) — kein API-Key nötig, aber langsam auf CPU

### Prompt-Struktur

**System-Prompt** (`pipeline/brief.py`) definiert:
1. Persona: "Senior-Strategieberater für deutsche Mittelständler im Bereich Digitalisierung/KI"
2. Stil: klar, konkret, keine Floskeln, keine erfundenen Fakten
3. Output-Schema: 7 Felder (headline, subheadline, executive_summary, trends, opportunities, top_articles, action_items)
4. Regeln:
   - NUR Quellen aus Input nutzen, keine externen Fakten
   - Trends müssen quer durch mehrere Quellen sichtbar sein
   - Opportunities müssen echten Bedarf adressieren
   - Action Items müssen INNERHALB von 7 Tagen umsetzbar sein
5. JSON-Format-Beispiel (exakt)

**User-Prompt** baut die Top-25-Artikel-Liste (sortiert nach Score):
```
VERTICAL: German Mittelstand Digital & KI-Automation

ARTIKEL DIESE WOCHE (50 von 50 insgesamt, sortiert nach Score):

1. [The Decoder | de | 2026-06-05] Google mietet 110.000 Nvidia-Chips...
   URL: https://the-decoder.de/...
   KW: google, nvidia, spacex, ki, chips
   Zusammenfassung: ...

2. [...]
...
```

Plus explizite Reminder: "Trends MÜSSEN quer durch mehrere Quellen sichtbar sein", "Opportunities MÜSSEN echten Bedarf adressieren", "Action Items INNERHALB von 7 Tagen".

### Output-Schema

```json
{
  "headline": "max 100 chars, der eigentliche Insight der Woche",
  "subheadline": "max 200 chars, Kontext",
  "executive_summary": "3-4 Sätze als <p>-Text",
  "trends": [
    {"title": "...", "what": "...", "why": "...", "signal": "hoch|mittel|niedrig"}
  ],
  "opportunities": [
    {"title": "...", "what": "...", "who": "...", "how": "hoch|mittel|niedrig", "price": "EUR-Range"}
  ],
  "top_articles": [
    {"title": "...", "url": "...", "source": "...", "date": "YYYY-MM-DD", "why": "...", "tags": ["..."]}
  ],
  "action_items": ["konkret, in 7 Tagen machbar", "..."]
}
```

→ LLM gibt valides JSON zurück, das direkt vom Frontend gerendert wird. Kein Post-Processing, keine Templates, keine Sanitization-Schicht.

### Kosten pro Run

| Stage | Tokens | Kosten |
|---|---|---|
| Input (System + User Prompt) | ~6.500 | ~$0.001 |
| Output (Brief JSON) | ~700 | ~$0.0004 |
| **Total pro Run** | **~7.200** | **~$0.0015** |

Wöchentlicher Run: ~$0.08/Jahr. Vernachlässigbar.

---

## Frontend — Editorial Design System

### Design Tokens

In `web/index.html` als CSS Custom Properties (`:root`). Inspiriert von japanischen Editorial-Print-Magazinen (白黒 = schwarz-weiß, Swiss International Style).

```css
--paper: #f5f3ef;        /* warm off-white, Print-Charakter */
--paper-warm: #eeebe4;   /* leicht dunkler für Cards */
--paper-dark: #dedad2;   /* Header-Borders */
--ink: #0a0a0a;          /* fast schwarz, nicht 100% */
--ink-soft: #2b2b2b;     /* Body-Text */
--ink-mute: #6b6b6b;     /* Meta-Infos */
--ink-faint: #a0a09a;    /* Section-Labels */
--silver: #c0bdb6;       /* Akzent */
--gold: #b8b09a;         /* Akzent warm */

--serif-jp: "Noto Serif JP", "Hiragino Mincho Pro", "Yu Mincho", serif;
--sans: "Inter Tight", "Inter", -apple-system, sans-serif;
--body: "Inter", -apple-system, sans-serif;
--mono: "JetBrains Mono", "SF Mono", Menlo, monospace;

--signal-high: #b01a1a;  /* rot, dringend */
--signal-mid: #c08a30;   /* bernstein, mittel */
--signal-low: #6b9b3a;   /* grün, niedrig */
```

### Layout-Patterns

- **Masthead** (sticky): Brand links, Nav rechts, Issue-Nummer (W23-2026)
- **Hero** (80px padding): Headline (clamp 34-60px), Subheadline (Serif JP), Pill-Metriken
- **Sections** (01-05, nummeriert): Section-Titel + Japanisches 漢字 Label rechts
- **Cards** (Trends): 3-spaltig auf Desktop, weißer Hintergrund, Signal-Pille absolut positioniert
- **Cards** (Opportunities): Vollbreit, warmer Hintergrund, schwarze 4px Border-Left, Field-Grid mit Preis & Umsetzbarkeit
- **Articles** (Liste): Datum links (Mono), Title+Meta+Tags+Why rechts
- **Action Items** (Dark): Schwarzer Block mit ordered list, leading-zero Counter
- **CTA**: Warm-hell, Headline + Mailto-Button + GitHub-Link

### Responsiveness

- Container max-width: 980px
- Headline: `clamp(34px, 5.5vw, 60px)` — fluide Skalierung
- Grids: `auto-fit minmax(300px, 1fr)` — passen sich an
- Mobile (<720px): Single-Column, reduced padding, simplified nav

### JavaScript-Logik

`web/app.js` macht:
1. `fetch('data/latest.json', {cache: 'no-store'})`
2. Bei 404/Error: zeigt Error-State mit Hinweis auf Pipeline-Run
3. Bei Erfolg: rendert 5 Sektionen via `innerHTML`-Injection (alle Strings escaped)
4. Action Items als `<ol>` mit CSS-counter
5. Date-Formatting via `toLocaleDateString('de-DE')`

~200 Zeilen Vanilla JS, keine Dependencies, kein Build-Step.

---

## Setup lokal

### Voraussetzungen
- Python 3.11+
- pip oder uv
- OpenAI-Account (oder OpenRouter/anderer OpenAI-Compat Provider)

### Schritte

```bash
# 1. Clone
git clone https://github.com/igoingtodevx/industry-watcher.git
cd industry-watcher

# 2. Venv + Deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Env
cp .env.example .env
# .env editieren: OPENAI_API_KEY, OPENAI_BASE_URL setzen

# 4. Run
python scripts/run_pipeline.py

# 5. Frontend lokal ansehen
cd web && python3 -m http.server 8080
# → http://localhost:8080
```

### Was du sehen solltest

```
=== STEP 1/3 — Scrape ===
Fetching Heise Online (Hauptfeed, gefiltert auf KI/Digital) ...
  kept=3, filter-skipped=17
...
Raw articles fetched: 79
After dedupe: 79
After scoring/cap: 50

=== STEP 2/3 — Generate brief (LLM) ===
Calling gpt-4o-mini for brief (articles=50, prompt=15357 chars)
LLM returned 6889 chars, tokens used: 6994
Wrote output/brief.json

=== STEP 3/3 — Assemble frontend JSON ===
Wrote web/data/latest.json (27795 bytes)

PIPELINE OK
```

Wenn du weniger als 30 Artikel bekommst: RSS-Feeds prüfen (`curl -I <url>`), `lookback_hours` in `sources.yaml` erhöhen, neue Quellen hinzufügen.

---

## Deployment — Vercel

### Erst-Deployment

```bash
# Im Projekt-Root
vercel link --yes
vercel --prod --yes
```

Vercel erkennt automatisch:
- `vercel.json` mit `outputDirectory: "web"` → serviert `web/` als Root
- Static Files → kein Build-Step nötig
- `data/latest.json` ist inkludiert (gecached)

URL: `https://<project-name>-<hash>.vercel.app`

### Re-Deploy

```bash
vercel --prod --yes
```

Oder: GitHub-Integration aktivieren (Vercel → Project → Settings → Git → Connect Repo) → Push zu `master` triggert automatisch.

### Vercel-Settings (optional)

- **Domain:** Settings → Domains → Custom Domain hinzufügen
- **Environment Variables:** Settings → Environment Variables (für Production)
- **Build Command:** leer (Static Site)
- **Output Directory:** `web` (aus `vercel.json`)

---

## Recurring — Cron

### Option A: GitHub Actions (empfohlen)

Workflow-Datei: `.github/workflows/weekly-brief.yml`

**Setup:**
1. Workflow-Datei manuell auf GitHub hochladen (siehe Hinweis unten)
2. Repo → Settings → Secrets and variables → Actions → New secret:
   - `OPENAI_API_KEY` = dein Key
   - `OPENAI_BASE_URL` = `https://api.openai.com/v1`
3. Fertig — läuft jeden Mo 06:00 UTC

**Cron-Schedule anpassen** (in `weekly-brief.yml`):
```yaml
on:
  schedule:
    - cron: "0 6 * * 1"      # Mo 06:00 UTC
    # - cron: "0 18 * * 5"   # Fr 18:00 UTC (alternative)
  workflow_dispatch:          # manueller Trigger
```

**Hinweis zum Push:** GitHub-Actions-Workflows erfordern am Push-Token `workflow`-Scope. Falls dein Token den nicht hat (wie in dieser Repo-Initialisierung), lade die `.yml`-Datei direkt via GitHub-Web-UI hoch: Repo → "Add file" → "Create new file" → `.github/workflows/weekly-brief.yml` → pasten → Commit.

### Option B: VPS-Cron

```bash
# In /etc/cron.d/ai-industry-watcher
0 6 * * 1 deploy cd /home/deploy/workspace/ai-industry-watcher && \
  /home/deploy/workspace/.venv/bin/python3 scripts/run_pipeline.py >> \
  /var/log/industry-watcher.log 2>&1
```

### Option C: Manuell

```bash
cd /path/to/industry-watcher
python3 scripts/run_pipeline.py
git add web/data/latest.json && git commit -m "chore: brief" && git push
```

---

## Custom Domain — Namecheap → Vercel

Beispiel: `watcher.sejerlaenner.tech` (oder beliebige Subdomain einer bestehenden Domain).

### Schritte

1. **Namecheap:** Advanced DNS → Add new record
   ```
   Type: CNAME
   Host: watcher
   Value: cname.vercel-dns.com
   TTL: Automatic
   ```
2. **Vercel:** Project → Settings → Domains → "Add"
   - Domain: `watcher.sejerlaenner.tech`
   - Vercel verifiziert automatisch und generiert SSL (Let's Encrypt)
3. **Warten:** DNS-Propagation 5-30 Min, SSL-Generation 1-2 Min
4. **Live:** `https://watcher.sejerlaenner.tech`

Für Apex-Domain (`sejerlaenner.tech` ohne Subdomain): A-Record auf `76.76.21.21` statt CNAME.

---

## Anpassen: andere Branche, anderes Model, anderes Design

### Andere Branche (5 Min)

1. `sources.yaml` öffnen
2. URLs ersetzen oder hinzufügen (z.B. für "Bayerischer Maschinenbau":
   - `maschinenmarkt.de/feed/` (vorher testen!)
   - `konstruktionspraxis.de/feed/`
   - Branchenverbände, IHK-Feeds, Fachzeitschriften)
3. Filter-Keywords anpassen (was ist in dieser Branche relevant?)
4. `scoring.lookback_hours` evtl. anpassen (manche Branchen ticken wöchentlich, manche täglich)
5. `pipeline/brief.py` → `SYSTEM_PROMPT` anpassen: "Senior-Strategieberater für bayerische Maschinenbau-Betriebe" etc.

### Anderes Model (1 Min)

```bash
# In .env
OPENAI_MODEL=gpt-4o           # oder claude-3-5-sonnet, llama-3.3-70b, etc.
```

Oder in `pipeline/brief.py`:
```python
def generate_brief(..., model: str = "gpt-4o-mini"):
    # default-Param ändern
```

### Anderes Design (30 Min)

`web/index.html` Tokens austauschen (Farben, Fonts). Alles ist über CSS Custom Properties gesteuert.

Beliebte Alternativen:
- **Dark Mode:** Tokens invertieren, dunkler Hintergrund + heller Text
- **Magazin-Layout:** Multi-Column, größere Hero-Images
- **Minimal/Brutalist:** Weniger Borders, mehr Whitespace, Monospace-only

### Anderes Output-Format

- **PDF:** `pipeline/storage.py` erweitern um WeasyPrint + Jinja2 PDF-Template
- **Email-Daily:** Brief per SMTP an Subscriber schicken (statt nur Web)
- **Slack-Bot:** Brief als formattierte Slack-Message posten
- **API-Endpoint:** FastAPI um die Pipeline wickeln für Multi-Tenant SaaS

---

## Kosten

| Komponente | Pro Run | Pro Monat (4 Runs) | Pro Jahr |
|---|---|---|---|
| GPT-4o-mini (7K tokens) | $0.0015 | $0.006 | $0.08 |
| Vercel (Hobby Tier) | $0 | $0 | $0 |
| GitHub Actions (Public Repo) | $0 | $0 | $0 |
| RSS-Quellen | $0 | $0 | $0 |
| **Total** | **$0.0015** | **$0.006** | **$0.08** |

Bei mehr Runs/Tag: skaliert linear. 100 Runs/Tag = $4.50/Monat.

---

## Limitationen & Roadmap

### Aktuelle Limitationen

- **Mittelstand-Fokus suboptimal:** Heise/Golem filtern viel Global-Tech raus, aber The Decoder liefert 100% global. Für echte Mittelstand-Tiefe bräuchte es mehr Branchenverbands-Feeds (Bitkom, VDMA, DIHK).
- **Kein Eval:** Es gibt keine Messung ob die Opportunities tatsächlich "klickbar" sind. Manueller Review nötig.
- **Nur DE/EN:** Quellen in anderen Sprachen werden geparst aber LLM ignoriert sie.
- **Kein User-Feedback-Loop:** Welche Opportunities echte Klicks bekommen, wird nicht gemessen.
- **Statisches Frontend:** Keine Suche, keine Filter, keine historischen Briefings (nur "latest").
- **Kein RAG:** Top-25 werden einfach ins Prompt gepackt. Bei >100 Artikeln/Woche bräuchte es Embeddings + Vector-Store.

### Roadmap

- [ ] Tavily-basierte Fallback-Suche wenn RSS-Feeds leer sind
- [ ] Embedding-basierte RAG-Layer (sqlite-vec) für größere Quellen-Pools
- [ ] Multi-Tenant-API (FastAPI) mit Per-Customer-Quelle
- [ ] PDF-Export mit WeasyPrint
- [ ] Historische Briefings-Archiv (jeder Run committed)
- [ ] Email-Subscription (Resend/Brevo)
- [ ] Slack/Discord-Bot-Variante
- [ ] Source-Quality-Monitoring (welche Quellen liefern dauerhaft 0 Artikel?)

---

## Troubleshooting

### "0 Artikel nach Scraping"

→ Teste einzelne Feeds: `curl -I <url>`. Wenn 404: URL veraltet, neue suchen. Wenn 200 aber leer: `optional: true` setzen oder entfernen.

### "LLM-Output ist kein valides JSON"

→ Seltener Fall. `response_format: json_object` ist gesetzt, aber bei Network-Timeouts kann es vorkommen. `brief.py` hat Fallback-Regex (`\{[\s\S]*\}`) der das erste JSON-Block extrahiert. Falls das auch scheitert: in `output/brief.json` steht das rohe LLM-Output, manuell fixen.

### "Page lädt, zeigt aber nichts"

→ Browser-Konsole öffnen. Wenn "Konnte data/latest.json nicht laden": `web/data/latest.json` existiert nicht lokal oder wurde nicht committed. Pipeline lokal laufen lassen, dann `git add -f web/data/latest.json && git commit && git push`.

### "Vercel zeigt alten Content nach Push"

→ Vercel cached Static Files. Hard-Refresh (Ctrl+Shift+R) oder Vercel → Deployments → "..." → "Redeploy".

### "GitHub-Actions Cron läuft nicht"

→ Actions → Tab → Check ob Workflow-Fehler auftauchen. Häufigste Ursache: Secrets nicht gesetzt. Repo-Settings → Secrets prüfen.

### "Andere RSS-URLs testen"

```bash
for url in <url1> <url2> <url3>; do
  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 -A "python-requests/2.31.0" "$url")
  echo "$status  $url"
done
```

200 = OK, 301/302 = folgt Redirect (testen mit `-L`), 404 = tot, 5xx = Server-Problem.

---

## Contributing

Issues und PRs willkommen. Speziell:
- Neue RSS-Quellen für die Mittelstand-Vertical
- Andere Branchen-Quellen-Sets (gerne als `sources.<vertical>.yaml`)
- Bessere Filter-Keywords
- Verbesserungen am Prompt

## License

MIT — nutze, ändere, verkaufe weiter. Credit nice-to-have.

---

**Maintainer:** Flo's Hidden Labs · [floshiddenlabs.me](https://floshiddenlabs.me) · 2026
