"""add per-game absent flags on player_weeks

Revision ID: 009_per_game_absent
Revises: 008_team_roster_members
Create Date: 2026-05-22

gameN_absent marks a book-average / missed game slot (score still counts for team pins).
Week-level absent remains full-week absence.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_per_game_absent"
down_revision: Union[str, Sequence[str], None] = "008_team_roster_members"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for n in range(1, 6):
        op.add_column(
            "player_weeks",
            sa.Column(
                f"game{n}_absent",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    for n in range(5, 0, -1):
        op.drop_column("player_weeks", f"game{n}_absent")
