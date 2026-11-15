"""seed changelog site_pages row

Revision ID: 012_changelog_page
Revises: 011_site_pages
Create Date: 2026-11-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012_changelog_page"
down_revision: Union[str, Sequence[str], None] = "011_site_pages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO site_pages (slug, title, body) "
            "SELECT 'changelog', 'Changelog', '' "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM site_pages WHERE slug = 'changelog'"
            ")"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM site_pages WHERE slug = 'changelog'"))
