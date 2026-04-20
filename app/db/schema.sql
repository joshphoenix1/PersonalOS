-- News aggregator SQLite schema.
-- articles: ingested stories, dedup keyed on url_hash.
-- prices:   one row per symbol (INSERT OR REPLACE keeps it current).
-- weather:  one row per city (INSERT OR REPLACE).
-- fetch_log: diagnostics.

CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash      TEXT    NOT NULL UNIQUE,
    url           TEXT    NOT NULL,
    title         TEXT    NOT NULL,
    summary       TEXT,
    source        TEXT    NOT NULL,
    source_weight REAL    NOT NULL DEFAULT 0.5,
    published_at  TEXT,           -- ISO8601 UTC, may be NULL if feed lacks it
    fetched_at    TEXT    NOT NULL,
    region        TEXT    NOT NULL,  -- gulf | iran_war | oil_markets | markets_macro | global | drop
    score         REAL    NOT NULL DEFAULT 0.0,
    is_major      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles(fetched_at);
CREATE INDEX IF NOT EXISTS idx_articles_score      ON articles(score);
CREATE INDEX IF NOT EXISTS idx_articles_is_major   ON articles(is_major, fetched_at);
CREATE INDEX IF NOT EXISTS idx_articles_region     ON articles(region);

CREATE TABLE IF NOT EXISTS prices (
    symbol      TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    category    TEXT NOT NULL,      -- commodity | index | fx
    price       REAL,
    prev_close  REAL,
    change_pct  REAL,
    fetched_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weather (
    city        TEXT PRIMARY KEY,
    lat         REAL NOT NULL,
    lon         REAL NOT NULL,
    temp_c      REAL,
    feels_c     REAL,
    humidity    REAL,
    wind_kph    REAL,
    weather_code INTEGER,
    summary     TEXT,
    high_c      REAL,
    low_c       REAL,
    fetched_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fetch_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    target   TEXT NOT NULL,
    status   TEXT NOT NULL,      -- ok | error
    message  TEXT,
    items    INTEGER DEFAULT 0,
    ts       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fetch_log_ts ON fetch_log(ts);
