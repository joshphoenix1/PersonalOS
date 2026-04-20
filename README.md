# News Aggregator

Backend for a Gulf-focused executive news dashboard. Ingests RSS/Google News from
a whitelisted set of non-partisan professional sources, layers commodity/FX/index
tickers and Gulf-city weather, and serves the whole thing as a JSON API for a
frontend to render.

## Scope

- **News:** finance, geopolitics, Gulf region. No opinion, tabloid, or editorial.
- **Markets:** Brent, WTI, gold, US + Gulf indices, EUR/USD + USD/GCC-currency pairs.
- **Weather:** GCC capitals/commercial hubs.
- **Cadence:** 15 min news/markets, hourly weather. Major items stick up to 12h.

## Quickstart (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# L3+ will populate the DB and runners; for now the scaffold is empty.
```

## Layout

```
app/
  api/         # FastAPI routes + selectors
  db/          # SQLite schema + access
  ingest/      # RSS, Google News, markets, weather, classify, dedup
  config.py    # source whitelist, tickers, cities, keyword weights
  scheduler.py # APScheduler entrypoint
deploy/        # systemd + nginx + EC2 bringup
tasks/         # todo.md, lessons.md
```

## Deployment

Target: Ubuntu EC2. See `deploy/README.md` after L17.
