"""League-wide game stats behind the leaderboard and weekly summaries."""

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
    assert stats["league_avg"] == 157.38
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


def test_get_league_game_stats_season_totals_includes_week():
    facts = [
        _fact("Alice", 5, games=(279, 200, 200, 200)),
        _fact("Bob", 2, games=(91, 100, 100, 100), team="Team B"),
    ]
    stats = get_league_game_stats(facts, season_num=9)
    assert stats["high_game"]["week"] == 5
    assert stats["low_game"]["week"] == 2


def test_get_team_scores_through_week_stops_at_that_week():
    from stats.compute import get_team_scores

    facts = [
        _fact("Alice", 1, games=(200, 200, 200, 200)),
        _fact("Bob", 1, games=(180, 180, 180, 180), team="Team B"),
        _fact("Alice", 2, games=(210, 210, 210, 210)),
        _fact("Bob", 2, games=(190, 190, 190, 190), team="Team B"),
    ]
    data = get_team_scores(facts, season="Season 9", through_week=1, season_num=9)
    assert data["Team A"]["avg_per_game"] == 200
    assert data["Team B"]["avg_per_game"] == 180
    assert data["Team A"]["pins_for"] == 800
