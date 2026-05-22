"""Upsert player_week rows for DB-managed seasons (Phase 7)."""
from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import PlayerWeek, Team
from db.players import get_or_create_player
from db.sync import _get_or_create_season
from stats.facts import canonical_team_name, resolve_opponent_on_roster


def compute_week_average(
    games: tuple[Optional[float], ...],
    provided: Optional[float] = None,
) -> Optional[float]:
    if provided is not None:
        return float(provided)
    played = [g for g in games if g is not None]
    if not played:
        return None
    return sum(played) / len(played)


def _get_or_create_team(
    session: Session,
    season_id: int,
    team_name: str,
    *,
    color_hex: Optional[str] = None,
) -> int:
    team = session.scalar(
        select(Team).where(Team.season_id == season_id, Team.name == team_name)
    )
    if team is None:
        team = Team(season_id=season_id, name=team_name, color_hex=color_hex)
        session.add(team)
        session.flush()
    return team.id


def _normalize_row(row: dict[str, Any], season_num: int, roster: List[str]) -> dict[str, Any]:
    team = canonical_team_name(str(row["team"]).strip(), season_num=season_num)
    player = str(row["player_display_name"]).strip()
    week = int(row["week"])
    games = (
        row.get("game1"),
        row.get("game2"),
        row.get("game3"),
        row.get("game4"),
        row.get("game5"),
    )
    week_average = compute_week_average(games, row.get("week_average"))
    opponent = row.get("opponent")
    if opponent:
        opp = str(opponent).strip()
        hit = resolve_opponent_on_roster(opp, roster, season_num=season_num)
        if hit:
            opponent = hit
        else:
            opponent = opp
    return {
        "team": team,
        "player_display_name": player,
        "week": week,
        "game1": games[0],
        "game2": games[1],
        "game3": games[2],
        "game4": games[3],
        "game5": games[4],
        "week_average": week_average,
        "absent": bool(row.get("absent")),
        "substitute": bool(row.get("substitute")),
        "playoffs": bool(row.get("playoffs")),
        "opponent": opponent,
    }


def upsert_player_week(
    session: Session,
    season_number: int,
    row: dict[str, Any],
    *,
    sheet_key: Optional[str] = None,
    player_cache: Optional[dict[str, int]] = None,
    roster: Optional[List[str]] = None,
    preserve_scores: bool = False,
) -> PlayerWeek:
    """Insert or update one player_week row. Caller commits the session."""
    label = sheet_key or f"Season {season_number}"
    season = _get_or_create_season(session, label, season_number)
    if roster is None:
        roster = [
            canonical_team_name(str(row["team"]).strip(), season_num=season_number)
        ]
    normalized = _normalize_row(row, season_number, roster)

    team_id = _get_or_create_team(session, season.id, normalized["team"])
    cache = player_cache if player_cache is not None else {}
    player_id = get_or_create_player(
        session, cache, normalized["player_display_name"]
    )

    existing = session.scalar(
        select(PlayerWeek).where(
            PlayerWeek.season_id == season.id,
            PlayerWeek.week == normalized["week"],
            PlayerWeek.team_id == team_id,
            PlayerWeek.player_display_name == normalized["player_display_name"],
        )
    )
    if existing is None:
        pw = PlayerWeek(
            season_id=season.id,
            week=normalized["week"],
            team_id=team_id,
            player_id=player_id,
            player_display_name=normalized["player_display_name"],
            game1=normalized["game1"],
            game2=normalized["game2"],
            game3=normalized["game3"],
            game4=normalized["game4"],
            game5=normalized["game5"],
            week_average=normalized["week_average"],
            absent=normalized["absent"],
            substitute=normalized["substitute"],
            playoffs=normalized["playoffs"],
            opponent=normalized["opponent"],
            source_row_fingerprint=None,
        )
        session.add(pw)
        session.flush()
        return pw

    existing.player_id = player_id
    if preserve_scores:
        session.flush()
        return existing
    existing.game1 = normalized["game1"]
    existing.game2 = normalized["game2"]
    existing.game3 = normalized["game3"]
    existing.game4 = normalized["game4"]
    existing.game5 = normalized["game5"]
    existing.week_average = normalized["week_average"]
    existing.absent = normalized["absent"]
    existing.substitute = normalized["substitute"]
    existing.playoffs = normalized["playoffs"]
    existing.opponent = normalized["opponent"]
    session.flush()
    return existing


def sync_week_team_opponents(
    session: Session,
    season_number: int,
    week: int,
    team_opponents: dict[str, str],
    *,
    sheet_key: Optional[str] = None,
) -> int:
    """Set opponent on every player_week row for each team in the map."""
    if not team_opponents:
        return 0
    label = sheet_key or f"Season {season_number}"
    season = _get_or_create_season(session, label, season_number)
    season_id = season.id
    roster = sorted(
        {canonical_team_name(name, season_num=season_number) for name in team_opponents}
        | {canonical_team_name(opp, season_num=season_number) for opp in team_opponents.values()}
    )
    updated = 0
    for team_name, opp_raw in team_opponents.items():
        team = canonical_team_name(str(team_name).strip(), season_num=season_number)
        team_id = _get_or_create_team(session, season_id, team)
        opp = str(opp_raw).strip() if opp_raw else None
        if opp:
            hit = resolve_opponent_on_roster(opp, roster, season_num=season_number)
            opp = hit or opp
        rows = session.scalars(
            select(PlayerWeek).where(
                PlayerWeek.season_id == season_id,
                PlayerWeek.week == week,
                PlayerWeek.team_id == team_id,
            )
        ).all()
        for pw in rows:
            if pw.opponent != opp:
                pw.opponent = opp
                updated += 1
    session.flush()
    return updated


def save_week_rows(
    session: Session,
    season_number: int,
    week: int,
    rows: List[dict[str, Any]],
    *,
    sheet_key: Optional[str] = None,
    preserve_scores: bool = False,
) -> int:
    """Upsert all rows for one week. Returns count written."""
    roster = sorted(
        {
            canonical_team_name(str(r["team"]).strip(), season_num=season_number)
            for r in rows
            if r.get("team")
        }
    )
    player_cache: dict[str, int] = {}
    count = 0
    for row in rows:
        payload = dict(row)
        payload["week"] = week
        upsert_player_week(
            session,
            season_number,
            payload,
            sheet_key=sheet_key,
            player_cache=player_cache,
            roster=roster,
            preserve_scores=preserve_scores,
        )
        count += 1
    return count
