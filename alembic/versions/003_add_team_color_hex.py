"""add color_hex to teams

Revision ID: 003_team_color_hex
Revises: 002_game5_winner
Create Date: 2026-05-16

"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from stats.facts import canonical_team_name

revision: str = "003_team_color_hex"
down_revision: Union[str, Sequence[str], None] = "002_game5_winner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_colors() -> dict[str, str]:
    path = Path(__file__).resolve().parents[2] / "team_colors.json"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    return {canonical_team_name(k): v for k, v in raw.items()}


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column("color_hex", sa.String(length=7), nullable=True),
    )
    colors = _json_colors()
    if not colors:
        return
    bind = op.get_bind()
    teams = bind.execute(sa.text("SELECT id, name FROM teams")).fetchall()
    for team_id, name in teams:
        hex_c = colors.get(canonical_team_name(name)) or colors.get(name)
        if hex_c:
            bind.execute(
                sa.text("UPDATE teams SET color_hex = :hex WHERE id = :id"),
                {"hex": hex_c, "id": team_id},
            )


def downgrade() -> None:
    op.drop_column("teams", "color_hex")
