"""Weather fetcher: Open-Meteo. No API key, no rate-limit for civil use."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import WEATHER_CITIES
from app.db.init import log_fetch, tx

log = logging.getLogger(__name__)

API = "https://api.open-meteo.com/v1/forecast"

# WMO weather code → short label (subset used).
WMO = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Rain showers", 81: "Rain showers", 82: "Violent rain",
    95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Severe thunderstorm",
}


def _fetch_one(client: httpx.Client, name: str, lat: float, lon: float) -> dict | None:
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto",
        "forecast_days": 1,
        "wind_speed_unit": "kmh",
    }
    try:
        r = client.get(API, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("open-meteo failed for %s: %s", name, e)
        return None

    cur = data.get("current", {})
    daily = data.get("daily", {})
    code = int(cur.get("weather_code", -1)) if cur.get("weather_code") is not None else None
    high = low = None
    try:
        high = float(daily.get("temperature_2m_max", [None])[0])
        low = float(daily.get("temperature_2m_min", [None])[0])
    except (TypeError, IndexError, ValueError):
        pass
    return {
        "temp_c": cur.get("temperature_2m"),
        "feels_c": cur.get("apparent_temperature"),
        "humidity": cur.get("relative_humidity_2m"),
        "wind_kph": cur.get("wind_speed_10m"),
        "weather_code": code,
        "summary": WMO.get(code or -1, "Unknown"),
        "high_c": high,
        "low_c": low,
    }


def fetch_weather() -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    rows: list[tuple] = []
    misses: list[str] = []
    with httpx.Client() as client:
        for name, lat, lon in WEATHER_CITIES:
            r = _fetch_one(client, name, lat, lon)
            if r is None:
                misses.append(name)
                continue
            rows.append((
                name, lat, lon, r["temp_c"], r["feels_c"], r["humidity"], r["wind_kph"],
                r["weather_code"], r["summary"], r["high_c"], r["low_c"], now_iso,
            ))

    with tx() as conn:
        conn.executemany(
            """INSERT INTO weather
                 (city, lat, lon, temp_c, feels_c, humidity, wind_kph, weather_code, summary, high_c, low_c, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(city) DO UPDATE SET
                 lat=excluded.lat, lon=excluded.lon,
                 temp_c=excluded.temp_c, feels_c=excluded.feels_c,
                 humidity=excluded.humidity, wind_kph=excluded.wind_kph,
                 weather_code=excluded.weather_code, summary=excluded.summary,
                 high_c=excluded.high_c, low_c=excluded.low_c,
                 fetched_at=excluded.fetched_at""",
            rows,
        )

    log_fetch("weather", "ok", f"hit={len(rows)} miss={len(misses)}", len(rows))
    return {"hit": len(rows), "miss": len(misses), "missing": misses}


if __name__ == "__main__":
    import logging as _l
    _l.basicConfig(level=_l.INFO)
    print(fetch_weather())
