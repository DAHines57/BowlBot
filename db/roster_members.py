"""Season team roster memberships (players on teams per season)."""
from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import Player, PlayerWeek, Season, Team, TeamRosterMember
from db.players import get_or_create_player


def membership_active_at_week(member: TeamRosterMember, week: int) -> bool:
    if not member.active:
        return False
    if member.started_week > week:
        return False
    if member.ended_week is not None and member.ended_week < week:
        return False
    return True


def roster_week_for_season(session: Session, season_id: int) -> int:
    w = session.scalar(
        select(func.min(PlayerWeek.week)).where(PlayerWeek.season_id == season_id)
    )
    return int(w) if w is not None else 1


def current_roster_week(session: Session, season_id: int) -> int:
    """Latest week with any player_week row (0 if none)."""
    w = session.scalar(
        select(func.max(PlayerWeek.week)).where(PlayerWeek.season_id == season_id)
    )
    return int(w) if w is not None else 0


def max_scored_week(session: Session, season_id: int) -> int:
    """Latest week with at least one entered score or an absence flag."""
    best = 0
    for pw in session.scalars(
        select(PlayerWeek).where(PlayerWeek.season_id == season_id)
    ).all():
        if pw.absent or any(
            getattr(pw, g) is not None for g in ("game1", "game2", "game3", "game4", "game5")
        ):
            best = max(best, int(pw.week))
    return best


def player_needs_template_row(
    session: Session,
    season_id: int,
    team_id: int,
    player_id: int,
    roster_week: int,
) -> bool:
    """True if this player should get a player_week template row on roster save."""
    member = session.scalar(
        select(TeamRosterMember).where(
            TeamRosterMember.season_id == season_id,
            TeamRosterMember.team_id == team_id,
            TeamRosterMember.player_id == player_id,
        )
    )
    if member is None:
        return True
    if member.started_week == roster_week:
        return True
    if not member.active or member.ended_week is not None:
        return True
    return False


def _player_week_has_scores(pw: PlayerWeek) -> bool:
    if pw.absent or pw.substitute or pw.playoffs or pw.opponent:
        return True
    if pw.week_average is not None:
        return True
    return any(
        getattr(pw, g) is not None for g in ("game1", "game2", "game3", "game4", "game5")
    )


def cleanup_stale_template_rows(session: Session, season_id: int) -> int:
    """Remove blank player_week rows outside a member's roster week range."""
    deleted = 0
    members = session.scalars(
        select(TeamRosterMember).where(TeamRosterMember.season_id == season_id)
    ).all()
    for m in members:
        for pw in session.scalars(
            select(PlayerWeek).where(
                PlayerWeek.season_id == season_id,
                PlayerWeek.team_id == m.team_id,
                PlayerWeek.player_id == m.player_id,
            )
        ).all():
            if _player_week_has_scores(pw):
                continue
            w = int(pw.week)
            if w < m.started_week or (
                m.ended_week is not None and w > m.ended_week
            ):
                session.delete(pw)
                deleted += 1
    session.flush()
    return deleted


def template_rows_for_week(
    session: Session,
    season_number: int,
    week: int,
) -> List[dict[str, Any]]:
    """Blank score-entry rows for every roster member active in this week."""
    from stats.facts import canonical_team_name

    season = session.scalar(select(Season).where(Season.number == season_number))
    if season is None:
        return []
    members = session.scalars(
        select(TeamRosterMember)
        .where(TeamRosterMember.season_id == season.id)
    ).all()
    if not members:
        return []
    teams = {
        t.id: t
        for t in session.scalars(select(Team).where(Team.season_id == season.id)).all()
    }
    rows: List[dict[str, Any]] = []
    for team_id, team in teams.items():
        for pname in team_player_names_for_week(session, season.id, team_id, week):
            rows.append(
                {
                    "team": canonical_team_name(team.name, season_num=season_number),
                    "player_display_name": pname,
                    "game1": None,
                    "game2": None,
                    "game3": None,
                    "game4": None,
                    "game5": None,
                    "absent": False,
                    "game1_absent": False,
                    "game2_absent": False,
                    "game3_absent": False,
                    "game4_absent": False,
                    "game5_absent": False,
                    "substitute": False,
                    "substitute_scores_count": False,
                    "substituted_for": None,
                    "playoffs": False,
                    "opponent": None,
                }
            )
    return rows


def default_roster_effective_week(session: Session, season_id: int) -> int:
    """Default week for roster changes (next week to enter, or 1 for a new season)."""
    max_w = current_roster_week(session, season_id)
    return max_w + 1 if max_w > 0 else 1


def roster_week_choices(session: Session, season_id: int, *, extra: int = 2) -> List[int]:
    """Week numbers offered on the season setup form."""
    max_w = current_roster_week(session, season_id)
    high = max(max_w + extra, 1)
    return list(range(1, high + 1))


def get_active_members_for_team(
    session: Session,
    season_id: int,
    team_id: int,
    *,
    week: Optional[int] = None,
) -> List[TeamRosterMember]:
    rows = session.scalars(
        select(TeamRosterMember)
        .where(
            TeamRosterMember.season_id == season_id,
            TeamRosterMember.team_id == team_id,
        )
        .order_by(TeamRosterMember.id)
    ).all()
    if week is None:
        return [m for m in rows if m.active and m.ended_week is None]
    return [m for m in rows if membership_active_at_week(m, week)]


def backfill_season_roster(
    session: Session,
    season_id: int,
    *,
    roster_week: Optional[int] = None,
    clear_existing: bool = False,
) -> int:
    """Build memberships from non-substitute player_week rows at the roster week."""
    if clear_existing:
        session.execute(
            TeamRosterMember.__table__.delete().where(
                TeamRosterMember.season_id == season_id
            )
        )
        session.flush()

    cache: dict[str, int] = {}
    first_week: dict[tuple[int, int], int] = {}
    for pw in session.scalars(
        select(PlayerWeek)
        .where(
            PlayerWeek.season_id == season_id,
            PlayerWeek.substitute.is_(False),
        )
    ).all():
        if pw.team_id is None:
            continue
        player_id = pw.player_id
        if player_id is None:
            player_id = get_or_create_player(session, cache, pw.player_display_name)
            pw.player_id = player_id
        key = (pw.team_id, player_id)
        w = int(pw.week)
        if key not in first_week or w < first_week[key]:
            first_week[key] = w

    if not first_week:
        return 0

    count = 0
    for (team_id, player_id), started in first_week.items():
        existing = session.scalar(
            select(TeamRosterMember).where(
                TeamRosterMember.season_id == season_id,
                TeamRosterMember.team_id == team_id,
                TeamRosterMember.player_id == player_id,
            )
        )
        if existing is None:
            session.add(
                TeamRosterMember(
                    season_id=season_id,
                    team_id=team_id,
                    player_id=player_id,
                    is_captain=False,
                    started_week=started,
                    ended_week=None,
                    active=True,
                )
            )
            count += 1
        else:
            existing.active = True
            existing.ended_week = None
            if existing.started_week > started:
                existing.started_week = started
            count += 1
    session.flush()
    return count


def backfill_all_seasons(session: Session, *, clear_existing: bool = False) -> int:
    seasons = session.scalars(select(Season.id)).all()
    total = 0
    for sid in seasons:
        total += backfill_season_roster(
            session, sid, clear_existing=clear_existing
        )
    return total


def sync_roster_from_admin(
    session: Session,
    season: Season,
    teams: Sequence[dict[str, Any]],
    *,
    roster_week: int = 1,
) -> int:
    """Upsert active memberships from season admin team/player lists."""
    wanted: set[tuple[int, int]] = set()
    cache: dict[str, int] = {}
    count = 0

    for team_data in teams:
        team_name = str(team_data.get("name") or "").strip()
        if not team_name:
            continue
        team_id = team_data.get("id")
        team: Optional[Team] = None
        if team_id is not None:
            try:
                tid = int(team_id)
            except (TypeError, ValueError):
                tid = 0
            if tid > 0:
                team = session.get(Team, tid)
        if team is None:
            team = session.scalar(
                select(Team).where(
                    Team.season_id == season.id, Team.name == team_name
                )
            )
        if team is None or team.season_id != season.id:
            continue

        players = team_data.get("players") or []
        if isinstance(players, str):
            players = [p.strip() for p in players.splitlines() if p.strip()]
        captain = team_data.get("captain")
        captain_name = str(captain).strip() if captain else ""

        for raw_name in players:
            pname = str(raw_name).strip()
            if not pname:
                continue
            player_id = get_or_create_player(session, cache, pname)
            wanted.add((team.id, player_id))
            is_captain = bool(captain_name and pname == captain_name)
            member = session.scalar(
                select(TeamRosterMember).where(
                    TeamRosterMember.season_id == season.id,
                    TeamRosterMember.team_id == team.id,
                    TeamRosterMember.player_id == player_id,
                )
            )
            if member is None:
                session.add(
                    TeamRosterMember(
                        season_id=season.id,
                        team_id=team.id,
                        player_id=player_id,
                        is_captain=is_captain,
                        started_week=roster_week,
                        ended_week=None,
                        active=True,
                    )
                )
                count += 1
            else:
                was_inactive = not member.active or member.ended_week is not None
                member.active = True
                member.ended_week = None
                if was_inactive or member.started_week > roster_week:
                    member.started_week = roster_week
                member.is_captain = is_captain
                count += 1

        if captain_name:
            for other in session.scalars(
                select(TeamRosterMember).where(
                    TeamRosterMember.season_id == season.id,
                    TeamRosterMember.team_id == team.id,
                    TeamRosterMember.is_captain.is_(True),
                )
            ).all():
                player = session.get(Player, other.player_id)
                if player and player.display_name != captain_name:
                    other.is_captain = False

    for member in session.scalars(
        select(TeamRosterMember).where(TeamRosterMember.season_id == season.id)
    ).all():
        key = (member.team_id, member.player_id)
        if key in wanted:
            continue
        if not member.active and member.ended_week is not None:
            continue
        member.active = False
        member.ended_week = max(1, roster_week - 1)
        member.is_captain = False

    session.flush()
    return count


def ensure_membership_for_player(
    session: Session,
    season: Season,
    team: Team,
    player_name: str,
    *,
    roster_week: int = 1,
) -> TeamRosterMember:
    cache: dict[str, int] = {}
    player_id = get_or_create_player(session, cache, player_name)
    member = session.scalar(
        select(TeamRosterMember).where(
            TeamRosterMember.season_id == season.id,
            TeamRosterMember.team_id == team.id,
            TeamRosterMember.player_id == player_id,
        )
    )
    if member is None:
        member = TeamRosterMember(
            season_id=season.id,
            team_id=team.id,
            player_id=player_id,
            is_captain=False,
            started_week=roster_week,
            ended_week=None,
            active=True,
        )
        session.add(member)
    else:
        member.active = True
        member.ended_week = None
        if member.started_week > roster_week:
            member.started_week = roster_week
    session.flush()
    return member


def clone_roster_memberships(
    session: Session,
    src_season_id: int,
    dst_season: Season,
    *,
    team_name_map: Optional[dict[str, str]] = None,
) -> int:
    """Copy active memberships to a new season (teams must already exist by name)."""
    src_members = session.scalars(
        select(TeamRosterMember)
        .where(
            TeamRosterMember.season_id == src_season_id,
            TeamRosterMember.active.is_(True),
            TeamRosterMember.ended_week.is_(None),
        )
    ).all()
    if not src_members:
        return backfill_season_roster(session, dst_season.id, roster_week=1)

    src_teams = {
        t.id: t
        for t in session.scalars(
            select(Team).where(Team.season_id == src_season_id)
        ).all()
    }
    dst_by_name = {
        t.name: t
        for t in session.scalars(
            select(Team).where(Team.season_id == dst_season.id)
        ).all()
    }
    count = 0
    for m in src_members:
        src_team = src_teams.get(m.team_id)
        if src_team is None:
            continue
        dst_name = (
            team_name_map.get(src_team.name, src_team.name)
            if team_name_map
            else src_team.name
        )
        dst_team = dst_by_name.get(dst_name)
        if dst_team is None:
            continue
        exists = session.scalar(
            select(TeamRosterMember).where(
                TeamRosterMember.season_id == dst_season.id,
                TeamRosterMember.team_id == dst_team.id,
                TeamRosterMember.player_id == m.player_id,
            )
        )
        if exists is not None:
            continue
        session.add(
            TeamRosterMember(
                season_id=dst_season.id,
                team_id=dst_team.id,
                player_id=m.player_id,
                is_captain=m.is_captain,
                started_week=1,
                ended_week=None,
                active=True,
            )
        )
        count += 1
    session.flush()
    return count


def team_player_names_from_memberships(
    session: Session,
    season_id: int,
    team_id: int,
    *,
    week: Optional[int] = None,
) -> List[str]:
    members = get_active_members_for_team(session, season_id, team_id, week=week)
    names: List[str] = []
    for m in members:
        player = session.get(Player, m.player_id)
        if player:
            names.append(player.display_name)
    return sorted(names)


def team_player_names_for_week(
    session: Session,
    season_id: int,
    team_id: int,
    week: int,
) -> List[str]:
    """Players on this team for this week (membership + actual week rows)."""
    names: set[str] = set(team_player_names_from_memberships(
        session, season_id, team_id, week=week
    ))
    for pw in session.scalars(
        select(PlayerWeek.player_display_name).where(
            PlayerWeek.season_id == season_id,
            PlayerWeek.team_id == team_id,
            PlayerWeek.week == week,
            PlayerWeek.substitute.is_(False),
        )
    ).all():
        pname = str(pw).strip()
        if pname:
            names.add(pname)
    return sorted(names)


def captain_for_team_at_week(
    session: Session,
    season_id: int,
    team_id: int,
    week: int,
    player_names: List[str],
) -> Optional[str]:
    """Captain among players listed for this team/week."""
    if not player_names:
        return None
    name_set = set(player_names)
    for m in get_active_members_for_team(session, season_id, team_id, week=week):
        if not m.is_captain:
            continue
        player = session.get(Player, m.player_id)
        if player and player.display_name in name_set:
            return player.display_name
    return None
