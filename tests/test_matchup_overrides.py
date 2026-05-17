"""Tests for matchup_overrides in stats."""
from placement_bracket import winner_loser_from_matchup
from stats.compute import get_team_scores
from stats.matchup_overrides import find_matchup_override, result_from_wlt, sides_from_overrides


def test_result_from_wlt():
    assert result_from_wlt(3, 2) == "W"
    assert result_from_wlt(2, 3) == "L"
    assert result_from_wlt(2, 2, 1) == "T"


def test_sides_from_overrides_home_only():
    home = {"wins": 3, "losses": 2, "ties": 0}
    h_w, h_l, h_t, a_w, a_l, a_t, hr, ar = sides_from_overrides(
        "A", "B", home, None
    )
    assert (h_w, h_l, h_t) == (3, 2, 0)
    assert (a_w, a_l, a_t) == (2, 3, 0)
    assert hr == "W" and ar == "L"


def test_winner_loser_tiebreak_on_pins():
    m = {
        "home": {"name": "Gutter", "result": "T", "pins": 8200, "game_pins": [2100, 2050, 2050, 2000]},
        "away": {"name": "Splittin", "result": "T", "pins": 7900, "game_pins": [2000, 1950, 1950, 2000]},
    }
    wl = winner_loser_from_matchup(m)
    assert wl == ("Gutter", "Splittin")


def test_find_matchup_override():
    rows = [
        {
            "season_number": 9,
            "week": 3,
            "team": "Pin Seekers",
            "opponent": "Other",
            "wins": 3,
            "losses": 2,
            "ties": 0,
        }
    ]
    hit = find_matchup_override(rows, season_num=9, week=3, team="pin seekers")
    assert hit is not None
    assert hit["wins"] == 3


def test_get_team_scores_uses_override_when_pins_would_differ():
    """Standings W/L come from overrides, not per-game pin comparison."""
    facts = [
        {
            "season_number": 9,
            "season_label": "Season 9",
            "week": 1,
            "team": "Team A",
            "opponent": "Team B",
            "player_display_name": "Alice",
            "substitute": False,
            "absent": False,
            "game1": 200,
            "game2": 200,
            "game3": 200,
            "game4": 200,
        },
        {
            "season_number": 9,
            "season_label": "Season 9",
            "week": 1,
            "team": "Team B",
            "opponent": "Team A",
            "player_display_name": "Bob",
            "substitute": False,
            "absent": False,
            "game1": 100,
            "game2": 100,
            "game3": 100,
            "game4": 100,
        },
    ]
    overrides = [
        {
            "season_number": 9,
            "week": 1,
            "team": "Team A",
            "opponent": "Team B",
            "wins": 1,
            "losses": 4,
            "ties": 0,
        },
        {
            "season_number": 9,
            "week": 1,
            "team": "Team B",
            "opponent": "Team A",
            "wins": 4,
            "losses": 1,
            "ties": 0,
        },
    ]
    data = get_team_scores(
        facts, season="Season 9", season_num=9, matchup_overrides=overrides
    )
    assert data["Team A"]["wins"] == 1
    assert data["Team A"]["losses"] == 4
    assert data["Team A"]["record_overridden"] is True
    assert data["Team A"]["record_override_mark"] is True
    assert data["Team B"]["wins"] == 4
    assert data["Team B"]["losses"] == 1


def test_get_team_scores_override_without_roster_opponent_name():
    """Override opponent hint is used when facts omit opponent."""
    facts = [
        {
            "season_number": 9,
            "season_label": "Season 9",
            "week": 2,
            "team": "Team A",
            "opponent": None,
            "player_display_name": "Alice",
            "substitute": False,
            "absent": False,
            "game1": 150,
            "game2": 150,
            "game3": 150,
            "game4": 150,
        },
        {
            "season_number": 9,
            "season_label": "Season 9",
            "week": 2,
            "team": "Team B",
            "opponent": "Team A",
            "player_display_name": "Bob",
            "substitute": False,
            "absent": False,
            "game1": 160,
            "game2": 160,
            "game3": 160,
            "game4": 160,
        },
    ]
    overrides = [
        {
            "season_number": 9,
            "week": 2,
            "team": "Team A",
            "opponent": "Team B",
            "wins": 3,
            "losses": 2,
            "ties": 0,
        },
    ]
    data = get_team_scores(
        facts, season="Season 9", season_num=9, matchup_overrides=overrides
    )
    assert data["Team A"]["wins"] == 3
    assert data["Team A"]["losses"] == 2
    assert data["Team A"]["record_overridden"] is True
    assert data["Team A"]["record_override_mark"] is True


def test_record_override_mark_skips_playoff_weeks():
    facts = [
        {
            "season_number": 9,
            "season_label": "Season 9",
            "week": 8,
            "team": "Team A",
            "opponent": "Team B",
            "playoffs": True,
            "player_display_name": "Alice",
            "substitute": False,
            "absent": False,
            "game1": 200,
            "game2": 200,
            "game3": 200,
            "game4": 200,
        },
        {
            "season_number": 9,
            "season_label": "Season 9",
            "week": 8,
            "team": "Team B",
            "opponent": "Team A",
            "playoffs": True,
            "player_display_name": "Bob",
            "substitute": False,
            "absent": False,
            "game1": 100,
            "game2": 100,
            "game3": 100,
            "game4": 100,
        },
    ]
    overrides = [
        {
            "season_number": 9,
            "week": 8,
            "team": "Team A",
            "opponent": "Team B",
            "wins": 1,
            "losses": 4,
            "ties": 0,
            "playoffs": True,
        },
    ]
    data = get_team_scores(
        facts, season="Season 9", season_num=9, matchup_overrides=overrides
    )
    assert data["Team A"]["wins"] == 1
    assert data["Team A"]["record_overridden"] is True
    assert data["Team A"]["record_override_mark"] is False
