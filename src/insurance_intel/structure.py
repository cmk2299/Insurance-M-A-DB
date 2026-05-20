"""LLM-based structuring of trade-press articles into M&A events.

Sends an article (markdown) to Claude, expects JSON-array output matching
the schema documented in ``prompts/structure_event.txt``. Failures are
caught and returned as empty event lists rather than raising — a single
unparseable article should not bring down the whole sweep.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from anthropic import Anthropic

from insurance_intel.config import settings

log = logging.getLogger(__name__)


def _load_prompt() -> str:
    prompt_path = settings.repo_root / "prompts" / "structure_event.txt"
    return prompt_path.read_text(encoding="utf-8")


def _load_consolidators() -> str:
    """Returns the consolidators YAML as a string for inlining into the prompt."""
    cons_path = settings.repo_root / "consolidators.yaml"
    return cons_path.read_text(encoding="utf-8")


def _load_consolidators_dict() -> dict[str, Any]:
    cons_path = settings.repo_root / "consolidators.yaml"
    with cons_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


# Lazy-loaded module-level cache
_SYSTEM_PROMPT: str | None = None
_CONS_YAML: str | None = None


def _get_system_prompt() -> str:
    global _SYSTEM_PROMPT, _CONS_YAML
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = _load_prompt()
    if _CONS_YAML is None:
        _CONS_YAML = _load_consolidators()
    return f"{_SYSTEM_PROMPT}\n\n--- KNOWN CONSOLIDATORS ---\n{_CONS_YAML}"


def structure_article(
    *,
    markdown: str,
    source_publication: str,
    source_url: str,
    client: Anthropic | None = None,
) -> list[dict[str, Any]]:
    """Returns a list of M&A event dicts. Empty list = no events found
    or LLM failed (failures are logged, not raised).

    The returned dicts match the JSON schema in ``prompts/structure_event.txt``
    and the columns of the ``ma_events`` table in ``migrations/001_initial.sql``.
    Each event additionally carries ``source_url`` and ``source_publication``
    fields populated from the function arguments.
    """
    if client is None:
        client = Anthropic(api_key=settings.anthropic_api_key)

    system = _get_system_prompt()
    user = (
        f"SOURCE_PUBLICATION: {source_publication}\n"
        f"SOURCE_URL: {source_url}\n\n"
        f"--- ARTICLE MARKDOWN ---\n{markdown}"
    )

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.anthropic_max_output_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except Exception as exc:  # noqa: BLE001 — log and skip
        log.warning("Anthropic call failed for %s: %s", source_url, exc)
        return []

    if not response.content:
        log.warning("Empty response for %s", source_url)
        return []

    text = response.content[0].text.strip()
    # Strip code fences if model wraps despite instructions
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")

    try:
        events = json.loads(text)
    except json.JSONDecodeError:
        log.warning("Could not parse JSON for %s: %r", source_url, text[:200])
        return []

    if not isinstance(events, list):
        log.warning("LLM returned non-list for %s: %r", source_url, type(events))
        return []

    # Always populate source fields from caller args (don't trust LLM here)
    for event in events:
        event["source_url"] = source_url
        event["source_publication"] = source_publication

    return events
