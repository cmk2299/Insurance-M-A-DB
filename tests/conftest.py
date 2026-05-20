"""Pytest fixtures shared across tests."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_mrh_trowe_nov2025() -> str:
    """Synthesized Trade-Press-style article covering MRH Trowe Nov 2025 four-deals."""
    return (FIXTURES_DIR / "mrh_trowe_nov2025.md").read_text(encoding="utf-8")


@pytest.fixture
def fixture_helmsauer_konermann() -> str:
    """Single-deal Helmsauer-Übernahme-Style article."""
    return (FIXTURES_DIR / "helmsauer_konermann.md").read_text(encoding="utf-8")


@pytest.fixture
def fixture_no_event() -> str:
    """Generic article with no M&A content — should produce empty event list."""
    return (FIXTURES_DIR / "no_event_article.md").read_text(encoding="utf-8")
