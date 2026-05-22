"""Stats ignore blank template rows and respect roster week windows."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.facts_loader import load_all_facts
from db.models import PlayerWeek
from db.season_admin import create_season, save_season_roster
from stats import compute
from stats.facts import fact_counts_for_stats


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_future_starter_not_in_player_scores(db_session):
    create_season(db_session, 30)
    save_season_roster(
        db_session,
        30,
        [{"name": "Team A", "players": ["Alice"]}],
        roster_week=1,
    )
    from db.player_week_writes import save_week_rows

    save_week_rows(
        db_session,
        30,
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
        30,
        [{"id": team.id, "name": "Team A", "players": ["Alice", "Bababooey"]}],
        roster_week=2,
    )
    db_session.commit()
    facts = load_all_facts(db_session)
    scores = compute.get_player_scores(facts, season="Season 30")
    assert "Bababooey" not in scores
    assert "Alice" in scores
    bob_rows = db_session.scalars(
        select(PlayerWeek).where(PlayerWeek.player_display_name == "Bababooey")
    ).all()
    assert len(bob_rows) == 0


def test_blank_template_fact_filtered():
    f = {
        "season_number": 10,
        "week": 2,
        "team": "A",
        "player_display_name": "Bob",
        "substitute": False,
        "absent": False,
        "roster_started_week": 2,
        "roster_ended_week": None,
        "game1": None,
        "game2": None,
    }
    assert fact_counts_for_stats(f) is False
