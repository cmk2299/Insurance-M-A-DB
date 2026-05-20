"""Trade-Press source definitions for the weekly sweep.

Each source defines a Nimble query template plus an expected-volume
estimate for monitoring. The {date_range} placeholder is rendered at
sweep time with something like ``after:2026-05-12``.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TradePressSource:
    name: str
    base_url: str
    nimble_query_template: str
    expected_weekly_volume: int


SOURCES: list[TradePressSource] = [
    TradePressSource(
        name="versicherungsmonitor",
        base_url="https://www.versicherungsmonitor.de",
        nimble_query_template=(
            'site:versicherungsmonitor.de '
            '("Versicherungsmakler" OR "Vermittler") '
            '("Übernahme" OR "Akquisition" OR "Konsolidierung") {date_range}'
        ),
        expected_weekly_volume=2,
    ),
    TradePressSource(
        name="vwheute",
        base_url="https://versicherungswirtschaft-heute.de",
        nimble_query_template=(
            'site:versicherungswirtschaft-heute.de '
            '(Makler OR Vermittler) (Übernahme OR Akquisition OR übernimmt) {date_range}'
        ),
        expected_weekly_volume=3,
    ),
    TradePressSource(
        name="asscompact_de",
        base_url="https://www.asscompact.de",
        nimble_query_template=(
            'site:asscompact.de Versicherungsmakler (Übernahme OR Konsolidierung OR Generationswechsel) {date_range}'
        ),
        expected_weekly_volume=2,
    ),
    TradePressSource(
        name="asscompact_at",
        base_url="https://www.asscompact.at",
        nimble_query_template=(
            'site:asscompact.at Versicherungsmakler (Übernahme OR Akquisition) {date_range}'
        ),
        expected_weekly_volume=1,
    ),
    TradePressSource(
        name="procontra",
        base_url="https://www.procontra-online.de",
        nimble_query_template=(
            'site:procontra-online.de (Makler OR Vermittler) (Übernahme OR Akquisition OR übernimmt) {date_range}'
        ),
        expected_weekly_volume=2,
    ),
    TradePressSource(
        name="versicherungsbote",
        base_url="https://www.versicherungsbote.de",
        nimble_query_template=(
            'site:versicherungsbote.de Versicherungsmakler (Übernahme OR Konsolidierung) {date_range}'
        ),
        expected_weekly_volume=1,
    ),
    TradePressSource(
        name="finanzwelt",
        base_url="https://www.finanzwelt.de",
        nimble_query_template=(
            'site:finanzwelt.de (Makler OR Vermittler) (Akquisition OR Übernahme) {date_range}'
        ),
        expected_weekly_volume=1,
    ),
    TradePressSource(
        name="cash_online",
        base_url="https://www.cash-online.de",
        nimble_query_template=(
            'site:cash-online.de Versicherungsmakler (Übernahme OR Akquisition) {date_range}'
        ),
        expected_weekly_volume=1,
    ),
]


def total_expected_weekly_volume() -> int:
    """Brutto-Schätzung über alle Quellen, vor Dedupe."""
    return sum(s.expected_weekly_volume for s in SOURCES)
