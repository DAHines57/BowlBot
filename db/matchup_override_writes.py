"""Upsert / delete matchup_overrides for admin week entry."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.models import MatchupOverride, Season
from db.sync import _get_or_create_season


def parse_series_code(code: str) -> Tuple[int, int, int]:
    """Parse '3-2' or '2-2-1' into wins, losses, ties."""
    raw = str(code or "").strip()
    if not raw:
        raise ValueError("Empty series code.")
    parts = raw.split("-")
    if len(parts) == 2:
        wins, losses = int(parts[0]), int(parts[1])
        return wins, losses, 0
    if len(parts) == 3:
        return int(parts[0]), int(parts[1]), int(parts[2])
    raise ValueError(f"Invalid series code: {code!r}")


def format_series_code(wins: int, losses: int, ties: int = 0) -> str:
    if ties:
        return f"{int(wins)}-{int(losses)}-{int(ties)}"
    return f"{int(wins)}-{int(losses)}"


def inverse_series_code(code: str) -> str:
    wins, losses, ties = parse_series_code(code)
    return format_series_code(losses, wins, ties)


def overrides_for_week(
    session: Session, season_number: int, week: int
) -> List[dict]:
    season = session.scalar(select(Season).where(Season.number == season_number))
    if season is None:
        return []
    rows = session.scalars(
        select(MatchupOverride).where(
            MatchupOverride.season_id == season.id,
            MatchupOverride.week == week,
        )
    ).all()
    out: List[dict] = []
    for mo in rows:
        out.append(
            {
                "team": mo.team,
                "opponent": mo.opponent,
                "wins": int(mo.wins),
                "losses": int(mo.losses),
                "ties": int(mo.ties),
                "playoffs": bool(mo.playoffs),
                "code": format_series_code(mo.wins, mo.losses, mo.ties),
            }
        )
    return out


def sync_week_matchup_overrides(
    session: Session,
    season_number: int,
    week: int,
    overrides: Dict[str, Optional[str]],
    *,
    team_opponents: Optional[Dict[str, str]] = None,
    playoffs: bool = False,
    sheet_key: Optional[str] = None,
) -> int:
    """Apply series overrides for the teams present in ``overrides``.

    Empty / None values clear that team's override for the week. A non-empty
    code upserts the team and, when an opponent is known, the inverse row.
    Returns the number of upserted rows.
    """
    if week < 1:
        raise ValueError("Week must be at least 1.")
    season = _get_or_create_season(
        session,
        sheet_key or f"Season {season_number}",
        season_number,
    )
    opponents = team_opponents or {}
    touched = 0

    for team, code in overrides.items():
        team = str(team or "").strip()
        if not team:
            continue
        code = (code or "").strip() or None
        opp = str(opponents.get(team) or "").strip() or None

        if not code:
            session.execute(
                delete(MatchupOverride).where(
                    MatchupOverride.season_id == season.id,
                    MatchupOverride.week == week,
                    MatchupOverride.team == team,
                )
            )
            if opp:
                session.execute(
                    delete(MatchupOverride).where(
                        MatchupOverride.season_id == season.id,
                        MatchupOverride.week == week,
                        MatchupOverride.team == opp,
                    )
                )
            continue

        wins, losses, ties = parse_series_code(code)
        if not opp:
            raise ValueError(
                f"Series override for {team!r} needs an opponent this week."
            )
        _upsert_override(
            session,
            season_id=season.id,
            week=week,
            team=team,
            opponent=opp,
            wins=wins,
            losses=losses,
            ties=ties,
            playoffs=playoffs,
        )
        touched += 1
        _upsert_override(
            session,
            season_id=season.id,
            week=week,
            team=opp,
            opponent=team,
            wins=losses,
            losses=wins,
            ties=ties,
            playoffs=playoffs,
        )
        touched += 1

    return touched


def _upsert_override(
    session: Session,
    *,
    season_id: int,
    week: int,
    team: str,
    opponent: str,
    wins: int,
    losses: int,
    ties: int,
    playoffs: bool,
) -> None:
    existing = session.scalar(
        select(MatchupOverride).where(
            MatchupOverride.season_id == season_id,
            MatchupOverride.week == week,
            MatchupOverride.team == team,
        )
    )
    if existing is None:
        session.add(
            MatchupOverride(
                season_id=season_id,
                week=week,
                team=team,
                opponent=opponent,
                wins=wins,
                losses=losses,
                ties=ties,
                playoffs=playoffs,
            )
        )
        return
    existing.opponent = opponent
    existing.wins = wins
    existing.losses = losses
    existing.ties = ties
    existing.playoffs = playoffs
