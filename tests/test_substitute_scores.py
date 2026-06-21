"""Tests for substitute score entry and team-pin counting."""
from league_admin import parse_week_rows_payload
from stats.compute import get_team_scores
from stats.facts import fact_counts_for_team_pins


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


def test_parse_week_rows_payload_substitute_row():
    rows, err = parse_week_rows_payload(
        {
            "rows": [
                {
                    "team": "Team A",
                    "player_display_name": "Alice",
                    "game1": 180,
                    "game2": 180,
                    "game3": 180,
                    "game4": 180,
                    "absent": True,
                },
                {
                    "team": "Team A",
                    "player_display_name": "Jane",
                    "game1": 190,
                    "game2": 195,
                    "game3": 185,
                    "game4": 200,
                    "substitute": True,
                    "substituted_for": "Alice",
                    "substitute_scores_count": False,
                },
            ],
        }
    )
    assert err is None
    assert rows[1]["substitute"] is True
    assert rows[1]["substituted_for"] == "Alice"
    assert rows[1]["substitute_scores_count"] is False


def test_parse_week_rows_payload_substitute_requires_sub_for():
    _, err = parse_week_rows_payload(
        {
            "rows": [
                {"team": "Team A", "player_display_name": "Alice", "game1": 200},
                {
                    "team": "Team A",
                    "player_display_name": "Jane",
                    "game1": 190,
                    "substitute": True,
                },
            ],
        }
    )
    assert err is not None
    assert "substituted_for" in err


def test_parse_week_rows_payload_duplicate_sub_for_rejected():
    _, err = parse_week_rows_payload(
        {
            "rows": [
                {"team": "Team A", "player_display_name": "Alice", "game1": 200},
                {"team": "Team A", "player_display_name": "Bob", "game1": 200},
                {
                    "team": "Team A",
                    "player_display_name": "Jane",
                    "game1": 190,
                    "substitute": True,
                    "substituted_for": "Alice",
                },
                {
                    "team": "Team A",
                    "player_display_name": "John",
                    "game1": 185,
                    "substitute": True,
                    "substituted_for": "Alice",
                },
            ],
        }
    )
    assert err is not None
    assert "duplicate" in err.lower()


def test_fact_counts_for_team_pins_sub_not_counting():
    repl = {"Alice"}
    assert fact_counts_for_team_pins(_fact(substitute=True), replaced_by_counting_sub=repl) is False
    assert (
        fact_counts_for_team_pins(
            _fact(substitute=True, substitute_scores_count=True),
            replaced_by_counting_sub=repl,
        )
        is True
    )


def test_fact_counts_for_team_pins_excludes_replaced_regular():
    repl = {"Alice"}
    assert fact_counts_for_team_pins(_fact(), replaced_by_counting_sub=repl) is False
    assert fact_counts_for_team_pins(_fact(player_display_name="Bob"), replaced_by_counting_sub=repl) is True


def test_get_team_scores_uses_regular_average_when_sub_not_counting():
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
    result = get_team_scores(facts, team_name="Team A", season="Season 10", week=1, season_num=10)
    assert result["week_data"]["total"] == 720


def test_get_team_scores_uses_sub_when_counting():
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
    result = get_team_scores(facts, team_name="Team A", season="Season 10", week=1, season_num=10)
    assert result["week_data"]["total"] == 880
