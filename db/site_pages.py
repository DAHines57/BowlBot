"""CRUD for editable site pages (rules, etc.)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import SitePage

RULES_SLUG = "rules"
CHANGELOG_SLUG = "changelog"


def get_page(session: Session, slug: str) -> Optional[SitePage]:
    return session.scalar(select(SitePage).where(SitePage.slug == slug))


def get_or_create_page(
    session: Session,
    slug: str,
    *,
    title: str,
    body: str = "",
) -> SitePage:
    page = get_page(session, slug)
    if page is not None:
        return page
    page = SitePage(slug=slug, title=title, body=body or "")
    session.add(page)
    session.flush()
    return page


def save_page(
    session: Session,
    slug: str,
    *,
    title: str,
    body: str,
) -> SitePage:
    page = get_or_create_page(session, slug, title=title, body=body)
    page.title = (title or "").strip() or page.title
    page.body = body if body is not None else ""
    session.flush()
    return page


def page_to_dict(page: SitePage) -> dict:
    return {
        "slug": page.slug,
        "title": page.title,
        "body": page.body or "",
        "updated_at": page.updated_at.isoformat() if page.updated_at else None,
    }
