"""Google News RSS fetcher — used for sources without public RSS (Reuters, Bloomberg).

Google News wraps the real article URL in its own redirect. We parse the 'url' query
param when we can, otherwise the direct link is still functional (it 302s through
news.google.com). Upstream source identity is preserved via the configured name.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.ingest.rss import fetch_rss

log = logging.getLogger(__name__)


def _unwrap(url: str) -> str:
    """Best-effort: unwrap google news redirects of the form news.google.com/articles/...?url=..."""
    try:
        parsed = urlparse(url)
        if "news.google.com" not in parsed.netloc:
            return url
        qs = parse_qs(parsed.query)
        if "url" in qs and qs["url"]:
            return qs["url"][0]
    except Exception:
        pass
    return url


def fetch_google_news(query_url: str, source_name: str) -> list[dict[str, Any]]:
    """Fetch a Google News RSS URL and normalize like rss.fetch_rss."""
    items = fetch_rss(query_url, source_name)
    for it in items:
        it["url"] = _unwrap(it["url"])
    return items
