"""Editable site pages (rules)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.site_pages import (
    CHANGELOG_SLUG,
    RULES_SLUG,
    get_or_create_page,
    page_to_dict,
    save_page,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_get_or_create_and_save_rules(db_session):
    page = get_or_create_page(db_session, RULES_SLUG, title="League Rules")
    db_session.commit()
    assert page.slug == "rules"
    assert page.body == ""

    saved = save_page(
        db_session,
        RULES_SLUG,
        title="Monday Night Rules",
        body="# Absences\n\n- First miss is full average\n\nBe nice.",
    )
    db_session.commit()
    data = page_to_dict(saved)
    assert data["title"] == "Monday Night Rules"
    assert "First miss" in data["body"]
    assert data["updated_at"]


def test_get_or_create_and_save_changelog(db_session):
    page = get_or_create_page(db_session, CHANGELOG_SLUG, title="Changelog")
    db_session.commit()
    assert page.slug == "changelog"

    saved = save_page(
        db_session,
        CHANGELOG_SLUG,
        title="Changelog",
        body="# v2.1.0\n\n- Players / Subs toggle\n- Changelog tab",
    )
    db_session.commit()
    data = page_to_dict(saved)
    assert data["slug"] == "changelog"
    assert "v2.1.0" in data["body"]
