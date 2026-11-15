"""Admin matchup override upsert helpers."""

from db.matchup_override_writes import (
    format_series_code,
    inverse_series_code,
    parse_series_code,
)
from league_admin import parse_matchup_overrides_payload


def test_parse_and_format_series_codes():
    assert parse_series_code("3-2") == (3, 2, 0)
    assert parse_series_code("2-2-1") == (2, 2, 1)
    assert format_series_code(3, 2) == "3-2"
    assert format_series_code(2, 2, 1) == "2-2-1"
    assert inverse_series_code("3-2") == "2-3"
    assert inverse_series_code("2-2-1") == "2-2-1"


def test_parse_matchup_overrides_payload():
    assert parse_matchup_overrides_payload({}) == {}
    assert parse_matchup_overrides_payload(
        {"matchup_overrides": {"Team A": "3-2", "Team B": "", "Team C": None}}
    ) == {"Team A": "3-2", "Team B": None, "Team C": None}
