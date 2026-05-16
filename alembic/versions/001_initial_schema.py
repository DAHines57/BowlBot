"""initial schema: seasons, teams, players, player_weeks

Revision ID: 001_initial
Revises:
Create Date: 2026-05-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("sheet_key", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
        sa.UniqueConstraint("sheet_key"),
    )
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("display_name"),
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("season_id", "name", name="uq_teams_season_name"),
    )
    op.create_table(
        "player_weeks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("player_display_name", sa.String(length=128), nullable=False),
        sa.Column("game1", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("game2", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("game3", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("game4", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("game5", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("week_average", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("absent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("substitute", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("playoffs", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("opponent", sa.Text(), nullable=True),
        sa.Column("source_row_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "season_id",
            "week",
            "team_id",
            "player_display_name",
            name="uq_player_weeks_season_week_team_player",
        ),
        sa.UniqueConstraint("source_row_fingerprint"),
    )
    op.create_index("ix_player_weeks_season_week", "player_weeks", ["season_id", "week"], unique=False)
    op.create_index("ix_player_weeks_season_player", "player_weeks", ["season_id", "player_id"], unique=False)
    op.create_index(
        "ix_player_weeks_season_week_present",
        "player_weeks",
        ["season_id", "week"],
        unique=False,
        postgresql_where=sa.text("absent IS FALSE"),
    )


def downgrade() -> None:
    op.drop_index("ix_player_weeks_season_week_present", table_name="player_weeks")
    op.drop_index("ix_player_weeks_season_player", table_name="player_weeks")
    op.drop_index("ix_player_weeks_season_week", table_name="player_weeks")
    op.drop_table("player_weeks")
    op.drop_table("teams")
    op.drop_table("players")
    op.drop_table("seasons")
