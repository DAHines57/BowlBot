"""add substitute link and score-count flags on player_weeks

Revision ID: 010_substitute_fields
Revises: 009_per_game_absent
Create Date: 2026-06-21

substituted_for links a sub row to the roster player they replaced.
substitute_scores_count marks whether sub pins count toward team totals.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_substitute_fields"
down_revision: Union[str, Sequence[str], None] = "009_per_game_absent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "player_weeks",
        sa.Column("substitute_scores_count", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "player_weeks",
        sa.Column("substituted_for", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("player_weeks", "substituted_for")
    op.drop_column("player_weeks", "substitute_scores_count")
