"""Player absence counts."""

from stats.compute import get_all_time_stats, get_player_scores


def _fact(player, week, *, absent=False, games=(200, 200, 200, 200)):
    return {
        "season_number": 9,
        "season_label": "Season 9",
        "week": week,
        "team": "Team A",
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


def test_get_player_scores_counts_absences_per_season():
    facts = [
        _fact("Alice", 1),
        _fact("Alice", 2, absent=True),
        _fact("Alice", 3),
    ]
    data = get_player_scores(facts, season="Season 9", season_num=9)
    assert data["Alice"]["weeks_absent"] == 1
    assert data["Alice"]["weeks_played"] == 2


def test_get_all_time_stats_sums_absences_across_weeks():
    facts = [
        _fact("Alice", 1),
        _fact("Alice", 2, absent=True),
        _fact("Alice", 3, absent=True),
    ]
    stats = get_all_time_stats(facts)
    alice = next(p for p in stats["player_averages"] if p["player"] == "Alice")
    assert alice["absences"] == 2
