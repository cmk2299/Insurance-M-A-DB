"""ntfy.sh notifier — POSTs a short digest to a topic URL.

Topic URL examples:
  https://ntfy.sh/cmk-insurance-intel        (public ntfy.sh)
  https://ntfy.example.com/insurance-intel   (self-hosted)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from insurance_intel.config import settings

log = logging.getLogger(__name__)


def render_ntfy_body(*, week_label: str, events: list[dict[str, Any]]) -> tuple[str, str]:
    """Returns (title, body) for the ntfy notification."""
    p1 = [e for e in events if e.get("signal_priority") == 1]
    p2 = sum(1 for e in events if e.get("signal_priority") == 2)
    p3 = sum(1 for e in events if e.get("signal_priority") == 3)

    # HTTP headers must be ASCII — no en-dash, em-dash, or middle dot.
    title = f"Insurance-Intel {week_label} - {len(events)} Signale ({len(p1)} P1)"

    lines: list[str] = [f"{len(events)} Signale · {len(p1)} P1 / {p2} P2 / {p3} P3", ""]
    for e in p1[:5]:
        buyer = e.get("buyer_name") or "?"
        seller = (e.get("seller_name") or "?")[:50]
        lines.append(f"• {buyer} → {seller}")
    if len(p1) > 5:
        lines.append(f"… und {len(p1) - 5} weitere P1-Deals")
    if not p1:
        lines.append("keine direkten Deals in diesem Run")

    return title, "\n".join(lines)


def post_digest(*, week_label: str, events: list[dict[str, Any]]) -> bool:
    """POST a digest to the configured ntfy topic. Returns success bool."""
    title, body = render_ntfy_body(week_label=week_label, events=events)
    headers = {
        "Title": title,
        "Priority": "default",
        "Tags": "office,chart_with_upwards_trend",
    }
    try:
        resp = httpx.post(
            settings.ntfy_topic_url, content=body.encode("utf-8"), headers=headers, timeout=15.0
        )
        if resp.status_code >= 300:
            log.warning("ntfy returned %s: %s", resp.status_code, resp.text[:200])
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — notification must never crash the loop
        log.warning("ntfy POST failed: %s", exc)
        return False
