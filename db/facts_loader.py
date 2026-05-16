"""Load player-week facts from PostgreSQL (same shape as iter_player_week_rows)."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from db.models import PlayerWeek, Season, Team
from db.session import get_session
from stats.facts import canonical_team_name


def load_all_facts(session: Optional[Session] = None) -> List[dict]:
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        stmt = (
            select(PlayerWeek)
            .options(
                joinedload(PlayerWeek.team),
                joinedload(PlayerWeek.season),
            )
            .join(PlayerWeek.team)
            .join(PlayerWeek.season)
            .order_by(
                Season.number,
                PlayerWeek.week,
                Team.name,
                PlayerWeek.player_display_name,
            )
        )
        rows = session.scalars(stmt).all()
        facts: List[dict] = []
        for pw in rows:
            season = pw.season
            team = pw.team
            facts.append(
                {
                    "sheet_key": season.sheet_key,
                    "season_number": season.number,
                    "season_label": season.label,
                    "team": canonical_team_name(team.name),
                    "player_display_name": pw.player_display_name,
                    "week": pw.week,
                    "game1": float(pw.game1) if pw.game1 is not None else None,
                    "game2": float(pw.game2) if pw.game2 is not None else None,
                    "game3": float(pw.game3) if pw.game3 is not None else None,
                    "game4": float(pw.game4) if pw.game4 is not None else None,
                    "game5": float(pw.game5) if pw.game5 is not None else None,
                    "week_average": float(pw.week_average)
                    if pw.week_average is not None
                    else None,
                    "absent": bool(pw.absent),
                    "substitute": bool(pw.substitute),
                    "playoffs": bool(pw.playoffs),
                    "opponent": canonical_team_name(pw.opponent)
                    if pw.opponent
                    else None,
                    "game5_winner": pw.game5_winner,
                    "source_row_fingerprint": pw.source_row_fingerprint,
                }
            )
        return facts
    finally:
        if own_session:
            session.close()
