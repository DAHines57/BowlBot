"""Create seasons, rosters, and destructive deletes (admin)."""
from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from db.models import MatchupOverride, Player, PlayerWeek, Season, Team
from db.player_week_writes import save_week_rows
from db.sync import _get_or_create_player, _get_or_create_season
from db.team_colors import normalize_color_hex
from stats.facts import canonical_team_name, name_matches_team


def _parse_team_id(raw: Any) -> Optional[int]:
    if raw is None or raw == "":
        return None
    try:
        tid = int(raw)
    except (TypeError, ValueError):
        return None
    return tid if tid > 0 else None


def _player_week_has_entry_data(pw: PlayerWeek) -> bool:
    """True if this row has scores or other data worth keeping when off the roster."""
    if pw.absent or pw.substitute or pw.playoffs:
        return True
    if pw.opponent:
        return True
    if pw.week_average is not None:
        return True
    return any(
        g is not None for g in (pw.game1, pw.game2, pw.game3, pw.game4, pw.game5)
    )


def rename_team_references(
    session: Session,
    season_id: int,
    season_number: int,
    old_name: str,
    new_name: str,
) -> None:
    """Update denormalized team name strings after a retroactive rename."""
    new_canon = canonical_team_name(new_name, season_num=season_number)
    if canonical_team_name(old_name, season_num=season_number) == new_canon:
        return

    for pw in session.scalars(
        select(PlayerWeek).where(PlayerWeek.season_id == season_id)
    ).all():
        if pw.opponent and name_matches_team(pw.opponent, old_name):
            pw.opponent = new_canon

    for mo in session.scalars(
        select(MatchupOverride).where(MatchupOverride.season_id == season_id)
    ).all():
        if name_matches_team(mo.team, old_name):
            mo.team = new_canon
        if name_matches_team(mo.opponent, old_name):
            mo.opponent = new_canon
    session.flush()


def list_all_player_names(session: Session) -> List[str]:
    rows = session.scalars(select(Player.display_name).order_by(Player.display_name)).all()
    return list(rows)


def suggest_new_season_numbers(
    db_seasons: List[dict], *, ahead: int = 3
) -> List[int]:
    """Next season numbers to create (only above current max, no backfilling gaps)."""
    existing = {int(s["number"]) for s in db_seasons}
    if not existing:
        return list(range(1, ahead + 1))
    hi = max(existing)
    return list(range(hi + 1, hi + ahead + 1))


def list_db_seasons(session: Session) -> List[dict]:
    seasons = session.scalars(select(Season).order_by(Season.number.desc())).all()
    out = []
    for s in seasons:
        week_count = session.scalar(
            select(func.count(func.distinct(PlayerWeek.week))).where(
                PlayerWeek.season_id == s.id
            )
        )
        team_count = session.scalar(
            select(func.count()).select_from(Team).where(Team.season_id == s.id)
        )
        out.append(
            {
                "number": s.number,
                "label": s.label,
                "sheet_key": s.sheet_key,
                "team_count": team_count or 0,
                "week_count": week_count or 0,
            }
        )
    return out


def get_season_roster(session: Session, season_number: int) -> Optional[dict]:
    season = session.scalar(select(Season).where(Season.number == season_number))
    if season is None:
        return None

    teams = session.scalars(
        select(Team).where(Team.season_id == season.id).order_by(Team.name)
    ).all()
    roster_week = session.scalar(
        select(func.min(PlayerWeek.week)).where(PlayerWeek.season_id == season.id)
    )
    source_week = roster_week if roster_week else 1

    teams_out: List[dict] = []
    for team in teams:
        rows = session.scalars(
            select(PlayerWeek)
            .where(
                PlayerWeek.season_id == season.id,
                PlayerWeek.team_id == team.id,
                PlayerWeek.week == source_week,
                PlayerWeek.substitute.is_(False),
            )
            .order_by(PlayerWeek.player_display_name)
        ).all()
        players = [r.player_display_name for r in rows]
        teams_out.append(
            {
                "id": team.id,
                "name": team.name,
                "players": players,
                "color_hex": normalize_color_hex(team.color_hex),
            }
        )

    return {
        "season_number": season.number,
        "label": season.label,
        "roster_week": int(source_week),
        "teams": teams_out,
    }


def create_season(
    session: Session,
    season_number: int,
    *,
    clone_from: Optional[int] = None,
) -> Season:
    existing = session.scalar(select(Season).where(Season.number == season_number))
    if existing is not None:
        raise ValueError(f"Season {season_number} already exists.")

    label = f"Season {season_number}"
    season = _get_or_create_season(session, label, season_number)

    if clone_from is not None:
        src = get_season_roster(session, clone_from)
        if src and src["teams"]:
            cloned = []
            for t in src["teams"]:
                cloned.append(
                    {
                        "name": t["name"],
                        "players": list(t["players"]),
                        "color_hex": t.get("color_hex"),
                    }
                )
            save_season_roster(session, season_number, cloned, roster_week=1)
    return season


def save_season_roster(
    session: Session,
    season_number: int,
    teams: List[dict[str, Any]],
    *,
    roster_week: int = 1,
) -> int:
    """Upsert teams and roster-week rows; does not delete scored weeks."""
    season = session.scalar(select(Season).where(Season.number == season_number))
    if season is None:
        raise ValueError(f"Season {season_number} not found.")

    submitted_ids: set[int] = set()
    for team_data in teams:
        team_name = canonical_team_name(
            str(team_data.get("name") or "").strip(), season_num=season_number
        )
        if not team_name:
            continue
        color = normalize_color_hex(team_data.get("color_hex"))
        team_id = _parse_team_id(team_data.get("id"))
        if team_id is None:
            continue
        team = session.get(Team, team_id)
        if team is None or team.season_id != season.id:
            raise ValueError(f"Invalid team id {team_id} for season {season_number}.")
        submitted_ids.add(team_id)
        if canonical_team_name(team.name, season_num=season_number) != team_name:
            rename_team_references(
                session, season.id, season_number, team.name, team_name
            )
            team.name = team_name
        team.color_hex = color
    session.flush()

    wanted: set[tuple[str, str]] = set()
    save_rows: List[dict] = []
    wanted_teams: set[str] = set()
    for team_data in teams:
        team_name = canonical_team_name(
            str(team_data.get("name") or "").strip(), season_num=season_number
        )
        if not team_name:
            continue
        wanted_teams.add(team_name)
        players = team_data.get("players") or []
        if isinstance(players, str):
            players = [p.strip() for p in players.splitlines() if p.strip()]

        for player in players:
            pname = str(player).strip()
            if not pname:
                continue
            wanted.add((team_name, pname))
            save_rows.append(
                {
                    "team": team_name,
                    "player_display_name": pname,
                    "game1": None,
                    "game2": None,
                    "game3": None,
                    "game4": None,
                    "game5": None,
                    "absent": False,
                    "substitute": False,
                    "playoffs": False,
                    "opponent": None,
                }
            )

    if save_rows:
        save_week_rows(
            session,
            season_number,
            roster_week,
            save_rows,
            sheet_key=season.label,
            preserve_scores=True,
        )

    for team_data in teams:
        team_name = canonical_team_name(
            str(team_data.get("name") or "").strip(), season_num=season_number
        )
        if not team_name or _parse_team_id(team_data.get("id")) is not None:
            continue
        team = session.scalar(
            select(Team).where(Team.season_id == season.id, Team.name == team_name)
        )
        if team is not None:
            team.color_hex = normalize_color_hex(team_data.get("color_hex"))

    roster_rows = session.scalars(
        select(PlayerWeek)
        .options(joinedload(PlayerWeek.team))
        .where(
            PlayerWeek.season_id == season.id,
            PlayerWeek.week == roster_week,
        )
    ).all()
    for pw in roster_rows:
        team_name = pw.team.name if pw.team else ""
        key = (team_name, pw.player_display_name)
        if key in wanted:
            continue
        if _player_week_has_entry_data(pw):
            continue
        session.delete(pw)

    db_teams = session.scalars(select(Team).where(Team.season_id == season.id)).all()
    for team in db_teams:
        if team.id in submitted_ids:
            continue
        if team.name in wanted_teams:
            continue
        has_rows = session.scalar(
            select(func.count())
            .select_from(PlayerWeek)
            .where(PlayerWeek.team_id == team.id)
        )
        if not has_rows:
            session.delete(team)

    return len(wanted)


def add_team(session: Session, season_number: int, team_name: str) -> Team:
    season = session.scalar(select(Season).where(Season.number == season_number))
    if season is None:
        raise ValueError(f"Season {season_number} not found.")
    name = canonical_team_name(team_name.strip(), season_num=season_number)
    existing = session.scalar(
        select(Team).where(Team.season_id == season.id, Team.name == name)
    )
    if existing:
        return existing
    team = Team(season_id=season.id, name=name)
    session.add(team)
    session.flush()
    return team


def add_player_to_team(
    session: Session,
    season_number: int,
    team_name: str,
    player_name: str,
    *,
    roster_week: int = 1,
) -> None:
    season = session.scalar(select(Season).where(Season.number == season_number))
    if season is None:
        raise ValueError(f"Season {season_number} not found.")
    name = canonical_team_name(team_name.strip(), season_num=season_number)
    team = session.scalar(
        select(Team).where(Team.season_id == season.id, Team.name == name)
    )
    if team is None:
        team = add_team(session, season_number, name)
    player = player_name.strip()
    cache: dict[str, int] = {}
    _get_or_create_player(session, cache, player)
    save_week_rows(
        session,
        season_number,
        roster_week,
        [
            {
                "team": team.name,
                "player_display_name": player,
                "game1": None,
                "game2": None,
                "game3": None,
                "game4": None,
                "game5": None,
                "absent": False,
                "substitute": False,
                "playoffs": False,
                "opponent": None,
            }
        ],
        sheet_key=season.label,
    )


def delete_week(session: Session, season_number: int, week: int) -> int:
    season = session.scalar(select(Season).where(Season.number == season_number))
    if season is None:
        raise ValueError(f"Season {season_number} not found.")
    result = session.execute(
        delete(PlayerWeek).where(
            PlayerWeek.season_id == season.id,
            PlayerWeek.week == week,
        )
    )
    session.execute(
        delete(MatchupOverride).where(
            MatchupOverride.season_id == season.id,
            MatchupOverride.week == week,
        )
    )
    return result.rowcount or 0


def delete_season(session: Session, season_number: int) -> None:
    """Delete a season and all teams, scores, and matchup overrides for it."""
    season = session.scalar(select(Season).where(Season.number == season_number))
    if season is None:
        raise ValueError(f"Season {season_number} not found.")
    sid = season.id
    # session.delete(season) makes ORM null child FKs first (fails on teams.season_id).
    session.execute(delete(PlayerWeek).where(PlayerWeek.season_id == sid))
    session.execute(delete(MatchupOverride).where(MatchupOverride.season_id == sid))
    session.execute(delete(Team).where(Team.season_id == sid))
    session.execute(delete(Season).where(Season.id == sid))
