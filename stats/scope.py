"""Season/week scoping for stats queries.

A ``Scope`` describes which fact rows a query covers and how they should be
aggregated. Positions are ``(season_number, week)`` tuples, which sort
lexicographically: ``seasons.number`` is unique and aligned with ``seasons.id``
(migration 004), so ``(season, week)`` is a stable global ordering key.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from utils import safe_int

Position = Tuple[int, int]

# How to combine games spread over more than one season.
MODE_SEASON = "season"  # average the per-season averages
MODE_CAREER = "career"  # every game the player has ever bowled, range ignored
MODE_RANGE = "range"  # pool every game inside the range into one mean
MODES = (MODE_SEASON, MODE_CAREER, MODE_RANGE)

# Which half of the schedule counts.
PLAYOFFS_REGULAR = "regular"  # regular season only
PLAYOFFS_BOTH = "both"
PLAYOFFS_ONLY = "only"  # playoff weeks only
PLAYOFF_MODES = (PLAYOFFS_REGULAR, PLAYOFFS_BOTH, PLAYOFFS_ONLY)


def fact_position(fact: dict) -> Position:
    """``(season_number, week)`` for a fact row, for range comparisons and sorting."""
    return (safe_int(fact.get("season_number"), 0), safe_int(fact.get("week"), 0))


def parse_position(raw: Optional[str]) -> Optional[Position]:
    """Parse ``"14.3"`` (season 14, week 3) into a position. ``None`` when unparseable."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if "." in text:
        season_txt, week_txt = text.split(".", 1)
    else:
        season_txt, week_txt = text, "1"
    season = safe_int(season_txt, 0)
    week = safe_int(week_txt, 0)
    if season < 1 or week < 1:
        return None
    return (season, week)


def format_position(pos: Optional[Position]) -> Optional[str]:
    """Inverse of :func:`parse_position`."""
    if pos is None:
        return None
    return f"{pos[0]}.{pos[1]}"


@dataclass(frozen=True)
class Scope:
    """A window of play plus the aggregation mode to apply over it.

    ``start``/``end`` are inclusive. ``None`` means unbounded on that side, so a
    scope with both unset covers every fact row.
    """

    start: Optional[Position] = None
    end: Optional[Position] = None
    mode: str = MODE_RANGE
    playoffs: str = PLAYOFFS_BOTH

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"unknown scope mode {self.mode!r}; expected one of {MODES}")
        if self.playoffs not in PLAYOFF_MODES:
            raise ValueError(
                f"unknown playoffs filter {self.playoffs!r}; "
                f"expected one of {PLAYOFF_MODES}"
            )

    @classmethod
    def for_season(cls, season_num: int, **kwargs) -> "Scope":
        """Whole-season scope, used to express today's single-season queries."""
        return cls(start=(season_num, 1), end=(season_num, 10**6), **kwargs)

    @classmethod
    def career(cls, **kwargs) -> "Scope":
        kwargs.setdefault("mode", MODE_CAREER)
        return cls(start=None, end=None, **kwargs)

    @property
    def bounds_apply(self) -> bool:
        """Career mode spans a player's whole history, so range bounds are ignored."""
        return self.mode != MODE_CAREER

    @property
    def is_unbounded(self) -> bool:
        return not self.bounds_apply or (self.start is None and self.end is None)

    @property
    def season_span(self) -> Optional[Tuple[int, int]]:
        """``(first_season, last_season)`` covered, or ``None`` when unbounded."""
        if not self.bounds_apply or self.start is None or self.end is None:
            return None
        return (self.start[0], self.end[0])

    @property
    def single_season(self) -> Optional[int]:
        """The season number when this scope sits inside one season, else ``None``.

        PAR is only defined relative to a season (prior-season baseline plus a
        year-to-date average), so callers use this to decide whether to show it.
        """
        span = self.season_span
        if span is None or span[0] != span[1]:
            return None
        return span[0]

    def season_ytd_complete(self, facts: Iterable[dict]) -> bool:
        """True when this scope covers one season from week 1 through latest played week.

        Used to gate the "if absent" projection, which only makes sense over a
        full year-to-date window rather than a partial range or single week.
        """
        if not self.bounds_apply or self.single_season is None:
            return False
        season_num = self.single_season
        if self.start != (season_num, 1):
            return False
        latest_week = 0
        for f in facts:
            if safe_int(f.get("season_number"), 0) != season_num:
                continue
            wk = safe_int(f.get("week"), 0)
            if wk > latest_week:
                latest_week = wk
        if latest_week < 1:
            return False
        if self.end is None:
            return True
        if self.end[0] > season_num:
            return True
        return self.end[1] >= latest_week

    def contains(self, fact: dict) -> bool:
        """Whether a fact row falls inside this scope."""
        # Ahead of the is_unbounded check below, so the playoff filter applies
        # to career and unbounded scopes too.
        is_playoff = bool(fact.get("playoffs"))
        if self.playoffs == PLAYOFFS_REGULAR and is_playoff:
            return False
        if self.playoffs == PLAYOFFS_ONLY and not is_playoff:
            return False
        if self.is_unbounded:
            return True
        pos = fact_position(fact)
        if pos[1] < 1:
            return False
        if self.start is not None and pos < self.start:
            return False
        if self.end is not None and pos > self.end:
            return False
        return True
