"""Load player-week facts from PostgreSQL (same shape as iter_player_week_rows)."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from db.models import MatchupOverride, PlayerWeek, Season, Team, TeamRosterMember
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
        roster_windows: dict[tuple[int, int, int], tuple[int, Optional[int]]] = {}
        for m in session.scalars(select(TeamRosterMember)).all():
            roster_windows[(m.season_id, m.team_id, m.player_id)] = (
                int(m.started_week),
                int(m.ended_week) if m.ended_week is not None else None,
            )
        facts: List[dict] = []
        for pw in rows:
            season = pw.season
            team = pw.team
            if pw.player_id is not None:
                window = roster_windows.get((season.id, team.id, pw.player_id))
                started, ended = window if window else (1, None)
            else:
                started, ended = 1, None
            facts.append(
                {
                    "sheet_key": season.sheet_key,
                    "season_number": season.number,
                    "season_label": season.label,
                    "team": canonical_team_name(team.name, season_num=season.number),
                    "player_display_name": pw.player_display_name,
                    "week": pw.week,
                    "roster_started_week": started,
                    "roster_ended_week": ended,
                    "game1": float(pw.game1) if pw.game1 is not None else None,
                    "game2": float(pw.game2) if pw.game2 is not None else None,
                    "game3": float(pw.game3) if pw.game3 is not None else None,
                    "game4": float(pw.game4) if pw.game4 is not None else None,
                    "game5": float(pw.game5) if pw.game5 is not None else None,
                    "week_average": float(pw.week_average)
                    if pw.week_average is not None
                    else None,
                    "absent": bool(pw.absent),
                    "game1_absent": bool(pw.game1_absent),
                    "game2_absent": bool(pw.game2_absent),
                    "game3_absent": bool(pw.game3_absent),
                    "game4_absent": bool(pw.game4_absent),
                    "game5_absent": bool(pw.game5_absent),
                    "substitute": bool(pw.substitute),
                    "playoffs": bool(pw.playoffs),
                    "opponent": canonical_team_name(
                        pw.opponent, season_num=season.number
                    )
                    if pw.opponent
                    else None,
                    "source_row_fingerprint": pw.source_row_fingerprint,
                }
            )
        return facts
    finally:
        if own_session:
            session.close()


def load_all_matchup_overrides(session: Optional[Session] = None) -> List[dict]:
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        stmt = (
            select(MatchupOverride)
            .options(joinedload(MatchupOverride.season))
            .join(MatchupOverride.season)
            .order_by(Season.number, MatchupOverride.week, MatchupOverride.team)
        )
        rows = session.scalars(stmt).all()
        out: List[dict] = []
        for mo in rows:
            sn = mo.season.number
            out.append(
                {
                    "season_number": sn,
                    "week": mo.week,
                    "team": canonical_team_name(mo.team, season_num=sn),
                    "opponent": canonical_team_name(mo.opponent, season_num=sn)
                    if mo.opponent
                    else "",
                    "wins": int(mo.wins),
                    "losses": int(mo.losses),
                    "ties": int(mo.ties),
                    "playoffs": bool(mo.playoffs),
                }
            )
        return out
    finally:
        if own_session:
            session.close()
