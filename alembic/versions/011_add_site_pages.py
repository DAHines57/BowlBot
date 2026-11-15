"""add site_pages for editable rules content

Revision ID: 011_site_pages
Revises: 010_substitute_fields
Create Date: 2026-11-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_site_pages"
down_revision: Union[str, Sequence[str], None] = "010_substitute_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "site_pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("slug", name="uq_site_pages_slug"),
    )
    op.execute(
        sa.text(
            "INSERT INTO site_pages (slug, title, body) "
            "VALUES ('rules', 'League Rules', '')"
        )
    )


def downgrade() -> None:
    op.drop_table("site_pages")
