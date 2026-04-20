"""DB read helpers shaped for the API responses.

Major-box stickiness: articles marked is_major=1 in the last `sticky_hours` stay in
the major list even if newer, higher-scoring items exist. New majors are appointed
each ingest cycle by run.py (top-5 by score in last 24h).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.db.init import get_conn


def _row_to_article(r) -> dict[str, Any]:
    return {
        "id": r["id"],
        "title": r["title"],
        "summary": r["summary"],
        "url": r["url"],
        "source": r["source"],
        "region": r["region"],
        "score": r["score"],
        "published_at": r["published_at"],
        "fetched_at": r["fetched_at"],
    }


def get_major_news(limit: int = 8) -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=settings.major_sticky_hours)).isoformat()
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT id, title, summary, url, source, region, score, published_at, fetched_at
               FROM articles
               WHERE is_major = 1 AND fetched_at > ?
               ORDER BY score DESC, fetched_at DESC
               LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_article(r) for r in rows]


def get_minor_news(limit: int = 30, offset: int = 0, region: str | None = None) -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=settings.article_retention_hours)).isoformat()
    sql = """SELECT id, title, summary, url, source, region, score, published_at, fetched_at
             FROM articles
             WHERE is_major = 0 AND region != 'drop' AND fetched_at > ?"""
    params: list[Any] = [cutoff]
    if region:
        sql += " AND region = ?"
        params.append(region)
    sql += " ORDER BY score DESC, fetched_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [_row_to_article(r) for r in rows]


def get_markets() -> dict[str, list[dict[str, Any]]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT symbol, label, category, price, prev_close, change_pct, fetched_at FROM prices ORDER BY category, label"
        ).fetchall()
    finally:
        conn.close()
    out: dict[str, list[dict[str, Any]]] = {"commodity": [], "index": [], "fx": []}
    for r in rows:
        out.setdefault(r["category"], []).append({
            "symbol": r["symbol"],
            "label": r["label"],
            "price": r["price"],
            "prev_close": r["prev_close"],
            "change_pct": r["change_pct"],
            "fetched_at": r["fetched_at"],
        })
    return out


def get_weather() -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT city, lat, lon, temp_c, feels_c, humidity, wind_kph,
                      weather_code, summary, high_c, low_c, fetched_at
               FROM weather ORDER BY city"""
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def snapshot() -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "major_news": get_major_news(),
        "minor_news": get_minor_news(limit=30),
        "markets": get_markets(),
        "weather": get_weather(),
    }
