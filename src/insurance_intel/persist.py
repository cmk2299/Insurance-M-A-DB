"""Postgres persistence layer.

Thin wrapper over psycopg with three concerns:
  * begin_run / end_run lifecycle
  * insert_hit with content_hash dedupe
  * insert_event linked to a hit_id

Connections are short-lived and opened per logical batch.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

import psycopg

from insurance_intel.config import settings

log = logging.getLogger(__name__)


def normalize_for_hash(text: str) -> str:
    """Whitespace-collapse + lowercase before hashing.

    Same article fetched twice should produce the same hash even if
    whitespace differs slightly.
    """
    return re.sub(r"\s+", " ", text.lower()).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_for_hash(text).encode("utf-8")).hexdigest()


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(settings.postgres_dsn) as conn:
        yield conn


def begin_run() -> int:
    """Insert a 'running' loop_runs row, return its id."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO loop_runs (status) VALUES ('running') RETURNING id"
        )
        row = cur.fetchone()
        conn.commit()
        assert row is not None
        return int(row[0])


def end_run(
    run_id: int,
    *,
    status: str,
    events_added: int,
    events_skipped_dupe: int,
    sources_attempted: int,
    sources_failed: int,
    notes: str | None = None,
) -> None:
    assert status in {"succeeded", "failed", "partial"}
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE loop_runs
               SET finished_at = now(),
                   status = %s,
                   events_added = %s,
                   events_skipped_dupe = %s,
                   sources_attempted = %s,
                   sources_failed = %s,
                   notes = %s
             WHERE id = %s
            """,
            (status, events_added, events_skipped_dupe, sources_attempted, sources_failed, notes, run_id),
        )
        conn.commit()


def last_successful_run_finished_at() -> datetime | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT finished_at FROM loop_runs
             WHERE status IN ('succeeded','partial')
               AND finished_at IS NOT NULL
             ORDER BY finished_at DESC
             LIMIT 1
            """
        )
        row = cur.fetchone()
        if row is None:
            return None
        return row[0]


def try_insert_hit(
    *,
    run_id: int,
    source: str,
    url: str,
    title: str | None,
    snippet: str | None,
    raw_markdown: str,
) -> int | None:
    """Insert a hit, return its id. Return None if content_hash collision (dedupe)."""
    chash = content_hash(raw_markdown)
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.execute(
                """
                INSERT INTO trade_press_hits
                  (run_id, source, url, title, snippet, content_hash, raw_markdown)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (run_id, source, url, title, snippet, chash, raw_markdown),
            )
            row = cur.fetchone()
            conn.commit()
            assert row is not None
            return int(row[0])
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            return None


def insert_event(hit_id: int, event: dict[str, Any]) -> None:
    """Insert an LLM-structured event linked to a trade_press_hits row."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ma_events (
              hit_id, event_date, buyer_name, buyer_consolidator_id, seller_name,
              deal_type, transaction_value_eur, segment, region,
              source_url, source_publication, data_quality, signal_priority,
              llm_confidence, raw_llm_output
            )
            VALUES (
              %s, %s, %s, %s, %s,
              %s, %s, %s, %s,
              %s, %s, %s, %s,
              %s, %s
            )
            """,
            (
                hit_id,
                event.get("event_date"),
                event.get("buyer_name"),
                event.get("buyer_consolidator_id"),
                event.get("seller_name"),
                event.get("deal_type"),
                event.get("transaction_value_eur"),
                event.get("segment"),
                event.get("region"),
                event["source_url"],
                event["source_publication"],
                event.get("data_quality", "hypothesis-pending-review"),
                event.get("signal_priority", 1),
                event.get("llm_confidence"),
                json.dumps(event),
            ),
        )
        conn.commit()


def events_for_run(run_id: int) -> list[dict[str, Any]]:
    """Fetch all events for a given run_id, for digest rendering."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              e.event_date, e.buyer_name, e.buyer_consolidator_id,
              e.seller_name, e.deal_type, e.transaction_value_eur,
              e.segment, e.region, e.signal_priority, e.data_quality,
              e.llm_confidence, e.source_url, e.source_publication
            FROM ma_events e
            JOIN trade_press_hits h ON h.id = e.hit_id
            WHERE h.run_id = %s
            ORDER BY e.signal_priority ASC, e.event_date DESC NULLS LAST
            """,
            (run_id,),
        )
        cols = [d.name for d in cur.description or []]
        return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]
