"""add game5_winner to player_weeks

Revision ID: 002_game5_winner
Revises: 001_initial
Create Date: 2026-05-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_game5_winner"
down_revision: Union[str, Sequence[str], None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "player_weeks",
        sa.Column("game5_winner", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("player_weeks", "game5_winner")
