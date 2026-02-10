# CLAUDE.md — Health Dashboard

> **Purpose:** Persistent project context for Claude sessions. Read this first, every time.
> **Last updated:** 2026-02-10

---

## 1. Project Overview

Personal health tracking dashboard for **Pierre Taljaard**. Syncs exercise and weight data from Garmin Connect to a local SQLite database, generates a static HTML dashboard (hosted on GitHub Pages), and sends daily Telegram health coaching notifications.

**This is a single-user personal project** — not a multi-tenant app, not an API, not a SaaS. All data belongs to one person. Simplicity is a feature.

---

## 2. Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| Database | SQLite (`health.db`, checked into git) |
| Dashboard | Static HTML with Tailwind CSS (CDN) + Chart.js (CDN) |
| Data source | Garmin Connect API via `garminconnect` library |
| Notifications | Telegram Bot API via `requests` |
| AI summary | Claude API (claude-3-haiku) via direct HTTP `requests` |
| Hosting | GitHub Pages (from `main` branch, `index.html`) |
| CI/CD | GitHub Actions (2 workflows: sync every 3h, notify daily at 6am SAST) |
| Config | `.env` file (local) + GitHub Secrets (CI) |
| Dependencies | `garminconnect`, `python-dotenv`, `requests` (see `requirements.txt`) |

---

## 3. Architecture Decisions

> ⚠️ **DO NOT CHANGE without discussion**

1. **SQLite as the single source of truth.** The project migrated from Notion to SQLite. `health.db` is committed to git so GitHub Actions can read/write it. Do not move to Postgres, Supabase, or any external DB.

2. **Static HTML dashboard.** `generate_dashboard.py` outputs a complete, self-contained HTML file. No frontend framework, no build step, no server. Do not introduce React, Next.js, or any bundler.

3. **No web server / no API.** The "API" is just Python scripts that read from SQLite and output HTML or send Telegram messages. Do not add Flask, FastAPI, or any HTTP server.

4. **Garmin → SQLite → HTML pipeline.** Data flows one way: Garmin API → `garmin_notion_sync.py` → `health.db` → `generate_dashboard.py` → `dashboard.html`/`index.html`. Keep this pipeline simple.

5. **Dashboard and database committed to git.** Both `health.db` and `dashboard.html`/`index.html` are version-controlled and auto-committed by the GitHub Actions sync workflow.

6. **Weight in kg, distance in km, duration in minutes.** All conversions happen at sync time (`garmin_notion_sync.py`). The rest of the codebase assumes these units.

7. **Dates stored as `YYYY-MM-DD` text strings.** Not Unix timestamps, not datetime objects in the DB.

8. **Activity types are a fixed set.** Garmin types map to a controlled vocabulary: Run, Trail Run, Walk, Hike, Indoor Cycle, Kettlebells, Tennis, Padel, Golf. The mapping lives in `GARMIN_TO_TYPE` in `garmin_notion_sync.py`.

---

## 4. Folder Structure

```
health-dashboard/
├── .env.example          # Template for local environment variables
├── .github/
│   └── workflows/
│       ├── sync.yml      # Every 3h: Garmin sync → generate dashboard → commit
│       └── notify.yml    # Daily 4am UTC (6am SAST): Telegram health summary
├── .gitignore
├── GARMIN_SYNC_SETUP.md  # Setup guide for Garmin-to-DB sync
├── TELEGRAM_BOT_SPEC.md  # Full specification for Telegram notifications
├── db.py                 # Shared database module (get_connection, init_db)
├── garmin_notion_sync.py # Syncs Garmin data → SQLite (activities + weight)
├── generate_dashboard.py # Generates static HTML dashboard from SQLite data
├── health_notifications.py # Builds daily summary + sends via Telegram
├── health.db             # SQLite database (committed to git)
├── dashboard.html        # Generated HTML dashboard
├── index.html            # Copy of dashboard.html (served by GitHub Pages)
├── daily_health_sync.sh  # Local shell script: sync + generate (macOS, legacy)
├── push_dashboard.sh     # Local shell script: copy + git push (macOS, legacy)
└── requirements.txt      # Python dependencies
```

**Note:** `daily_health_sync.sh` and `push_dashboard.sh` contain hardcoded local macOS paths. They are legacy scripts from before the GitHub Actions migration. The CI workflows (`sync.yml`, `notify.yml`) are the authoritative automation.

---

## 5. Database Schema

### `activities`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key, autoincrement |
| exercise | TEXT | Activity name from Garmin (e.g., "Morning Run") |
| date | TEXT | `YYYY-MM-DD` format |
| type | TEXT | Mapped type: Run, Walk, Kettlebells, etc. |
| garmin_activity_id | TEXT | Unique Garmin ID (prevents duplicate syncs) |
| duration | REAL | Minutes (converted from seconds at sync time) |
| distance | REAL | Kilometres (converted from metres at sync time) |
| calories | INTEGER | |
| avg_heart_rate | INTEGER | |
| max_heart_rate | INTEGER | |
| notes | TEXT | Garmin activity description (max 2000 chars) |

### `weigh_ins`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key, autoincrement |
| date | TEXT | `YYYY-MM-DD` format, UNIQUE constraint |
| weight_kg | REAL | Weight in kilograms (converted from grams at sync time) |

**Key constraints:**
- `activities.garmin_activity_id` has a UNIQUE constraint (deduplication)
- `weigh_ins.date` has a UNIQUE constraint (one entry per day)
- Both tables use `INSERT OR IGNORE` for idempotent syncs

---

## 6. Scripts and Their Purposes

| Script | Purpose | Triggered by |
|--------|---------|-------------|
| `garmin_notion_sync.py` | Fetch activities + weight from Garmin API, insert into SQLite | `sync.yml` (every 3h) or manual |
| `generate_dashboard.py` | Read SQLite, compute stats, generate `dashboard.html` | `sync.yml` (after sync) or manual |
| `health_notifications.py` | Build daily health summary, send via Telegram | `notify.yml` (6am SAST daily) or manual |
| `db.py` | Shared DB module: `get_connection()`, `init_db()` | Imported by all Python scripts |

**There are no API routes.** This is not a web application.

---

## 7. Environment Variables

### Local development (`.env` file)
| Variable | Used by | Purpose |
|----------|---------|---------|
| `GARMIN_EMAIL` | `garmin_notion_sync.py` | Garmin Connect login email |
| `GARMIN_PASSWORD` | `garmin_notion_sync.py` | Garmin Connect login password |
| `DAYS_TO_SYNC` | `garmin_notion_sync.py` | Days of history to sync (default: 7) |

### GitHub Secrets (CI only)
| Secret | Used by | Workflow |
|--------|---------|---------|
| `GARMIN_EMAIL` | `garmin_notion_sync.py` | `sync.yml` |
| `GARMIN_PASSWORD` | `garmin_notion_sync.py` | `sync.yml` |
| `ANTHROPIC_API_KEY` | `generate_dashboard.py` | `sync.yml` |
| `TELEGRAM_BOT_TOKEN` | `health_notifications.py` | `notify.yml` |
| `TELEGRAM_CHAT_ID` | `health_notifications.py` | `notify.yml` |

---

## 8. Code Conventions

- **Pure Python scripts** — no classes except `GarminClient`. Functions are the primary abstraction.
- **British English spelling** in comments and variable names (e.g., "initialise", "summarise").
- **f-strings** used throughout for string formatting.
- **`db.py` is the single entry point** for all database access. Never create a `sqlite3.connect()` call outside of `db.py`.
- **Logging** via Python `logging` module in `garmin_notion_sync.py`; `print()` statements in other scripts.
- **No type hints** in existing code (no mypy or type checking).
- **No tests.** There is no test suite.
- **HTML is generated as a Python f-string** in `generate_dashboard.py`. The entire dashboard is one massive string template. Avoid adding more HTML generation this way if possible.
- **Activity type constants** are defined as sets (e.g., `CARDIO_TYPES`) and dicts (e.g., `GARMIN_TO_TYPE`). Keep these as the canonical source.

---

## 9. Health Tracking Business Rules

These are domain-specific rules embedded in the code. Future changes must respect them:

- **Weekly targets** (rolling 7 days): 4 cardio, 3 strength (Kettlebells)
- **Monthly targets** (calendar month): 16 cardio, 10 strength
- **Grace thresholds:** Weekly allows 1 below target (3 cardio OK, 2 strength OK). Monthly allows 1 behind pace.
- **Rest day warnings:** 2+ consecutive = warning, 3+ = urgent
- **Weigh-in reminders:** Alert if no weigh-in for 3+ days
- **"Last 7 days"** = yesterday + 6 days before (excludes today)
- **Falling off:** Checks what activity from 8 days ago will leave the 7-day window tomorrow
- **Cardio types:** Run, Trail Run, Walk, Hike, Rucking, Indoor Cycle, Tennis, Padel, Golf
- **Strength type:** Kettlebells only
- **Weight goal:** 82 kg by end of 2026 (starting from 97.5 kg on 1 Jan 2026)
- **Coaching philosophy:** Intermittent fasting (16:8), low-carb, MAF Method (low-intensity aerobic). Never recommend HIIT or calorie counting in the AI summary.
- **AI summary model:** `claude-3-haiku-20240307` via direct API call (not SDK). Max 300 tokens, 3 paragraphs, max 180 words.

---

## 10. Current Feature Status

### ✅ Complete
- Garmin Connect sync (activities + weight → SQLite)
- Static HTML dashboard with Tailwind + Chart.js
- Weekly / monthly / YTD stats
- Weight progress chart with 10-day rolling average
- Calendar view with workout day indicators
- AI-powered progress summary (Claude Haiku)
- Daily Telegram health coaching notification
- "Falling off" warnings (activity leaving 7-day window)
- Today's exercise recommendation (priority-based logic)
- GitHub Actions automation (sync every 3h, notify daily 6am SAST)
- GitHub Pages deployment

### 🔧 Partially Built / Needs Work
- `daily_health_sync.sh` / `push_dashboard.sh` — legacy local scripts with hardcoded macOS paths; superseded by GitHub Actions but still in repo
- `.env.example` is incomplete — missing `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ANTHROPIC_API_KEY`
- `garmin_notion_sync.py` still named with "notion" despite migrating away from Notion

### ❌ Not Started
- No test suite
- No reply commands for Telegram bot (/status, /week, /month)
- No streak celebrations
- No weekly Sunday summary
- No error alerting (if a GitHub Action fails, no notification is sent)

---

## 11. Known Issues / Tech Debt

1. **File naming:** `garmin_notion_sync.py` references Notion in its name but has nothing to do with Notion. Rename to `garmin_sync.py`.
2. **Giant HTML template:** `generate_dashboard.py` has a ~350-line f-string HTML template. Difficult to maintain. Consider Jinja2 templates if it grows further.
3. **No error handling on GitHub Actions failures.** If the sync or notify workflow fails, nobody gets alerted.
4. **Shell scripts have hardcoded paths.** `daily_health_sync.sh` and `push_dashboard.sh` use absolute macOS paths. Could be removed or updated.
5. **`CARDIO_TYPES` defined in multiple places.** Both `health_notifications.py` and `generate_dashboard.py` define cardio types independently. Should be centralised in `db.py` or a constants module.
6. **AI model is hardcoded.** `generate_dashboard.py` uses `claude-3-haiku-20240307`. Should use a newer model or make it configurable.
7. **No `.env.example` for all env vars.** Telegram and Anthropic vars are undocumented in the template.

---

## 12. Session Log

_Format for future sessions:_

```
### YYYY-MM-DD — Brief description
**Changes:**
- What was added/changed/fixed

**Decisions made:**
- Any architectural or business rule decisions

**Known issues introduced:**
- Any new tech debt or issues
```
