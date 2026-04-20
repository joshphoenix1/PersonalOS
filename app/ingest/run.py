"""Ingest orchestrator: fetch all sources → dedup → classify → insert → mark major."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.db.init import get_conn, log_fetch, tx
from app.ingest.classify import classify
from app.ingest.dedup import dedup_batch
from app.ingest.sources import fetch_all

log = logging.getLogger(__name__)

MAJOR_BOX_SIZE = 5          # how many items get is_major=1 each cycle
MAJOR_SCORING_WINDOW_H = 24  # look back this far when picking top-scored majors


def _existing_keys() -> tuple[set[str], list[str]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT url_hash, title FROM articles WHERE fetched_at > ?",
            ((datetime.now(timezone.utc) - timedelta(hours=settings.article_retention_hours)).isoformat(),),
        ).fetchall()
    finally:
        conn.close()
    hashes = {r["url_hash"] for r in rows}
    titles = [r["title"].lower() for r in rows]
    return hashes, titles


def _insert(articles: list[dict]) -> int:
    if not articles:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for a in articles:
        rows.append((
            a["url_hash"], a["url"], a["title"], a.get("summary", ""),
            a["source"], float(a.get("source_weight", 0.5)),
            a.get("published_at"), now,
            a["region"], a["score"],
        ))
    with tx() as conn:
        cur = conn.executemany(
            """INSERT OR IGNORE INTO articles
               (url_hash, url, title, summary, source, source_weight, published_at, fetched_at, region, score)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        return cur.rowcount


def _refresh_major_flags() -> None:
    """Set is_major=1 on the top MAJOR_BOX_SIZE articles (excluding 'drop') from the
    last MAJOR_SCORING_WINDOW_H hours. Articles already marked major stay marked
    (stickiness handled at query time via fetched_at window)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=MAJOR_SCORING_WINDOW_H)).isoformat()
    with tx() as conn:
        top_rows = conn.execute(
            """SELECT id FROM articles
               WHERE region != 'drop' AND fetched_at > ?
               ORDER BY score DESC, fetched_at DESC
               LIMIT ?""",
            (cutoff, MAJOR_BOX_SIZE),
        ).fetchall()
        top_ids = [r["id"] for r in top_rows]
        if top_ids:
            q_marks = ",".join("?" * len(top_ids))
            conn.execute(f"UPDATE articles SET is_major=1 WHERE id IN ({q_marks})", top_ids)


def run_ingest() -> dict:
    """One ingest cycle. Safe to call on schedule."""
    fetched_at_iso = datetime.now(timezone.utc).isoformat()
    try:
        raw = fetch_all()
        log.info("fetched %d raw items from all sources", len(raw))

        for a in raw:
            a["fetched_at"] = fetched_at_iso

        existing_hashes, existing_titles = _existing_keys()
        deduped = dedup_batch(raw, existing_hashes, existing_titles)
        log.info("%d new after dedup", len(deduped))

        kept = []
        for a in deduped:
            region, score = classify(a)
            if region == "drop":
                continue
            a["region"] = region
            a["score"] = score
            kept.append(a)
        log.info("%d after classifier drops", len(kept))

        _insert(kept)
        _refresh_major_flags()

        log_fetch("ingest", "ok", f"raw={len(raw)} new={len(deduped)} kept={len(kept)}", len(kept))
        return {"raw": len(raw), "new": len(deduped), "kept": len(kept)}
    except Exception as e:
        log.exception("run_ingest failed")
        log_fetch("ingest", "error", str(e))
        raise


if __name__ == "__main__":
    logging.basicConfig(level=settings.log_level)
    print(run_ingest())
