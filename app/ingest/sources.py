"""Dispatches each configured Source to the correct fetcher and returns merged results."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.config import SOURCES, Source
from app.ingest.google_news import fetch_google_news
from app.ingest.rss import fetch_rss

log = logging.getLogger(__name__)


def _fetch_one(source: Source) -> list[dict[str, Any]]:
    if source.fetcher == "rss":
        items = fetch_rss(source.url, source.name)
    elif source.fetcher == "google_news":
        items = fetch_google_news(source.url, source.name)
    else:
        log.error("unknown fetcher %s for %s", source.fetcher, source.name)
        return []
    for it in items:
        it["source_weight"] = source.weight
        it["source_region"] = source.region
    return items


def fetch_all() -> list[dict[str, Any]]:
    """Fetch every whitelisted source in parallel. Returns flat list of normalized articles."""
    all_items: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(_fetch_one, s): s for s in SOURCES}
        for fut in as_completed(futs):
            src = futs[fut]
            try:
                items = fut.result()
                log.info("fetched %d from %s", len(items), src.name)
                all_items.extend(items)
            except Exception as e:
                log.warning("fetch failed for %s: %s", src.name, e)
    return all_items
