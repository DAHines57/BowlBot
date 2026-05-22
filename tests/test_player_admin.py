"""Tests for global player rename and purge."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models import Player, PlayerWeek, TeamRosterMember
from db.player_admin import (
    player_impact_summary,
    purge_player,
    rename_player,
)
from db.player_week_writes import save_week_rows
from db.season_admin import create_season, save_season_roster


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _seed_alice_scores(db_session):
    create_season(db_session, 10)
    save_season_roster(
        db_session,
        10,
        [{"name": "Team A", "players": ["Alice"]}],
    )
    save_week_rows(
        db_session,
        10,
        1,
        [
            {
                "team": "Team A",
                "player_display_name": "Alice",
                "game1": 200,
                "game2": 190,
                "game3": None,
                "game4": None,
                "game5": None,
                "absent": False,
                "substitute": False,
                "playoffs": False,
                "opponent": None,
            }
        ],
    )
    db_session.commit()


def test_rename_player_updates_week_rows(db_session):
    _seed_alice_scores(db_session)
    alice = db_session.scalar(select(Player).where(Player.display_name == "Alice"))
    assert alice is not None

    n = rename_player(db_session, alice.id, "Alicia")
    db_session.commit()

    assert n == 1
    assert db_session.scalar(select(Player).where(Player.display_name == "Alicia"))
    pw = db_session.scalar(select(PlayerWeek))
    assert pw is not None
    assert pw.player_display_name == "Alicia"
    assert pw.game1 == 200


def test_rename_rejects_duplicate_name(db_session):
    create_season(db_session, 10)
    save_season_roster(
        db_session,
        10,
        [
            {"name": "Team A", "players": ["Alice"]},
            {"name": "Team B", "players": ["Bob"]},
        ],
    )
    db_session.commit()
    alice = db_session.scalar(select(Player).where(Player.display_name == "Alice"))
    with pytest.raises(ValueError, match="already exists"):
        rename_player(db_session, alice.id, "Bob")


def test_purge_removes_week_rows_and_player(db_session):
    _seed_alice_scores(db_session)
    alice = db_session.scalar(select(Player).where(Player.display_name == "Alice"))
    impact = player_impact_summary(db_session, alice.id)
    assert impact["week_row_count"] >= 1
    assert impact["meaningful_row_count"] >= 1

    result = purge_player(db_session, alice.id, confirm_name="Alice")
    db_session.commit()

    assert result["deleted_week_rows"] >= 1
    assert db_session.scalar(select(Player).where(Player.display_name == "Alice")) is None
    assert db_session.scalars(select(PlayerWeek)).all() == []


def test_purge_requires_exact_confirm_name(db_session):
    _seed_alice_scores(db_session)
    alice = db_session.scalar(select(Player).where(Player.display_name == "Alice"))
    with pytest.raises(ValueError, match="Confirmation name"):
        purge_player(db_session, alice.id, confirm_name="alice")


def test_purge_removes_roster_memberships(db_session):
    _seed_alice_scores(db_session)
    alice = db_session.scalar(select(Player).where(Player.display_name == "Alice"))
    assert (
        db_session.scalar(
            select(TeamRosterMember).where(TeamRosterMember.player_id == alice.id)
        )
        is not None
    )

    purge_player(db_session, alice.id, confirm_name="Alice")
    db_session.commit()

    assert (
        db_session.scalar(
            select(TeamRosterMember).where(TeamRosterMember.player_id == alice.id)
        )
        is None
    )
