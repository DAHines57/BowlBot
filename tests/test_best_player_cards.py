"""Best player scores hub: mobile cards + Best seasons only for all-time."""

from image_generator import build_top_player_scores_hub_html


def test_build_top_player_scores_hub_has_cards_per_panel():
    games = [("Alice", "Team A", 1, 220, False)]
    weeks = [("Alice", "Team A", 1, 800, 4, False)]
    # Single-season hub: Best seasons tab is hidden.
    html = build_top_player_scores_hub_html(games, weeks, "Season 9", 10)
    assert html.count("score-card") >= 2
    assert "player-scores-section" in html
    assert 'data-sort-kind="games"' in html
    assert 'data-sort-kind="weeks"' in html
    assert 'data-default-sort="avg"' in html
    assert '<option value="avg" selected>Avg</option>' in html
    assert "Best seasons" not in html
    assert 'data-view-tab="averages"' not in html

    # All-time hub: Best seasons tab is shown with cards.
    season_rows = [
        {
            "player": "Alice",
            "team": "Team A",
            "season": "Season 9",
            "average": 200.0,
            "highest_game": 220,
            "lowest_game": 180,
            "weeks_played": 10,
            "games_bowled": 40,
        }
    ]
    all_time = build_top_player_scores_hub_html(
        games, weeks, "All Time", 10, player_season_rows=season_rows
    )
    assert "Best seasons" in all_time
    assert 'data-view-tab="averages"' in all_time
    assert 'data-sort-kind="averages"' in all_time
    assert 'class="team-season">' not in all_time
    assert 'data-disp-season="S9"' in all_time
    assert "S9 · H 220 · L 180" in all_time
    assert all_time.count("score-card") >= 3
    assert 'card-detail-label">Week</div>' in html
    assert "score-card--static" in html
    assert 'card-detail-label">Game</div>' not in html
    # Expand boxes don't repeat week/season/team already shown on the summary.
    assert 'class="dl">Team</div>' not in html
    assert 'class="dl">Wk</div>' not in html
    assert 'class="dl">Season</div>' not in all_time

