"""Per-game absent flags (book average) vs whole-week absent."""

import pytest

from stats.compute import get_player_scores, get_week_matchups
from stats.facts import games_list_for_player_stats, games_list_for_team


def _fact(
    player,
    week,
    *,
    absent=False,
    games=(200, 210, 205, 215),
    game_absent=None,
):
    g = list(games)
    while len(g) < 5:
        g.append(None)
    flags = game_absent or [False] * 5
    return {
        "season_number": 10,
        "season_label": "Season 10",
        "week": week,
        "team": "Team A",
        "opponent": "Team B",
        "player_display_name": player,
        "substitute": False,
        "absent": absent,
        "game1": g[0],
        "game2": g[1],
        "game3": g[2],
        "game4": g[3],
        "game5": g[4],
        "game1_absent": flags[0],
        "game2_absent": flags[1],
        "game3_absent": flags[2],
        "game4_absent": flags[3],
        "game5_absent": flags[4],
    }


def test_games_list_splits_team_vs_player():
    f = _fact("Alice", 5, games=(180, 200, 210, 205, None), game_absent=[True, False, False, False, False])
    assert games_list_for_team(f) == [180, 200, 210, 205]
    assert games_list_for_player_stats(f) == [200, 210, 205]


def test_player_season_average_excludes_book_avg_game():
    facts = [
        _fact("Alice", 1, games=(200, 200, 200, 200)),
        _fact(
            "Alice",
            2,
            games=(190, 220, 210, 200),
            game_absent=[True, False, False, False, False],
        ),
    ]
    data = get_player_scores(facts, season="Season 10", season_num=10)
    # 4 + 3 bowled games; book 190 excluded
    expected = (200 * 4 + 220 + 210 + 200) / 7
    assert data["Alice"]["average"] == pytest.approx(expected, rel=1e-3)


def test_matchup_game_pins_use_slot_index():
    facts = [
        _fact("Alice", 1, games=(190, 220, 210, 200), game_absent=[True, False, False, False, False]),
        _fact("Bob", 1, games=(200, 200, 200, 200)),
    ]
    out = get_week_matchups(facts, week=1, season_num=10)
    team_a = next(m for m in out["matchups"] if m["home"]["name"] == "Team A")
    assert team_a["home"]["game_pins"] == [390, 420, 410, 400]


def test_matchup_players_include_per_game_absent_flags():
    def _fact_b(player, games):
        f = _fact(player, 1, games=games)
        f["team"] = "Team B"
        f["opponent"] = "Team A"
        return f

    facts = [
        _fact("Alice", 1, games=(190, 220, 210, 200), game_absent=[True, False, False, False, False]),
        _fact("Bob", 1, games=(200, 200, 200, 200)),
        _fact_b("Carol", (195, 195, 195, 195)),
        _fact_b("Dave", (205, 205, 205, 205)),
    ]
    out = get_week_matchups(facts, week=1, season_num=10)
    team_a = next(m for m in out["matchups"] if m["home"]["name"] == "Team A")
    assert team_a.get("away")
    alice = next(p for p in team_a["home"]["players"] if p["name"] == "Alice")
    bob = next(p for p in team_a["home"]["players"] if p["name"] == "Bob")
    assert alice["game_absent"] == [True, False, False, False, False]
    assert bob["game_absent"] == [False] * 5


def test_matchup_html_marks_missed_game_score_red():
    from image_generator import _matchup_game_cells_html

    html = _matchup_game_cells_html(
        [186, 221, 229, 163],
        4,
        [True, False, False, False],
    )
    assert "pst-score--miss" in html
    assert html.count("pst-score--miss") == 1
    assert "186" in html


def test_team_game_breakdown_flags_missed_slot():
    from stats.compute import _attach_team_game_players, _team_game_players_index

    facts = [
        _fact("Alice", 1, games=(190, 220, 210, 200), game_absent=[True, False, False, False, False]),
        _fact("Bob", 1, games=(200, 200, 200, 200)),
    ]
    index = _team_game_players_index(facts)
    players = index[("Team A", 1, 1)]
    assert players["Alice"]["missed_game"] is True
    assert players["Alice"]["value"] == 190
    assert players["Bob"]["missed_game"] is False


def test_team_week_breakdown_lists_missed_games():
    from stats.compute import _team_week_players_index

    facts = [
        _fact(
            "Alice",
            1,
            games=(190, 220, 210, 200),
            game_absent=[True, False, True, False, False],
        ),
        _fact("Bob", 1, games=(200, 200, 200, 200)),
    ]
    index = _team_week_players_index(facts)
    alice = index[("Team A", 1)]["Alice"]
    assert alice["missed_games"] == [1, 3]
    assert index[("Team A", 1)]["Bob"].get("missed_games") is None


def test_team_week_roster_html_shows_abs_game_tags():
    from image_generator import _team_roster_detail_html

    html = _team_roster_detail_html(
        {
            "Alice": {
                "absent": False,
                "value": 205.0,
                "missed_games": [1, 3],
            },
            "Bob": {"absent": True, "value": 200.0},
        }
    )
    assert "ABS G1,3" in html
    assert html.count("player-tag") == 1
    assert 'class="absent-badge">ABS</span>' in html


def test_team_roster_html_marks_missed_game_red():
    from image_generator import _team_roster_detail_html

    html = _team_roster_detail_html(
        {
            "Alice": {"absent": False, "value": 186.0, "missed_game": True},
            "Bob": {"absent": False, "value": 200.0, "missed_game": False},
        }
    )
    assert "team-roster-avg--miss" in html
    assert html.count("team-roster-avg--miss") == 1
    assert "186" in html


def test_whole_week_absent_still_excludes_player_average():
    facts = [
        _fact("Alice", 1, games=(200, 200, 200, 200), absent=True),
    ]
    data = get_player_scores(facts, season="Season 10", season_num=10)
    assert data["Alice"]["average"] == 0
    assert data["Alice"]["weeks_absent"] == 1
