"""Seasons omitted from sync and the app season list."""
from __future__ import annotations

# League season numbers excluded (bad/incomplete v5 sheet data).
EXCLUDED_SEASON_NUMBERS: frozenset[int] = frozenset({2})


def is_season_excluded(season_number: int) -> bool:
    return int(season_number) in EXCLUDED_SEASON_NUMBERS
