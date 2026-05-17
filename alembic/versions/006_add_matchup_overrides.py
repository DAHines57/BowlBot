"""add matchup_overrides for v4-era weekly W/L/T

Revision ID: 006_matchup_overrides
Revises: 005_remove_season_2
Create Date: 2026-05-17

Stores per-week matchup win/loss/tie from v4 sheets for seasons where pin
totals in the DB are synthetic (repeated averages) and cannot drive records.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_matchup_overrides"
down_revision: Union[str, Sequence[str], None] = "005_remove_season_2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "matchup_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("team", sa.String(length=128), nullable=False),
        sa.Column("opponent", sa.String(length=128), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("losses", sa.Integer(), nullable=False),
        sa.Column("ties", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "playoffs",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "season_id",
            "week",
            "team",
            name="uq_matchup_overrides_season_week_team",
        ),
    )
    op.create_index(
        "ix_matchup_overrides_season_week",
        "matchup_overrides",
        ["season_id", "week"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_matchup_overrides_season_week", table_name="matchup_overrides")
    op.drop_table("matchup_overrides")
