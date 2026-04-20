"""Generic RSS/Atom fetcher. Normalizes feedparser output into article dicts."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser

log = logging.getLogger(__name__)

_USER_AGENT = "newsagg/0.1 (+https://example.com)"
_TIMEOUT = 15  # feedparser honors socket timeout


def _parse_date(entry: dict[str, Any]) -> str | None:
    """Return ISO8601 UTC string, or None if no parseable date."""
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if not val:
            continue
        try:
            dt = parsedate_to_datetime(val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct:
        try:
            return datetime.fromtimestamp(time.mktime(struct), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            pass
    return None


def _clean_summary(raw: str | None) -> str:
    if not raw:
        return ""
    import re
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500]


def fetch_rss(url: str, source_name: str) -> list[dict[str, Any]]:
    """Fetch an RSS/Atom feed and return normalized article dicts.

    Returned dict keys: url, title, summary, source, published_at (ISO8601 or None).
    Never raises — returns [] on failure. Logs the reason.
    """
    import socket
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(_TIMEOUT)
    try:
        parsed = feedparser.parse(url, agent=_USER_AGENT)
    except Exception as e:
        log.warning("feedparser raised on %s: %s", url, e)
        return []
    finally:
        socket.setdefaulttimeout(old_timeout)

    if parsed.bozo and not parsed.entries:
        log.warning("feed %s parse error: %s", url, getattr(parsed, "bozo_exception", "unknown"))
        return []

    out: list[dict[str, Any]] = []
    for entry in parsed.entries:
        link = entry.get("link") or ""
        title = (entry.get("title") or "").strip()
        if not link or not title:
            continue
        out.append({
            "url": link,
            "title": title,
            "summary": _clean_summary(entry.get("summary") or entry.get("description")),
            "source": source_name,
            "published_at": _parse_date(entry),
        })
    return out
