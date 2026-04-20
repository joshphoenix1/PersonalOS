"""Markets fetcher.

Commodities + indices: Stooq daily CSV (free, no key, reliable).
FX: open.er-api.com — one call gives every currency vs USD.
Both are free. Yfinance is avoided because Yahoo rate-limits aggressively.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone

import httpx

from app.config import COMMODITIES, FX_PAIRS, INDICES
from app.db.init import log_fetch, tx

log = logging.getLogger(__name__)

STOOQ_QUOTE = "https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv"
ER_API = "https://open.er-api.com/v6/latest/USD"


def _fetch_stooq(client: httpx.Client, symbol: str) -> dict | None:
    """Return {price, prev_close, change_pct} from stooq's light quote endpoint.

    CSV: Symbol,Date,Time,Open,High,Low,Close,Volume. We use Close as current
    price and today's Open as the prev_close proxy (gives intraday change from
    open — standard interpretation for active markets; zero on weekends).
    """
    try:
        r = client.get(STOOQ_QUOTE.format(sym=symbol), timeout=10)
        r.raise_for_status()
    except Exception as e:
        log.info("stooq http fail for %s: %s", symbol, e)
        return None

    body = r.text.strip()
    if "N/D" in body or not body:
        return None

    reader = csv.DictReader(io.StringIO(body))
    row = next(reader, None)
    if not row:
        return None
    try:
        open_ = float(row["Open"])
        close = float(row["Close"])
    except (KeyError, TypeError, ValueError):
        return None

    change_pct = ((close - open_) / open_ * 100.0) if open_ else 0.0
    return {"price": close, "prev_close": open_, "change_pct": round(change_pct, 3)}


def _fetch_fx_all(client: httpx.Client) -> dict[str, float] | None:
    """Returns {currency_code: rate_vs_usd} or None on failure."""
    try:
        r = client.get(ER_API, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("er-api failed: %s", e)
        return None
    if data.get("result") != "success":
        log.warning("er-api non-success: %s", data.get("result"))
        return None
    return data.get("rates") or None


def _prev_fx_price(symbol: str) -> float | None:
    """Look up the stored price for this FX symbol before this fetch. Used to
    derive change_pct for FX, which er-api doesn't provide directly."""
    from app.db.init import get_conn
    conn = get_conn()
    try:
        row = conn.execute("SELECT price FROM prices WHERE symbol = ?", (symbol,)).fetchone()
    finally:
        conn.close()
    return row["price"] if row else None


def fetch_markets() -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    rows: list[tuple] = []
    misses: list[str] = []

    with httpx.Client(headers={"User-Agent": "newsagg/0.1"}) as client:
        # Commodities + indices via stooq
        for label, sym in list(COMMODITIES.items()) + list(INDICES.items()):
            category = "commodity" if label in COMMODITIES else "index"
            q = _fetch_stooq(client, sym)
            if q is None:
                misses.append(sym)
                continue
            rows.append((sym, label, category, q["price"], q["prev_close"], q["change_pct"], now_iso))

        # FX via one batched er-api call
        fx_rates = _fetch_fx_all(client)
        if fx_rates is None:
            for label, ccy, _invert in FX_PAIRS:
                misses.append(f"FX:{label}")
        else:
            for label, ccy, invert in FX_PAIRS:
                raw = fx_rates.get(ccy)
                if raw is None or raw == 0:
                    misses.append(f"FX:{label}")
                    continue
                price = (1.0 / raw) if invert else float(raw)
                prev = _prev_fx_price(f"fx:{ccy}") or price
                change_pct = ((price - prev) / prev * 100.0) if prev else 0.0
                rows.append((f"fx:{ccy}", label, "fx", price, prev, round(change_pct, 4), now_iso))

    with tx() as conn:
        conn.executemany(
            """INSERT INTO prices (symbol, label, category, price, prev_close, change_pct, fetched_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(symbol) DO UPDATE SET
                 label=excluded.label,
                 category=excluded.category,
                 price=excluded.price,
                 prev_close=excluded.prev_close,
                 change_pct=excluded.change_pct,
                 fetched_at=excluded.fetched_at""",
            rows,
        )

    msg = f"hit={len(rows)} miss={len(misses)}"
    if misses:
        msg += f" missing={','.join(misses)}"
    log_fetch("markets", "ok", msg, len(rows))
    return {"hit": len(rows), "miss": len(misses), "missing": misses}


if __name__ == "__main__":
    import logging as _l
    _l.basicConfig(level=_l.INFO)
    print(fetch_markets())
