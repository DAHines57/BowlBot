"""Tests for team_roster_members table and admin integration."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models import Player, Team, TeamRosterMember
from db.roster_members import backfill_season_roster
from db.season_admin import create_season, get_season_roster, save_season_roster


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_save_roster_creates_memberships(db_session):
    create_season(db_session, 20)
    save_season_roster(
        db_session,
        20,
        [{"name": "Team A", "players": ["Alice", "Bob"]}],
    )
    db_session.commit()
    members = db_session.scalars(select(TeamRosterMember)).all()
    assert len(members) == 2
    assert all(m.active for m in members)
    assert all(m.ended_week is None for m in members)

    roster = get_season_roster(db_session, 20)
    assert roster is not None
    assert set(roster["teams"][0]["players"]) == {"Alice", "Bob"}


def test_remove_player_deactivates_membership(db_session):
    create_season(db_session, 21)
    save_season_roster(
        db_session,
        21,
        [{"name": "Team A", "players": ["Alice", "Bob"]}],
    )
    db_session.commit()
    from db.models import Team

    t = db_session.scalar(select(Team).where(Team.name == "Team A"))
    save_season_roster(
        db_session,
        21,
        [{"id": t.id, "name": "Team A", "players": ["Bob"]}],
    )
    db_session.commit()
    alice = db_session.scalar(
        select(TeamRosterMember)
        .join(Player, TeamRosterMember.player_id == Player.id)
        .where(Player.display_name == "Alice")
    )
    assert alice is not None
    assert alice.active is False
    assert alice.ended_week == 1
    roster = get_season_roster(db_session, 21)
    assert "Alice" not in roster["teams"][0]["players"]


def test_captain_round_trip(db_session):
    create_season(db_session, 22)
    save_season_roster(
        db_session,
        22,
        [{"name": "Team A", "players": ["Alice", "Bob"], "captain": "Alice"}],
    )
    db_session.commit()
    roster = get_season_roster(db_session, 22)
    assert roster["teams"][0]["captain"] == "Alice"


def test_mid_season_add_player_uses_latest_week(db_session):
    create_season(db_session, 24)
    save_season_roster(db_session, 24, [{"name": "Team A", "players": ["Alice"]}])
    from db.player_week_writes import save_week_rows

    for week in (1, 2):
        save_week_rows(
            db_session,
            24,
            week,
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
    team = db_session.scalar(select(Team).where(Team.name == "Team A"))
    save_season_roster(
        db_session,
        24,
        [{"id": team.id, "name": "Team A", "players": ["Alice", "Bob"]}],
        roster_week=2,
    )
    db_session.commit()
    bob = db_session.scalar(
        select(TeamRosterMember)
        .join(Player, TeamRosterMember.player_id == Player.id)
        .where(Player.display_name == "Bob")
    )
    assert bob is not None
    assert bob.started_week == 2
    assert bob.active is True
    from db.models import PlayerWeek

    bob_pw = db_session.scalar(
        select(PlayerWeek).where(
            PlayerWeek.player_display_name == "Bob", PlayerWeek.week == 2
        )
    )
    assert bob_pw is not None


def test_remove_at_effective_week_ends_prior_week(db_session):
    create_season(db_session, 25)
    save_season_roster(db_session, 25, [{"name": "Team A", "players": ["Alice", "Bob"]}])
    from db.player_week_writes import save_week_rows

    for week in (1, 2, 3, 4, 5, 6, 7):
        save_week_rows(
            db_session,
            25,
            week,
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
    team = db_session.scalar(select(Team).where(Team.name == "Team A"))
    save_season_roster(
        db_session,
        25,
        [{"id": team.id, "name": "Team A", "players": ["Alice", "Carol"]}],
        roster_week=8,
    )
    db_session.commit()
    bob = db_session.scalar(
        select(TeamRosterMember)
        .join(Player, TeamRosterMember.player_id == Player.id)
        .where(Player.display_name == "Bob")
    )
    carol = db_session.scalar(
        select(TeamRosterMember)
        .join(Player, TeamRosterMember.player_id == Player.id)
        .where(Player.display_name == "Carol")
    )
    assert bob.ended_week == 7
    assert bob.active is False
    assert carol.started_week == 8
    assert carol.active is True


def test_backfill_from_player_weeks(db_session):
    create_season(db_session, 23)
    save_season_roster(
        db_session,
        23,
        [{"name": "Team A", "players": ["Alice"]}],
    )
    db_session.execute(TeamRosterMember.__table__.delete())
    db_session.commit()
    from db.models import Season

    season = db_session.scalar(select(Season).where(Season.number == 23))
    n = backfill_season_roster(db_session, season.id)
    db_session.commit()
    assert n >= 1
    roster = get_season_roster(db_session, 23)
    assert roster["teams"][0]["players"] == ["Alice"]
