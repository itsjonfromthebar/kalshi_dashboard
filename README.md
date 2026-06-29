# Kalshi Intelligence Dashboard

A local-first Streamlit dashboard for personal Kalshi market tracking, snapshots, watchlists, movers, alerts, portfolio lookup, and daily briefs.

## Current features

- Kalshi REST client
- Demo/prod environment config
- RSA-PSS request signing for authenticated endpoints
- SQLite-first database
- Market ingestion and historical snapshots
- Markets explorer with search/category/volume filters
- Movers and opportunity scanner
- Watchlist with charts
- Single-market probability and volume charts
- Portfolio lookup for authenticated accounts
- Probability alert rules and alert history
- Markdown daily brief generator
- Scheduler script for recurring snapshots + alert evaluation
- Docker support

Kalshi docs note that the API covers real-time market data and trade execution, and includes REST, WebSocket, and FIX APIs for prediction markets. The docs index also lists markets, order books, trades, positions, balance, fills, candlesticks, live data, and rate-limit endpoints.

## Setup

### Windows PowerShell (recommended)

```powershell
cd C:\Users\jchap\OneDrive\Documents\Kalshi\kalshi_dashboard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

On its first run, the app creates `kalshi_dashboard.db` and loads clearly labelled sample data. No Kalshi account, key, or network call is needed. To search public production markets, use **Fetch public live markets** in the sidebar; it downloads up to 10,000 open markets into SQLite and does not require credentials. This is a manual live sync, not a continuously streaming feed: click it again whenever you want a fresh public-market snapshot. If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` once in that window, then repeat the activation command.

## Continuous public ticker feed

After you have clicked **Fetch public live markets** once, open a second Command Prompt window and run:

```bat
cd /d "C:\Users\jchap\OneDrive\Documents\Kalshi\kalshi_dashboard"
.venv\Scripts\activate.bat
pip install -r requirements.txt
python scripts\live_poll.py
```

Leave that second window running. It refreshes public market prices every 60 seconds and writes them into SQLite; the Streamlit Explorer will show the updated values when it reruns. Press `Ctrl+C` in the second window to stop it. The updater is read-only and never submits orders.

Only edit `.env` when you later want to connect your own Kalshi account:

```bash
KALSHI_ENV=demo
KALSHI_API_KEY_ID=your-api-key-id
KALSHI_PRIVATE_KEY_PATH=./kalshi_private.key
DATABASE_URL=sqlite:///./kalshi_dashboard.db
SNAPSHOT_INTERVAL_MINUTES=5
SNAPSHOT_LIMIT=200
```

Place your downloaded Kalshi private key at the path above. Do not commit it. Private portfolio requests require both credential values. This dashboard never places trades.

## Run one snapshot

```powershell
$env:PYTHONPATH = "app"
python scripts/snapshot.py
```

## Run dashboard

```powershell
streamlit run app.py
```

## Run background scheduler

```powershell
$env:PYTHONPATH = "app"
python scripts/run_scheduler.py
```

## Evaluate alerts manually

```powershell
$env:PYTHONPATH = "app"
python scripts/evaluate_alerts.py
```

## Generate daily brief manually

```powershell
$env:PYTHONPATH = "app"
python scripts/daily_brief.py
```

## Docker

```bash
docker compose up --build
```

## Cloud deployment

This folder is prepared for Streamlit Community Cloud or Docker-based hosting.

- Main app file: `app.py`
- Python runtime: `python-3.12`
- Cloud login is controlled by `APP_AUTH_REQUIRED`, `APP_USERNAME`, and `APP_PASSWORD`.
- First cloud launch does not require Kalshi API credentials.
- Local database files, private keys, `.env`, and `.venv` are intentionally ignored.

See `DEPLOYMENT.md` for the step-by-step cloud setup.

## What to build next

See `CODEX_NEXT_STEPS.md`.

## Safety note

This starter app is for monitoring and analysis. It does not place trades. Keep API private keys out of GitHub.
