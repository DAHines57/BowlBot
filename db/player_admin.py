"""Global player rename and purge (admin)."""
from __future__ import annotations

from typing import Any, List

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from db.models import Player, PlayerWeek, Season, TeamRosterMember
from db.season_admin import _player_week_has_entry_data


def _week_rows_for_player(session: Session, player: Player) -> List[PlayerWeek]:
    """All player_week rows tied to this player (by id or orphan display name)."""
    return list(
        session.scalars(
            select(PlayerWeek).where(
                or_(
                    PlayerWeek.player_id == player.id,
                    (
                        PlayerWeek.player_id.is_(None)
                        & (PlayerWeek.player_display_name == player.display_name)
                    ),
                )
            )
        ).all()
    )


def list_players(session: Session) -> List[dict[str, Any]]:
    rows = session.scalars(select(Player).order_by(Player.display_name)).all()
    return [{"id": p.id, "display_name": p.display_name} for p in rows]


def player_impact_summary(session: Session, player_id: int) -> dict[str, Any]:
    """Counts and season breakdown before rename or purge."""
    player = session.get(Player, player_id)
    if player is None:
        raise ValueError(f"Player id {player_id} not found.")

    week_rows = _week_rows_for_player(session, player)
    meaningful = sum(1 for pw in week_rows if _player_week_has_entry_data(pw))

    season_ids = {pw.season_id for pw in week_rows}
    seasons: List[dict[str, Any]] = []
    for sid in sorted(season_ids):
        season = session.get(Season, sid)
        if season is None:
            continue
        s_rows = [pw for pw in week_rows if pw.season_id == sid]
        weeks = sorted({pw.week for pw in s_rows})
        s_meaningful = sum(1 for pw in s_rows if _player_week_has_entry_data(pw))
        seasons.append(
            {
                "number": season.number,
                "label": season.label,
                "week_row_count": len(s_rows),
                "meaningful_row_count": s_meaningful,
                "week_min": min(weeks) if weeks else None,
                "week_max": max(weeks) if weeks else None,
            }
        )

    roster_count = session.scalar(
        select(func.count())
        .select_from(TeamRosterMember)
        .where(TeamRosterMember.player_id == player.id)
    )

    return {
        "player_id": player.id,
        "display_name": player.display_name,
        "week_row_count": len(week_rows),
        "meaningful_row_count": meaningful,
        "season_count": len(season_ids),
        "roster_membership_count": int(roster_count or 0),
        "seasons": seasons,
    }


def rename_player(session: Session, player_id: int, new_name: str) -> int:
    """Rename player and all linked player_week rows; returns rows updated."""
    new_name = str(new_name or "").strip()
    if not new_name:
        raise ValueError("New name is required.")
    if len(new_name) > 128:
        raise ValueError("Name must be 128 characters or fewer.")

    player = session.get(Player, player_id)
    if player is None:
        raise ValueError(f"Player id {player_id} not found.")

    old_name = player.display_name
    if new_name == old_name:
        return 0

    other = session.scalar(select(Player).where(Player.display_name == new_name))
    if other is not None and other.id != player.id:
        raise ValueError(
            f"A player named '{new_name}' already exists (id {other.id}). "
            "Choose a different name or merge manually."
        )

    week_rows = _week_rows_for_player(session, player)
    for pw in week_rows:
        conflict = session.scalar(
            select(PlayerWeek.id).where(
                PlayerWeek.season_id == pw.season_id,
                PlayerWeek.week == pw.week,
                PlayerWeek.team_id == pw.team_id,
                PlayerWeek.player_display_name == new_name,
                PlayerWeek.id != pw.id,
            )
        )
        if conflict is not None:
            season = session.get(Season, pw.season_id)
            label = season.label if season else f"season_id={pw.season_id}"
            raise ValueError(
                f"Cannot rename to '{new_name}': week {pw.week} on that team in {label} "
                "already has a row with that name."
            )

    for pw in week_rows:
        pw.player_display_name = new_name
    player.display_name = new_name
    session.flush()
    return len(week_rows)


def purge_player(
    session: Session,
    player_id: int,
    *,
    confirm_name: str,
) -> dict[str, int]:
    """Delete all week rows and the player record (roster memberships cascade)."""
    player = session.get(Player, player_id)
    if player is None:
        raise ValueError(f"Player id {player_id} not found.")

    typed = str(confirm_name or "").strip()
    if typed != player.display_name:
        raise ValueError(
            "Confirmation name does not match. "
            f"Type exactly: {player.display_name}"
        )

    display_name = player.display_name
    week_result = session.execute(
        delete(PlayerWeek).where(
            or_(
                PlayerWeek.player_id == player_id,
                (
                    PlayerWeek.player_id.is_(None)
                    & (PlayerWeek.player_display_name == display_name)
                ),
            )
        )
    )
    deleted_weeks = int(week_result.rowcount or 0)

    roster_result = session.execute(
        delete(TeamRosterMember).where(TeamRosterMember.player_id == player_id)
    )
    deleted_roster = int(roster_result.rowcount or 0)

    session.delete(player)
    session.flush()

    return {
        "deleted_week_rows": deleted_weeks,
        "deleted_roster_memberships": deleted_roster,
    }
