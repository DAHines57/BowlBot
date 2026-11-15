"""DB sync for week matchup overrides."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.matchup_override_writes import sync_week_matchup_overrides
from db.models import MatchupOverride
from db.season_admin import create_season


@pytest.fixture
def db_session():
    # Match production: autoflush=False (see db/session.py).
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


def test_sync_upserts_pair_and_clears(db_session):
    create_season(db_session, 14)
    db_session.commit()

    sync_week_matchup_overrides(
        db_session,
        14,
        3,
        {"Team A": "3-2"},
        team_opponents={"Team A": "Team B", "Team B": "Team A"},
        playoffs=False,
    )
    db_session.commit()

    rows = {
        r.team: r
        for r in db_session.scalars(select(MatchupOverride)).all()
    }
    assert rows["Team A"].wins == 3 and rows["Team A"].losses == 2
    assert rows["Team B"].wins == 2 and rows["Team B"].losses == 3

    sync_week_matchup_overrides(
        db_session,
        14,
        3,
        {"Team A": None},
        team_opponents={"Team A": "Team B", "Team B": "Team A"},
    )
    db_session.commit()
    assert db_session.scalars(select(MatchupOverride)).all() == []


def test_sync_both_sides_mirrored_no_integrity_error(db_session):
    """Admin UI mirrors inverse codes onto both teams; must not double-insert."""
    create_season(db_session, 14)
    db_session.commit()

    sync_week_matchup_overrides(
        db_session,
        14,
        5,
        {"Team A": "3-2", "Team B": "2-3"},
        team_opponents={"Team A": "Team B", "Team B": "Team A"},
        playoffs=False,
    )
    db_session.commit()

    rows = {
        r.team: r
        for r in db_session.scalars(select(MatchupOverride)).all()
    }
    assert set(rows) == {"Team A", "Team B"}
    assert rows["Team A"].wins == 3 and rows["Team A"].losses == 2
    assert rows["Team B"].wins == 2 and rows["Team B"].losses == 3


def test_sync_override_without_opponent_raises(db_session):
    create_season(db_session, 14)
    db_session.commit()

    with pytest.raises(ValueError, match="needs an opponent"):
        sync_week_matchup_overrides(
            db_session,
            14,
            3,
            {"Team A": "3-2"},
            team_opponents={},
        )
