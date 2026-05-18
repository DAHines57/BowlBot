"""Player game history for lookup charts."""

from image_generator import build_player_detail_html
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


def test_build_player_detail_html_includes_chart():
    html = build_player_detail_html(
        page_title="Alice",
        subtitle="Alice · Season 9",
        team="Team A",
        stats_title="Season stats",
        stat_rows=[("Average", "200.0", "gold")],
        game_history=[
            {"score": 210, "week": 1, "game": 1, "season_label": "Season 9", "season_number": 9},
            {"score": 220, "week": 1, "game": 2, "season_label": "Season 9", "season_number": 9},
        ],
        chart_scope="Season 9",
    )
    assert "Recent games" in html
    assert "player-chart" in html
    assert "player-chart-tip" in html
    assert "player-chart-point" in html
    assert "polyline" in html
    assert "wr.width - pad - tipW" in html


def test_build_player_detail_html_chart_includes_league_avg_line():
    html = build_player_detail_html(
        page_title="Alice",
        subtitle="Alice · Season 9",
        team="Team A",
        stats_title="Season stats",
        stat_rows=[("Average", "200.0", "gold")],
        game_history=[
            {"score": 210, "week": 1, "game": 1, "season_label": "Season 9", "season_number": 9},
            {"score": 220, "week": 1, "game": 2, "season_label": "Season 9", "season_number": 9},
        ],
        chart_scope="Season 9",
        league_avg=175.5,
    )
    assert "player-chart-league-avg" in html
    assert "league avg <strong>175.5</strong>" in html
