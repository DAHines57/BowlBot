"""remove Season 2 from database

Revision ID: 005_remove_season_2
Revises: 004_season_id_number
Create Date: 2026-05-16

Season 2 in the v5 workbook has no opponent column data; drop it from Postgres.
Re-sync will not recreate it (see db.excluded_seasons).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_remove_season_2"
down_revision: Union[str, Sequence[str], None] = "004_season_id_number"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM seasons WHERE number = 2"))


def downgrade() -> None:
    pass
