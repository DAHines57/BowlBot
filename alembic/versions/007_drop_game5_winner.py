"""drop game5_winner from player_weeks

Revision ID: 007_drop_game5_winner
Revises: 006_matchup_overrides
Create Date: 2026-05-17

Series W/L now comes from matchup_overrides; the per-row Game 5 winner column is unused.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_drop_game5_winner"
down_revision: Union[str, Sequence[str], None] = "006_matchup_overrides"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("player_weeks", "game5_winner")


def downgrade() -> None:
    op.add_column(
        "player_weeks",
        sa.Column("game5_winner", sa.String(length=128), nullable=True),
    )
