"""Per-source fetch orchestrator.

For each Trade-Press source:
  1. Render the Nimble query with the appropriate {date_range}.
  2. Call ``nimble search`` to get URLs.
  3. Call ``nimble extract`` for each URL to get article markdown.
  4. Dedupe via content_hash, persist to trade_press_hits.
  5. Run the LLM structurer over each new hit, persist ma_events.

Rate-limit: explicit 1 request/second between source-level calls, even if
the underlying CLI is faster. Trade-Press sites have no formal anti-bot
clause, but staying polite avoids triggering ad-hoc rate limiters.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from datetime import datetime, timedelta
from typing import Any

from anthropic import Anthropic

from insurance_intel.config import settings
from insurance_intel.persist import (
    begin_run,
    end_run,
    insert_event,
    last_successful_run_finished_at,
    try_insert_hit,
)
from insurance_intel.sources import SOURCES, TradePressSource
from insurance_intel.structure import structure_article

log = logging.getLogger(__name__)


def _date_range_string() -> str:
    last = last_successful_run_finished_at()
    if last is None:
        cutoff = datetime.utcnow() - timedelta(days=settings.coldstart_lookback_days)
    else:
        cutoff = last
    # Nimble search supports `after:YYYY-MM-DD` as a Google-style operator
    return f"after:{cutoff.strftime('%Y-%m-%d')}"


def _run_nimble_search(query: str, max_results: int) -> list[dict[str, Any]]:
    """Returns Nimble search results as a list of {title, url, description, ...} dicts."""
    proc = subprocess.run(
        [settings.nimble_bin, "search", "--query", query, "--max-results", str(max_results)],
        capture_output=True,
        text=True,
        timeout=60,
        env={**__import__("os").environ, "NIMBLE_API_KEY": settings.nimble_api_key},
    )
    if proc.returncode != 0:
        log.warning("Nimble search failed: %s", proc.stderr.strip())
        return []
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        log.warning("Nimble search returned non-JSON: %r", proc.stdout[:200])
        return []
    return payload.get("results", []) if isinstance(payload, dict) else []


def _run_nimble_extract(url: str) -> str | None:
    """Returns extracted markdown for the URL, or None on failure."""
    proc = subprocess.run(
        [
            settings.nimble_bin,
            "--transform",
            "data.markdown",
            "extract",
            "--url",
            url,
            "--format",
            "markdown",
        ],
        capture_output=True,
        text=True,
        timeout=90,
        env={**__import__("os").environ, "NIMBLE_API_KEY": settings.nimble_api_key},
    )
    if proc.returncode != 0:
        log.warning("Nimble extract failed for %s: %s", url, proc.stderr.strip())
        return None
    out = proc.stdout.strip()
    # CLI wraps the markdown in JSON quotes when --transform is used
    if out.startswith('"') and out.endswith('"'):
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return out.strip('"')
    return out


def _process_source(
    *,
    source: TradePressSource,
    run_id: int,
    date_range: str,
    anthropic_client: Anthropic,
) -> tuple[int, int]:
    """Process one source, return (events_added, hits_skipped_dupe)."""
    query = source.nimble_query_template.format(date_range=date_range)
    log.info("[%s] query=%s", source.name, query)
    results = _run_nimble_search(query, settings.nimble_max_results)
    events_added = 0
    hits_skipped = 0

    for result in results:
        url = result.get("url")
        if not url or not url.startswith("http"):
            continue
        title = result.get("title")
        snippet = result.get("description") or result.get("snippet")

        time.sleep(1.0)  # polite rate-limit per source
        markdown = _run_nimble_extract(url)
        if markdown is None or len(markdown) < 200:
            log.info("[%s] skipped %s — too short or extract failed", source.name, url)
            continue

        hit_id = try_insert_hit(
            run_id=run_id,
            source=source.name,
            url=url,
            title=title,
            snippet=snippet,
            raw_markdown=markdown,
        )
        if hit_id is None:
            hits_skipped += 1
            continue

        events = structure_article(
            markdown=markdown,
            source_publication=source.name,
            source_url=url,
            client=anthropic_client,
        )
        for event in events:
            insert_event(hit_id, event)
            events_added += 1

    return events_added, hits_skipped


def run_sweep() -> dict[str, Any]:
    """Top-level entry point. Returns a result summary dict."""
    run_id = begin_run()
    date_range = _date_range_string()
    log.info("Starting run %s with date_range=%s", run_id, date_range)

    anthropic_client = Anthropic(api_key=settings.anthropic_api_key)

    total_events = 0
    total_skipped = 0
    sources_failed = 0
    failures: list[str] = []

    for source in SOURCES:
        try:
            added, skipped = _process_source(
                source=source,
                run_id=run_id,
                date_range=date_range,
                anthropic_client=anthropic_client,
            )
            total_events += added
            total_skipped += skipped
        except Exception as exc:  # noqa: BLE001
            log.exception("Source %s failed", source.name)
            sources_failed += 1
            failures.append(f"{source.name}: {exc}")

    # Status determination
    if sources_failed >= 3:
        status = "failed"
    elif sources_failed > 0:
        status = "partial"
    elif total_events < settings.min_events_for_success:
        status = "partial"
    else:
        status = "succeeded"

    notes = "; ".join(failures) if failures else None

    end_run(
        run_id,
        status=status,
        events_added=total_events,
        events_skipped_dupe=total_skipped,
        sources_attempted=len(SOURCES),
        sources_failed=sources_failed,
        notes=notes,
    )

    return {
        "run_id": run_id,
        "status": status,
        "events_added": total_events,
        "events_skipped_dupe": total_skipped,
        "sources_attempted": len(SOURCES),
        "sources_failed": sources_failed,
        "date_range": date_range,
    }
