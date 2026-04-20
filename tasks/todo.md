# News Aggregator — Leaf-node Plan

## Phase 1 — Scaffolding
- [x] L1: Repo structure + requirements.txt + .env.example + README.md
- [x] L2: app/config.py — source whitelist, tickers, cities, keyword weights

## Phase 2 — Storage
- [x] L3: app/db/schema.sql + app/db/init.py — articles, prices, weather, fetch_log

## Phase 3 — Ingestion
- [x] L4: app/ingest/rss.py — generic feedparser RSS fetcher
- [x] L5: app/ingest/google_news.py — Google News RSS per source domain
- [x] L6: app/ingest/sources.py — registry: source → fetcher + URL/query
- [x] L7: app/ingest/classify.py — region bucket + importance score
- [x] L8: app/ingest/dedup.py — URL hash + title similarity
- [x] L9: app/ingest/run.py — fetch → dedup → classify → insert

## Phase 4 — Market + weather
- [x] L10: app/ingest/markets.py — yfinance + exchangerate.host
- [x] L11: app/ingest/weather.py — Open-Meteo, 7 Gulf cities

## Phase 5 — API
- [x] L12: app/api/main.py — /api/snapshot, /api/news/{major,minor}, /api/markets, /api/weather
- [x] L13: app/api/selectors.py — major-box selector + stickiness

## Phase 6 — Scheduling
- [x] L14: app/scheduler.py — APScheduler driver

## Phase 7 — Deploy
- [x] L15: deploy/newsagg.service — systemd unit
- [x] L16: deploy/nginx.conf — reverse proxy
- [x] L17: deploy/README.md — Ubuntu EC2 bringup

## Phase 8 — Verify
- [x] L18: Local smoke test — run, inspect DB, hit endpoints

## Review (after L18 smoke test)

**End-to-end pipeline works.** Live run ingested 910 raw items from 22 sources,
deduped to 838 new, classifier kept 800. Major box populated, stickiness active.
Weather: 7/7 Gulf cities. Markets: 15/15 after fixes.

**Deltas from the original plan — root-caused and corrected:**

1. **Gulf direct-RSS feeds are malformed.** The National / Khaleej Times / Gulf News
   / Arab News all return XML that feedparser can't recover. Switched those four
   to Google News fetcher (same source identity, reliable data). Later, if direct
   feeds are fixed publisher-side, swap back in one line in `app/config.py`.

2. **yfinance is rate-limited (Yahoo 429) from shared IPs.** Replaced with Stooq
   light-quote CSV (commodities + indices, free, no key) and open.er-api.com
   (FX, one batched call). Dropped yfinance + pandas + numpy from requirements.
   Lighter, faster, actually works.

3. **Gulf indices other than Tadawul aren't available on any reliable free
   source.** Dropped ADX, DFM, QE from config — Tadawul (`^tasi`) stays. Upgrade
   path: Polygon / Twelve Data / TwelveData (paid) if Gulf coverage matters later.

4. **Intraday change semantics:** stooq light endpoint gives OHLC for today only.
   `change_pct = (Close − Open) / Open × 100` — intraday move from open. On
   weekends/holidays Open == Close so 0%. Documented in `markets.py`.
   Note: FX change is vs last stored fetch (er-api has no prior-day in free tier).

**Known gaps for v2:**
- TLS / domain on EC2 (step 10 in `deploy/README.md` covers when ready).
- Front-end (separate project — design options pending).
- Historical data / change-vs-prior-day for commodities & indices (would need
  a paid vendor or a longer-lived local cache we backfill).
- Sentiment / LLM summaries not required for v1 (source whitelist handles quality).

