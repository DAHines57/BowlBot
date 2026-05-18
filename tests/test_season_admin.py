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
from db.team_colors import normalize_color_hex


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


def test_normalize_color_hex():
    assert normalize_color_hex("ff8040") == "#FF8040"
    assert normalize_color_hex("#abc") == "#AABBCC"
    assert normalize_color_hex("") is None
    assert normalize_color_hex("not-a-color") is None


def test_roster_color_round_trip(db_session):
    create_season(db_session, 12)
    save_season_roster(
        db_session,
        12,
        [{"name": "Pins Ahoy", "players": ["Alice"], "color_hex": "#FF5500"}],
    )
    db_session.commit()
    roster = get_season_roster(db_session, 12)
    assert roster["teams"][0]["color_hex"] == "#FF5500"
    team = db_session.scalar(select(Team).where(Team.name == "Pins Ahoy"))
    assert team.color_hex == "#FF5500"

    tid = team.id
    save_season_roster(
        db_session,
        12,
        [
            {
                "id": tid,
                "name": "Pins Ahoy",
                "players": ["Alice"],
                "color_hex": "#00FF00",
            }
        ],
    )
    db_session.commit()
    roster2 = get_season_roster(db_session, 12)
    assert roster2["teams"][0]["color_hex"] == "#00FF00"


def test_remove_player_from_roster_keeps_scored_week(db_session):
    create_season(db_session, 13)
    save_season_roster(
        db_session,
        13,
        [{"name": "Team A", "players": ["Alice", "Bob"]}],
    )
    from db.player_week_writes import save_week_rows

    save_week_rows(
        db_session,
        13,
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
    team = db_session.scalar(select(Team).where(Team.name == "Team A"))
    save_season_roster(
        db_session,
        13,
        [{"id": team.id, "name": "Team A", "players": ["Bob", "Carol"]}],
    )
    db_session.commit()
    alice_row = db_session.scalar(
        select(PlayerWeek).where(
            PlayerWeek.season_id == 13,
            PlayerWeek.week == 1,
            PlayerWeek.player_display_name == "Alice",
        )
    )
    assert alice_row is not None
    assert alice_row.game1 == 200
    bob_row = db_session.scalar(
        select(PlayerWeek).where(
            PlayerWeek.season_id == 13,
            PlayerWeek.week == 1,
            PlayerWeek.player_display_name == "Bob",
        )
    )
    assert bob_row is not None


def test_rename_team_preserves_roster_week_scores(db_session):
    """Renaming via season setup must not clear scores on the roster week."""
    create_season(db_session, 11)
    save_season_roster(
        db_session,
        11,
        [{"name": "Team A", "players": ["Alice"]}],
    )
    from db.player_week_writes import save_week_rows

    save_week_rows(
        db_session,
        11,
        1,
        [
            {
                "team": "Team A",
                "player_display_name": "Alice",
                "game1": 187,
                "game2": 192,
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
        11,
        [{"id": team.id, "name": "Team Alpha", "players": ["Alice"]}],
    )
    db_session.commit()
    pw = db_session.scalar(
        select(PlayerWeek).where(
            PlayerWeek.season_id == 11, PlayerWeek.week == 1, PlayerWeek.team_id == team.id
        )
    )
    assert pw is not None
    assert pw.game1 == 187
    assert pw.game2 == 192


def test_rename_team_retroactive(db_session):
    create_season(db_session, 10)
    save_season_roster(
        db_session,
        10,
        [
            {"name": "Team A", "players": ["Alice"]},
            {"name": "Team B", "players": ["Bob"]},
        ],
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
                "opponent": "Team B",
            }
        ],
    )
    db_session.commit()
    team_a = db_session.scalar(select(Team).where(Team.name == "Team A"))
    team_a_id = team_a.id

    save_season_roster(
        db_session,
        10,
        [
            {"id": team_a_id, "name": "Team Alpha", "players": ["Alice"]},
            {"name": "Team B", "players": ["Bob"]},
        ],
    )
    db_session.commit()

    teams = db_session.scalars(select(Team).where(Team.season_id == 10)).all()
    assert len(teams) == 2
    renamed = db_session.get(Team, team_a_id)
    assert renamed.name == "Team Alpha"

    w2 = db_session.scalars(
        select(PlayerWeek).where(PlayerWeek.season_id == 10, PlayerWeek.week == 2)
    ).all()
    assert len(w2) == 1
    assert w2[0].team_id == team_a_id
    assert w2[0].opponent == "Team B"


def test_clone_season_copies_team_colors(db_session):
    create_season(db_session, 5)
    save_season_roster(
        db_session,
        5,
        [{"name": "Lane Rangers", "players": ["Alice"], "color_hex": "#112233"}],
    )
    db_session.commit()
    create_season(db_session, 6, clone_from=5)
    db_session.commit()
    roster = get_season_roster(db_session, 6)
    assert roster["teams"][0]["color_hex"] == "#112233"
    team = db_session.scalar(
        select(Team)
        .join(Season, Team.season_id == Season.id)
        .where(Season.number == 6, Team.name == "Lane Rangers")
    )
    assert team.color_hex == "#112233"


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
