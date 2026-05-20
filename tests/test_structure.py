"""Integration tests for structure.structure_article.

These hit the real Anthropic API and are skipped if ANTHROPIC_API_KEY is unset.
Use sparingly — they cost money. Mark as 'live' to run only when explicitly requested:

    pytest -m live tests/test_structure.py
"""

from __future__ import annotations

import os

import pytest

from insurance_intel.structure import structure_article

pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"), reason="No ANTHROPIC_API_KEY in env"
)


@pytest.mark.live
def test_mrh_trowe_nov2025_yields_four_p1_events(fixture_mrh_trowe_nov2025: str):
    events = structure_article(
        markdown=fixture_mrh_trowe_nov2025,
        source_publication="cash_online",
        source_url="https://www.cash-online.de/fixture/mrh-trowe-nov-2025",
    )
    p1 = [e for e in events if e.get("signal_priority") == 1]
    # Article has 4 distinct deals — we expect the LLM to identify all of them.
    assert len(p1) == 4, f"Expected 4 P1 events, got {len(p1)}: {events!r}"
    # All four should match MRH Trowe as buyer.
    assert all(e.get("buyer_consolidator_id") == "mrh-trowe" for e in p1)
    # Eurass case should be flagged with Generationswechsel.
    eurass = [e for e in p1 if "Eurass" in (e.get("seller_name") or "")]
    assert len(eurass) == 1
    assert "Generationswechsel" in (eurass[0].get("deal_type") or "") or eurass[0].get("deal_type")


@pytest.mark.live
def test_helmsauer_konermann_single_p1(fixture_helmsauer_konermann: str):
    events = structure_article(
        markdown=fixture_helmsauer_konermann,
        source_publication="vwheute",
        source_url="https://versicherungswirtschaft-heute.de/fixture/helmsauer-konermann",
    )
    p1 = [e for e in events if e.get("signal_priority") == 1]
    assert len(p1) == 1
    ev = p1[0]
    assert ev.get("buyer_consolidator_id") == "helmsauer"
    assert "Konermann" in (ev.get("seller_name") or "")


@pytest.mark.live
def test_no_event_article_yields_empty(fixture_no_event: str):
    events = structure_article(
        markdown=fixture_no_event,
        source_publication="asscompact_de",
        source_url="https://www.asscompact.de/fixture/no-event",
    )
    # Either truly empty, or low-priority aggregate-reference at most.
    p1 = [e for e in events if e.get("signal_priority") == 1]
    assert len(p1) == 0
