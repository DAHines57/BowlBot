"""Player game history behind the profile chart."""

from stats.compute import get_player_game_history


def _fact(player, week, *, absent=False, season=9, games=(200, 210, 205, 215)):
    return {
        "season_number": season,
        "season_label": f"Season {season}",
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


def test_get_player_game_history_season_under_limit():
    facts = [_fact("Alice", w, games=(150 + w, 160 + w, 170 + w, 180 + w)) for w in range(1, 6)]
    hist = get_player_game_history(facts, "Alice", "Season 9", season_num=9, limit=30)
    assert len(hist) == 20  # 5 weeks * 4 games
    assert hist[-1]["week"] == 5
    assert hist[-1]["score"] == 180 + 5


def test_get_player_game_history_caps_at_30():
    facts = [_fact("Alice", w) for w in range(1, 15)]
    hist = get_player_game_history(facts, "Alice", "Season 9", season_num=9, limit=30)
    assert len(hist) == 30
    # 14 weeks * 4 games = 56; last 30 begin at week 7 game 3
    assert hist[0]["week"] == 7
    assert hist[0]["game"] == 3
    assert hist[-1]["week"] == 14


def test_get_player_game_history_all_time_cross_season():
    facts = [
        _fact("Alice", 1, season=8, games=(100, 100, 100, 100)),
        _fact("Alice", 1, season=9, games=(200, 200, 200, 200)),
    ]
    hist = get_player_game_history(facts, "Alice", season=None, limit=30)
    assert len(hist) == 8
    assert hist[-1]["score"] == 200
    assert hist[0]["season_number"] == 8


def test_get_player_game_history_marks_substitute_games():
    facts = [
        _fact("Alice", 1),
        {
            **_fact("Alice", 2),
            "substitute": True,
            "substituted_for": "Bob",
            "game1": 230,
            "game2": 225,
            "game3": 220,
            "game4": 215,
        },
    ]
    hist = get_player_game_history(facts, "Alice", "Season 9", season_num=9, limit=30)
    regular = [g for g in hist if not g.get("is_substitute")]
    sub = [g for g in hist if g.get("is_substitute")]
    assert len(regular) == 4
    assert len(sub) == 4
    assert sub[0]["week"] == 2
    assert sub[0]["score"] == 230


def test_get_player_game_history_keeps_missed_games_with_real_slots():
    """A missed game still has a score taken for it, so it stays in the history."""
    facts = [{**_fact("Alice", 1, games=(150, 200, 210, 220)), "game1_absent": True}]
    hist = get_player_game_history(facts, "Alice", "Season 9", season_num=9, limit=30)

    assert [g["score"] for g in hist] == [150, 200, 210, 220]
    assert [g["game"] for g in hist] == [1, 2, 3, 4]
    assert hist[0]["game_absent"] is True
    assert not any(g["game_absent"] for g in hist[1:])


def test_whole_week_absence_overrides_per_game_flags():
    facts = [{**_fact("Alice", 1, absent=True), "game1_absent": True}]
    assert get_player_game_history(facts, "Alice", "Season 9", season_num=9) == []
