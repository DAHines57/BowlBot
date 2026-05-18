"""Tests for season admin (create roster, delete)."""
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models import PlayerWeek, Season, Team
from db.season_admin import (
    create_season,
    delete_week,
    get_season_roster,
    save_season_roster,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_season_and_roster(db_session):
    create_season(db_session, 14)
    save_season_roster(
        db_session,
        14,
        [
            {"name": "Pins Ahoy", "players": ["Alice", "Bob"]},
            {"name": "Lane Rangers", "players": ["Carl"]},
        ],
    )
    db_session.commit()
    roster = get_season_roster(db_session, 14)
    assert roster is not None
    assert len(roster["teams"]) == 2
    assert roster["teams"][0]["players"]


def test_delete_week_keeps_other_weeks(db_session):
    create_season(db_session, 10)
    save_season_roster(
        db_session,
        10,
        [{"name": "Team A", "players": ["Alice"]}],
    )
    from db.player_week_writes import save_week_rows

    save_week_rows(
        db_session,
        10,
        2,
        [
            {
                "team": "Team A",
                "player_display_name": "Alice",
                "game1": 200,
                "game2": None,
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
    delete_week(db_session, 10, 2)
    db_session.commit()
    w1 = db_session.scalars(select(PlayerWeek.week).where(PlayerWeek.season_id == 10)).all()
    assert 1 in w1
    assert 2 not in w1


def test_delete_season_cascades_teams(db_session):
    create_season(db_session, 14)
    save_season_roster(
        db_session,
        14,
        [{"name": "All about the Pinjamins", "players": ["Alice", "Bob"]}],
    )
    db_session.commit()
    team_count = db_session.scalar(
        select(func.count()).select_from(Team).where(Team.season_id == 14)
    )
    assert team_count == 1

    from db.season_admin import delete_season

    delete_season(db_session, 14)
    db_session.commit()
    assert db_session.scalar(select(Season).where(Season.number == 14)) is None
    assert (
        db_session.scalar(select(func.count()).select_from(Team).where(Team.season_id == 14))
        == 0
    )
