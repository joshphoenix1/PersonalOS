"""Region bucket + importance score for each article.

Score = source_weight × region_multiplier × (1 + keyword_hits) × recency_factor.
Region is the highest-scoring bucket by keyword hits, falling back to source_region.
Articles that fall into the 'drop' bucket (Ukraine/entertainment/etc) are flagged
with region='drop' and score=0 so the orchestrator can skip them.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import KEYWORDS, REGION_WEIGHTS


def _keyword_score(text: str, bucket: str) -> float:
    kws = KEYWORDS.get(bucket, {})
    return sum(weight for kw, weight in kws.items() if kw in text)


def _recency_factor(published_at: str | None, fetched_at: str) -> float:
    """1.0 for fresh (<1h), decays to 0.4 over 24h."""
    ref_str = published_at or fetched_at
    try:
        ref = datetime.fromisoformat(ref_str.replace("Z", "+00:00"))
    except Exception:
        return 0.6
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    age_h = (datetime.now(timezone.utc) - ref).total_seconds() / 3600
    if age_h <= 1:
        return 1.0
    if age_h >= 24:
        return 0.4
    # linear decay 1.0 → 0.4 across 1–24h
    return 1.0 - (age_h - 1) * (0.6 / 23)


def classify(article: dict[str, Any]) -> tuple[str, float]:
    """Returns (region_bucket, score). Mutates nothing.

    Regions: gulf | iran_war | oil_markets | markets_macro | global | drop.
    """
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()

    drop_score = _keyword_score(text, "drop")  # negative or zero

    bucket_scores = {
        "gulf":          _keyword_score(text, "gulf"),
        "iran_war":      _keyword_score(text, "iran_war"),
        "oil_markets":   _keyword_score(text, "oil_markets"),
        "markets_macro": _keyword_score(text, "markets_macro"),
    }

    # Ukraine/Russia: only drop if NOT accompanied by oil/markets relevance.
    if drop_score < 0 and bucket_scores["oil_markets"] < 1.0:
        return "drop", 0.0

    best_bucket = max(bucket_scores, key=bucket_scores.get)
    best_hits = bucket_scores[best_bucket]

    if best_hits <= 0:
        # No bucket hits: fall back to source-declared region.
        src_region = article.get("source_region", "global")
        region = "gulf" if src_region == "gulf" else "global"
    else:
        region = best_bucket

    region_mult = REGION_WEIGHTS.get(region, 0.7)
    source_weight = float(article.get("source_weight", 0.5))
    recency = _recency_factor(article.get("published_at"), article.get("fetched_at", ""))
    score = source_weight * region_mult * (1 + best_hits) * recency

    # Any drop_score penalty still applies (softly) even if oil-adjacent kept it in.
    score = max(0.0, score + drop_score * 0.3)

    return region, round(score, 4)
