"""Roster display for a specific week."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.season_admin import create_season, get_season_roster, save_season_roster


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_roster_at_week_excludes_future_starter(db_session):
    create_season(db_session, 31)
    save_season_roster(
        db_session,
        31,
        [{"name": "Team A", "players": ["Alice"]}],
        roster_week=1,
    )
    from db.player_week_writes import save_week_rows

    save_week_rows(
        db_session,
        31,
        1,
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
    from db.models import Team

    team = db_session.scalar(select(Team).where(Team.name == "Team A"))
    save_season_roster(
        db_session,
        31,
        [{"id": team.id, "name": "Team A", "players": ["Alice", "Bababooey"]}],
        roster_week=2,
    )
    db_session.commit()

    w1 = get_season_roster(db_session, 31, view_week=1)
    w2 = get_season_roster(db_session, 31, view_week=2)
    assert w1 is not None and w2 is not None
    assert w1["teams"][0]["players"] == ["Alice"]
    assert w2["teams"][0]["players"] == ["Alice", "Bababooey"]


def test_week_view_includes_player_week_row_even_if_membership_starts_later(db_session):
    """Week 1 roster shows anyone who bowled week 1, not only membership started_week."""
    create_season(db_session, 32)
    save_season_roster(
        db_session,
        32,
        [{"name": "Team A", "players": ["Alice", "Lalo"]}],
        roster_week=1,
    )
    from db.models import Player, Team, TeamRosterMember
    from db.player_week_writes import save_week_rows

    save_week_rows(
        db_session,
        32,
        1,
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
            },
            {
                "team": "Team A",
                "player_display_name": "Lalo",
                "game1": 180,
                "game2": None,
                "game3": None,
                "game4": None,
                "game5": None,
                "absent": False,
                "substitute": False,
                "playoffs": False,
                "opponent": None,
            },
        ],
    )
    team = db_session.scalar(select(Team).where(Team.name == "Team A"))
    lalo = db_session.scalar(select(Player).where(Player.display_name == "Lalo"))
    member = db_session.scalar(
        select(TeamRosterMember).where(
            TeamRosterMember.team_id == team.id,
            TeamRosterMember.player_id == lalo.id,
        )
    )
    member.started_week = 2
    db_session.commit()

    w1 = get_season_roster(db_session, 32, view_week=1)
    assert "Lalo" in w1["teams"][0]["players"]
