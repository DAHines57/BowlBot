"""align seasons.id with seasons.number

Revision ID: 004_season_id_number
Revises: 003_team_color_hex
Create Date: 2026-05-16

Historically seasons.id was a serial (1, 2, …) while number held the league
season (2, 3, …). This migration renumbers PKs so id == number everywhere.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "004_season_id_number"
down_revision: Union[str, Sequence[str], None] = "003_team_color_hex"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TEAMS_FK = "teams_season_id_fkey"
_PW_FK = "player_weeks_season_id_fkey"
_TEMP_OFFSET = 10000


def _drop_season_fks() -> None:
    op.drop_constraint(_TEAMS_FK, "teams", type_="foreignkey")
    op.drop_constraint(_PW_FK, "player_weeks", type_="foreignkey")


def _create_season_fks() -> None:
    op.create_foreign_key(
        _TEAMS_FK,
        "teams",
        "seasons",
        ["season_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        _PW_FK,
        "player_weeks",
        "seasons",
        ["season_id"],
        ["id"],
        ondelete="CASCADE",
    )


def _move_children_to_temp_season_ids() -> None:
    op.execute(
        f"""
        UPDATE teams t
        SET season_id = s.number + {_TEMP_OFFSET}
        FROM seasons s
        WHERE t.season_id = s.id
        """
    )
    op.execute(
        f"""
        UPDATE player_weeks pw
        SET season_id = s.number + {_TEMP_OFFSET}
        FROM seasons s
        WHERE pw.season_id = s.id
        """
    )


def _move_children_from_temp_season_ids() -> None:
    op.execute(f"UPDATE teams SET season_id = season_id - {_TEMP_OFFSET}")
    op.execute(f"UPDATE player_weeks SET season_id = season_id - {_TEMP_OFFSET}")


def _renumber_season_pks(*, to_temp: bool) -> None:
    if to_temp:
        op.execute(f"UPDATE seasons SET id = number + {_TEMP_OFFSET}")
    else:
        op.execute(f"UPDATE seasons SET id = id - {_TEMP_OFFSET}")


def _reset_seasons_sequence() -> None:
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('seasons', 'id'),
            COALESCE((SELECT MAX(id) FROM seasons), 1)
        )
        """
    )


def upgrade() -> None:
    _drop_season_fks()
    _move_children_to_temp_season_ids()
    _renumber_season_pks(to_temp=True)
    _move_children_from_temp_season_ids()
    _renumber_season_pks(to_temp=False)
    _create_season_fks()
    _reset_seasons_sequence()


def downgrade() -> None:
    _drop_season_fks()
    op.execute(
        f"""
        UPDATE teams t
        SET season_id = s.number - 1 + {_TEMP_OFFSET}
        FROM seasons s
        WHERE t.season_id = s.id
        """
    )
    op.execute(
        f"""
        UPDATE player_weeks pw
        SET season_id = s.number - 1 + {_TEMP_OFFSET}
        FROM seasons s
        WHERE pw.season_id = s.id
        """
    )
    op.execute(f"UPDATE seasons SET id = number - 1 + {_TEMP_OFFSET}")
    op.execute(f"UPDATE teams SET season_id = season_id - {_TEMP_OFFSET}")
    op.execute(f"UPDATE player_weeks SET season_id = season_id - {_TEMP_OFFSET}")
    op.execute(f"UPDATE seasons SET id = id - {_TEMP_OFFSET}")
    _create_season_fks()
    _reset_seasons_sequence()
