"""Renderers for Markdown weekly digest and Slack-flavoured short digest.

Both consume the events list returned by ``persist.events_for_run``.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

PRIORITY_LABELS = {
    1: "P1 Direkte M&A-Events",
    2: "P2 Governance-Events",
    3: "P3 PE-Sponsor-Aktivität",
    4: "P4 Markt-Aggregate",
    5: "P5 Finanz-/Stammdaten",
}


def _group_by_priority(events: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        prio = event.get("signal_priority") or 1
        groups[prio].append(event)
    return groups


def _fmt_event_line(event: dict[str, Any]) -> str:
    date = event.get("event_date") or "n/a"
    buyer = event.get("buyer_name") or "?"
    seller = event.get("seller_name") or "?"
    value = event.get("transaction_value_eur") or "undisclosed"
    pub = event.get("source_publication") or "?"
    url = event.get("source_url") or "#"
    region = event.get("region") or ""
    region_str = f" · {region}" if region else ""
    return f"- **{date}** · {buyer} → {seller} · {value}{region_str} · [{pub}]({url})"


def render_markdown_report(
    *,
    run_id: int,
    run_started_at: datetime,
    events: list[dict[str, Any]],
    sources_stats: dict[str, dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
) -> str:
    iso_week = run_started_at.isocalendar()
    week_label = f"{iso_week.year}-W{iso_week.week:02d}"
    groups = _group_by_priority(events)

    p1_events = groups.get(1, [])
    tldr_lines = []
    tldr_lines.append(
        f"{len(events)} M&A-Signal{'e' if len(events) != 1 else ''} in dieser Woche "
        f"({len(p1_events)} direkte Deals)."
    )
    if p1_events:
        tldr_lines.append(
            "Top P1: "
            + ", ".join(
                f"{e.get('buyer_name', '?')} → {e.get('seller_name', '?')[:40]}"
                for e in p1_events[:3]
            )
            + "."
        )

    lines: list[str] = []
    lines.append(f"# Insurance-Intel Loop — Run {week_label} / {run_started_at:%Y-%m-%d}")
    lines.append("")
    lines.append("## TL;DR")
    lines.extend(tldr_lines)
    lines.append("")

    for prio in (1, 2, 3, 4, 5):
        rows = groups.get(prio, [])
        lines.append(f"## {PRIORITY_LABELS[prio]} ({len(rows)})")
        if rows:
            for ev in rows:
                lines.append(_fmt_event_line(ev))
        else:
            lines.append("- _keine_")
        lines.append("")

    if sources_stats:
        lines.append("## Quellen-Stats")
        lines.append("")
        lines.append("| Quelle | Hits | Status |")
        lines.append("|--------|------|--------|")
        for src_name, stats in sources_stats.items():
            lines.append(
                f"| {src_name} | {stats.get('hits', 0)} | {stats.get('status', 'ok')} |"
            )
        lines.append("")

    low_conf = [e for e in events if (e.get("llm_confidence") or 1.0) < 0.6]
    lines.append("## Anomalien / Datenqualität")
    if low_conf:
        for ev in low_conf:
            lines.append(
                f"- ⚠️  llm_confidence={ev.get('llm_confidence'):.2f} for "
                f"{ev.get('buyer_name')} → {ev.get('seller_name')} ({ev.get('source_url')})"
            )
    else:
        lines.append("- keine Auffälligkeiten in diesem Run.")
    lines.append("")

    if summary:
        lines.append("---")
        lines.append("")
        lines.append("**Run-Meta**")
        lines.append(
            f"- run_id={summary.get('run_id')} · "
            f"status={summary.get('status')} · "
            f"sources_attempted={summary.get('sources_attempted')} · "
            f"sources_failed={summary.get('sources_failed')}"
        )

    return "\n".join(lines) + "\n"

