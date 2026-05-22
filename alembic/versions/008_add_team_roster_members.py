"""add team_roster_members for season team rosters

Revision ID: 008_team_roster_members
Revises: 007_drop_game5_winner
Create Date: 2026-05-20

Links players to teams per season (captain, active, started/ended week).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_team_roster_members"
down_revision: Union[str, Sequence[str], None] = "007_drop_game5_winner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_roster_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("is_captain", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("started_week", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("ended_week", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "season_id",
            "team_id",
            "player_id",
            name="uq_roster_season_team_player",
        ),
    )
    op.create_index(
        "ix_roster_members_season_team",
        "team_roster_members",
        ["season_id", "team_id"],
        unique=False,
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE UNIQUE INDEX uq_roster_one_captain_per_team
            ON team_roster_members (team_id)
            WHERE is_captain IS TRUE
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_roster_one_captain_per_team")
    op.drop_index("ix_roster_members_season_team", table_name="team_roster_members")
    op.drop_table("team_roster_members")
