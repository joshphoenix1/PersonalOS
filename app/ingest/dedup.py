"""Dedup helpers: stable URL hash + in-memory title-similarity check.

URL hash normalizes the URL (strip tracking params, lowercase host) so the
same story syndicated with ?utm_source=... variants collapses to one row.
Title similarity catches the same story at two different URLs (e.g. Reuters
direct + Reuters via Google News).
"""
from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ref_", "ref", "_hsenc", "_hsmi")


def normalize_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        # Force https and strip www so http/https + www variants collapse.
        netloc = p.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        # Filter tracking params.
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=False)
             if not any(k.lower().startswith(pref) for pref in _TRACKING_PREFIXES)]
        q.sort()
        return urlunparse(("https", netloc, p.path.rstrip("/"), "", urlencode(q), ""))
    except Exception:
        return url


def url_hash(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:32]


def _title_key(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def dedup_batch(items: list[dict], existing_url_hashes: set[str], existing_titles: list[str]) -> list[dict]:
    """Remove items whose URL hash or near-duplicate title already exists.

    In-batch dedup is also applied (two sources publishing the same headline in the same tick).
    """
    out: list[dict] = []
    seen_hashes: set[str] = set(existing_url_hashes)
    seen_titles: list[str] = list(existing_titles)

    for it in items:
        h = url_hash(it["url"])
        if h in seen_hashes:
            continue
        tk = _title_key(it["title"])
        if not tk:
            continue
        # near-duplicate title (ratio >= 0.9) against any already-seen title
        if any(SequenceMatcher(None, tk, t).ratio() >= 0.9 for t in seen_titles):
            continue
        it["url_hash"] = h
        out.append(it)
        seen_hashes.add(h)
        seen_titles.append(tk)
    return out
