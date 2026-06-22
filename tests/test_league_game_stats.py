"""League-wide game stats for players page and weekly summary."""

from image_generator import build_players_html
from stats.compute import get_league_game_stats, get_week_summary


def _fact(player, week, *, absent=False, games=(200, 200, 200, 200), team="Team A"):
    return {
        "season_number": 9,
        "season_label": "Season 9",
        "week": week,
        "team": team,
        "opponent": "Team B",
        "player_display_name": player,
        "substitute": False,
        "absent": absent,
        "game1": games[0],
        "game2": games[1],
        "game3": games[2],
        "game4": games[3],
        "week_average": sum(games) / len(games),
    }


def test_get_league_game_stats_season_totals():
    facts = [
        _fact("Alice", 1, games=(266, 180, 200, 190)),
        _fact("Bob", 1, games=(93, 120, 110, 100), team="Team B"),
        _fact("Alice", 2, absent=True),
    ]
    stats = get_league_game_stats(facts, season_num=9)
    assert stats["high_game"] == {
        "score": 266,
        "player": "Alice",
        "team": "Team A",
        "week": 1,
    }
    assert stats["low_game"] == {
        "score": 93,
        "player": "Bob",
        "team": "Team B",
        "week": 1,
    }
    assert stats["league_avg"] == 157.4
    assert stats["total_players"] == 2
    assert stats["games_200_plus"] == 2
    assert stats["total_games"] == 8


def test_get_league_game_stats_all_time_includes_season_week():
    facts = [
        _fact("Alice", 1, games=(299, 200, 200, 200)),
        {
            **_fact("Bob", 4, games=(60, 100, 100, 100), team="Team B"),
            "season_number": 10,
            "season_label": "Season 10",
        },
    ]
    stats = get_league_game_stats(facts, exclude_substitutes=True)
    assert stats["high_game"]["season"] == "Season 9"
    assert stats["high_game"]["week"] == 1
    assert stats["low_game"]["season"] == "Season 10"
    assert stats["low_game"]["week"] == 4


def test_build_players_html_all_time_shows_season_week_on_highlights():
    html = build_players_html(
        {"Alice": {"team": "A", "average": 200, "highest_game": 299, "lowest_game": 60, "weeks_played": 5, "weeks_absent": 0, "std_dev": 1}},
        "All Time",
        summary={
            "high_game": {
                "score": 299,
                "player": "Ivan S.",
                "team": "Bowl Jobs",
                "season": "Season 9",
                "week": 3,
            },
            "low_game": {
                "score": 60,
                "player": "Oliver M.",
                "team": "Smoked Bowls",
                "season": "Season 8",
                "week": 12,
            },
            "league_avg": 173.3,
            "total_players": 25,
            "games_200_plus": 16,
            "total_games": 100,
        },
    )
    assert "Season 9 · Week 3" in html
    assert "Season 8 · Week 12" in html
    assert 'class="game-context"' in html


def test_get_week_summary_player_rows_include_low():
    facts = [
        _fact("Alice", 1, games=(266, 180, 200, 190)),
        _fact("Bob", 1, games=(93, 120, 110, 100)),
    ]
    week = get_week_summary(facts, week=1, season="Season 9", season_num=9)
    alice = next(p for p in week["players"] if p["name"] == "Alice")
    bob = next(p for p in week["players"] if p["name"] == "Bob")
    assert alice["low"] == 180
    assert bob["low"] == 93


def test_build_week_summary_html_has_low_column():
    from image_generator import build_html

    html = build_html(
        {
            "season": "Season 9",
            "week": 1,
            "players": [
                {
                    "name": "Alice",
                    "team": "Team A",
                    "avg": 209.0,
                    "high": 266,
                    "low": 180,
                    "absent": False,
                }
            ],
            "high_game": {"score": 266, "player": "Alice", "team": "Team A"},
            "low_game": {"score": 93, "player": "Bob", "team": "Team B"},
            "league_avg": 175.0,
            "total_players": 1,
            "games_200_plus": 3,
            "total_games": 4,
        }
    )
    assert "Low Game" in html
    assert 'data-sort-col="5"' in html
    assert ">Low<" in html


def test_get_week_summary_uses_same_league_stats():
    facts = [
        _fact("Alice", 3, games=(220, 210, 205, 215)),
        _fact("Bob", 3, games=(150, 160, 155, 145)),
    ]
    week = get_week_summary(facts, week=3, season="Season 9", season_num=9)
    league = get_league_game_stats(facts, season_num=9, week=3)
    assert week["high_game"] == league["high_game"]
    assert week["total_games"] == league["total_games"]
    assert week["total_players"] == 2


def test_build_players_html_season_shows_week_on_highlights():
    html = build_players_html(
        {"Alice": {"team": "A", "average": 200, "highest_game": 220, "lowest_game": 180, "weeks_played": 3, "weeks_absent": 0, "std_dev": 1}},
        "Season 9",
        summary={
            "high_game": {
                "score": 266,
                "player": "Rafa A.",
                "team": "The Replacements",
                "week": 5,
            },
            "low_game": {
                "score": 93,
                "player": "Erik C.",
                "team": "Loaded Bowlers",
                "week": 2,
            },
            "league_avg": 173.3,
            "total_players": 25,
            "games_200_plus": 16,
            "total_games": 100,
        },
    )
    assert "Week 5" in html
    assert "Week 2" in html
    assert "Season 9 · Week" not in html


def test_build_players_html_shows_league_summary_blocks():
    html = build_players_html(
        {"Alice": {"team": "A", "average": 200, "highest_game": 220, "lowest_game": 180, "weeks_played": 3, "weeks_absent": 0, "std_dev": 1}},
        "Season 9",
        summary={
            "high_game": {"score": 266, "player": "Rafa A.", "team": "The Replacements"},
            "low_game": {"score": 93, "player": "Erik C.", "team": "Loaded Bowlers"},
            "league_avg": 173.3,
            "total_players": 25,
            "games_200_plus": 16,
            "total_games": 100,
        },
    )
    assert "HIGH GAME" in html or "High Game" in html
    assert "266" in html
    assert "LEAGUE STATS" in html or "League Stats" in html
    assert "173.3" in html
    assert "200+ GAMES" in html or "200+ Games" in html


def test_get_league_game_stats_season_totals_includes_week():
    facts = [
        _fact("Alice", 5, games=(279, 200, 200, 200)),
        _fact("Bob", 2, games=(91, 100, 100, 100), team="Team B"),
    ]
    stats = get_league_game_stats(facts, season_num=9)
    assert stats["high_game"]["week"] == 5
    assert stats["low_game"]["week"] == 2


def test_build_teams_html_through_week_subtitle():
    from image_generator import build_teams_html
    from stats.compute import get_team_scores

    facts = [
        _fact("Alice", 1, games=(200, 200, 200, 200)),
        _fact("Bob", 1, games=(180, 180, 180, 180), team="Team B"),
        _fact("Alice", 2, games=(210, 210, 210, 210)),
        _fact("Bob", 2, games=(190, 190, 190, 190), team="Team B"),
    ]
    data = get_team_scores(facts, season="Season 9", through_week=1, season_num=9)
    html = build_teams_html(
        data, "Season 9", subtitle="Season 9 &nbsp;·&nbsp; through week 1"
    )
    assert "through week 1" in html
    assert "Standings" in html
    assert "Team A" in html
