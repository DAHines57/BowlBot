"""Tests for sub profile stats, display, and delete-on-save."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models import PlayerWeek, Season, Team
from db.player_week_writes import delete_substitute_rows_not_in_save, save_week_rows
from stats.compute import get_player_scores, get_week_matchups, get_week_summary


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _fact(**kwargs):
    base = {
        "season_number": 10,
        "season_label": "Season 10",
        "team": "Team A",
        "player_display_name": "Alice",
        "week": 1,
        "game1": 200.0,
        "game2": 200.0,
        "game3": 200.0,
        "game4": 200.0,
        "game5": None,
        "absent": False,
        "substitute": False,
        "substitute_scores_count": False,
        "substituted_for": None,
        "playoffs": False,
        "opponent": "Team B",
    }
    base.update(kwargs)
    return base


def test_sub_games_count_on_player_profile():
    facts = [
        _fact(
            player_display_name="Jane",
            substitute=True,
            substituted_for="Alice",
            game1=190,
            game2=195,
            game3=185,
            game4=200,
        ),
    ]
    result = get_player_scores(facts, "Jane", "Season 10", season_num=10)
    assert result["player"] == "Jane"
    assert len(result["scores"]) == 4
    assert result["average"] == pytest.approx(192.5)


def test_week_summary_shows_sub_not_double_regular():
    facts = [
        _fact(
            absent=True,
            game1=180,
            game2=180,
            game3=180,
            game4=180,
        ),
        _fact(
            player_display_name="Jane",
            substitute=True,
            substituted_for="Alice",
            substitute_scores_count=True,
            game1=220,
            game2=220,
            game3=220,
            game4=220,
        ),
    ]
    summary = get_week_summary(facts, 1, "Season 10", season_num=10)
    names = [p["name"] for p in summary["players"]]
    assert names.count("Alice") == 1
    assert "Jane" in names
    alice = next(p for p in summary["players"] if p["name"] == "Alice")
    jane = next(p for p in summary["players"] if p["name"] == "Jane")
    assert alice.get("subbed_out") is True
    assert alice["games"][:4] == [180, 180, 180, 180]
    assert alice["avg"] == 180.0
    assert jane.get("is_substitute") is True


def test_week_summary_non_counting_sub_shows_regular_book_avg():
    facts = [
        _fact(
            absent=True,
            game1=180,
            game2=180,
            game3=180,
            game4=180,
        ),
        _fact(
            player_display_name="Jane",
            substitute=True,
            substituted_for="Alice",
            substitute_scores_count=False,
            game1=220,
            game2=220,
            game3=220,
            game4=220,
        ),
    ]
    summary = get_week_summary(facts, 1, "Season 10", season_num=10)
    alice = next(p for p in summary["players"] if p["name"] == "Alice")
    assert alice.get("subbed_out") is not True
    assert alice["games"][:4] == [180, 180, 180, 180]


def test_week_summary_absent_sorts_by_avg_not_last():
    facts = [
        _fact(player_display_name="Bob", game1=210, game2=210, game3=210, game4=210),
        _fact(
            player_display_name="Carol",
            absent=True,
            game1=200,
            game2=200,
            game3=200,
            game4=200,
        ),
        _fact(player_display_name="Dave", game1=190, game2=190, game3=190, game4=190),
    ]
    summary = get_week_summary(facts, 1, "Season 10", season_num=10)
    main_names = [
        p["name"]
        for p in summary["players"]
        if not p.get("is_substitute")
    ]
    assert main_names.index("Bob") < main_names.index("Carol")
    assert main_names.index("Carol") < main_names.index("Dave")


def test_week_summary_html_absent_gets_rank():
    from image_generator import build_html

    facts = [
        _fact(player_display_name="Bob", game1=210, game2=210, game3=210, game4=210),
        _fact(
            player_display_name="Carol",
            absent=True,
            game1=200,
            game2=200,
            game3=200,
            game4=200,
        ),
    ]
    summary = get_week_summary(facts, 1, "Season 10", season_num=10)
    html = build_html(summary)
    assert 'data-orig-rank="2"' in html
    assert "ABSENT" in html


def test_week_matchups_counting_sub_shows_subbed_out_book_scores():
    facts = [
        _fact(
            absent=True,
            game1=180,
            game2=180,
            game3=180,
            game4=180,
        ),
        _fact(
            player_display_name="Jane",
            substitute=True,
            substituted_for="Alice",
            substitute_scores_count=True,
            game1=220,
            game2=220,
            game3=220,
            game4=220,
        ),
    ]
    data = get_week_matchups(facts, 1, "Season 10", season_num=10)
    home = data["matchups"][0]["home"]
    alice = next(p for p in home["players"] if p["name"] == "Alice")
    assert alice.get("subbed_out") is True
    assert alice["games"][:4] == [180, 180, 180, 180]


def test_week_matchups_non_counting_sub_shows_regular_book_avg():
    facts = [
        _fact(
            absent=True,
            game1=180,
            game2=180,
            game3=180,
            game4=180,
        ),
        _fact(
            player_display_name="Jane",
            substitute=True,
            substituted_for="Alice",
            substitute_scores_count=False,
            game1=220,
            game2=220,
            game3=220,
            game4=220,
        ),
    ]
    data = get_week_matchups(facts, 1, "Season 10", season_num=10)
    assert data.get("matchups")
    home = data["matchups"][0]["home"]
    assert home.get("players")
    alice = next(p for p in home["players"] if p["name"] == "Alice")
    jane = next(p for p in home["players"] if p["name"] == "Jane")
    assert alice.get("subbed_out") is not True
    assert alice["games"][:4] == [180, 180, 180, 180]
    assert alice.get("absent") is True
    assert jane.get("is_substitute") is True
    assert jane.get("scores_count") is False
    assert any(g is not None for g in jane["games"])


def test_delete_substitute_rows_not_in_save(db_session):
    season = Season(number=99, label="Season 99", sheet_key="Season 99", sort_order=99)
    db_session.add(season)
    db_session.flush()
    team = Team(season_id=season.id, name="Team A")
    db_session.add(team)
    db_session.flush()

    save_week_rows(
        db_session,
        99,
        1,
        [
            {
                "team": "Team A",
                "player_display_name": "Jane",
                "substitute": True,
                "substituted_for": "Alice",
                "game1": 200,
                "game2": 200,
                "game3": 200,
                "game4": 200,
            }
        ],
    )
    deleted = delete_substitute_rows_not_in_save(
        db_session,
        99,
        1,
        [
            {
                "team": "Team A",
                "player_display_name": "Alice",
                "substitute": False,
                "game1": 180,
                "game2": 180,
                "game3": 180,
                "game4": 180,
                "absent": True,
            }
        ],
    )
    db_session.commit()
    assert deleted == 1
    remaining = db_session.query(PlayerWeek).filter(PlayerWeek.substitute.is_(True)).all()
    assert remaining == []


def test_week_summary_html_shows_substitutes_in_leaderboard():
    from image_generator import build_html

    facts = [
        _fact(absent=True, game1=180, game2=180, game3=180, game4=180),
        _fact(
            player_display_name="Jane",
            substitute=True,
            substituted_for="Alice",
            substitute_scores_count=True,
            game1=220,
            game2=220,
            game3=220,
            game4=220,
        ),
    ]
    summary = get_week_summary(facts, 1, "Season 10", season_num=10)
    html = build_html(summary)
    assert 'data-panel="subs"' not in html
    assert "Jane" in html
    assert "sub-badge" in html
    assert "for Alice" in html or "sub-for-badge" in html
    assert ">180.0<" in html
    assert 'data-orig-rank="2"' in html


def test_matchup_non_counting_players_sorted_last():
    from image_generator import _matchup_player_table_html

    players = [
        {
            "name": "Jane",
            "games": [200, 200, 200, 200],
            "is_substitute": True,
            "scores_count": False,
            "sub_for": "Alice",
        },
        {
            "name": "Bob",
            "games": [210, 210, 210, 210],
            "is_substitute": False,
            "scores_count": True,
        },
        {
            "name": "Alice",
            "games": [180, 180, 180, 180],
            "absent": True,
            "subbed_out": False,
            "is_substitute": False,
            "scores_count": True,
        },
    ]
    html = _matchup_player_table_html(players, 4, away=False)
    bob_pos = html.index("Bob")
    jane_pos = html.index("Jane")
    alice_pos = html.index("Alice")
    assert jane_pos > bob_pos
    assert jane_pos > alice_pos
    assert "player-score-separator" in html
    assert 'class="player-tag player-tag--sub">SUB</span>' in html


def test_league_service_builds_subs_data_from_sub_appearances():
    from league_service import LeagueService

    class FakeData:
        def get_player_scores(self, player_name, season, *, include_substitutes=True):
            if include_substitutes:
                return {
                    "Jane": {
                        "team": "Team B",
                        "sub_appearances": [
                            {
                                "week": 1,
                                "team": "Team B",
                                "game_scores": [220, 210, 200, 215],
                            }
                        ],
                    }
                }
            return {
                "Alice": {
                    "team": "Team A",
                    "average": 200,
                    "highest_game": 220,
                    "lowest_game": 180,
                    "weeks_played": 5,
                    "weeks_absent": 0,
                    "std_dev": 10,
                }
            }

        def get_player_par(self, season):
            return {"Alice": 0}

        def get_league_game_stats(self, season=None, *, all_time=False):
            return {}

    svc = LeagueService(FakeData())
    html, err = svc.players_page("Season 10")
    assert err == ""
    assert "players-subs-toggle" in html
    assert "Jane" in html


def test_best_seasons_excludes_sub_only_players():
    facts = [
        _fact(
            player_display_name="Jane",
            substitute=True,
            substituted_for="Alice",
            game1=250,
            game2=250,
            game3=250,
            game4=250,
        ),
    ]
    roster = get_player_scores(
        facts, season="Season 10", season_num=10, include_substitutes=False
    )
    assert roster == {}
    profile = get_player_scores(
        facts, season="Season 10", season_num=10, include_substitutes=True
    )
    assert "Jane" in profile
    assert profile["Jane"]["sub_appearances"][0]["game_scores"] == [250, 250, 250, 250]
