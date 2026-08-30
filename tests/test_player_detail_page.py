"""Markup and styling of the player profile page."""

import re

import image_generator
from league_service import LeagueService


class _Data:
    def __init__(self, scores):
        self._scores = scores

    def find_player_names(self, name, season):
        return [self._scores.get("player", name)]

    def get_player_scores(self, name, season):
        return self._scores

    def get_player_game_history(self, name, season=None, limit=30):
        return [
            {"score": 210, "week": 1, "game": 1, "season_label": season, "season_number": 9},
            {"score": 195, "week": 2, "game": 1, "season_label": season, "season_number": 9},
        ]

    def get_league_game_stats(self, season=None, all_time=False):
        return {"league_avg": 180.0}


def _page():
    svc = LeagueService(
        _Data(
            {
                "player": "Alice",
                "team": "Team A",
                "scores": [200, 210],
                "average": 205.0,
                "std_dev": 5.0,
                "highest_game": 210,
                "lowest_game": 200,
                "weeks_absent": 1,
                "weeks_subbed": 0,
            }
        )
    )
    page, err = svc.player_detail_page("Alice", "Season 9")
    assert err == ""
    return page


def test_header_leads_with_the_name_then_team_and_scope():
    page = _page()

    assert '<div class="title">Alice</div>' in page
    assert 'class="player-team"' in page
    assert "Team A" in page
    assert "Season 9" in page
    # The team no longer needs a section of its own.
    assert "player-detail-team" not in page


def test_stats_render_as_toned_tiles_above_the_chart():
    page = _page()

    assert 'class="player-stat-rows"' in page
    assert "player-stat-val--gold" in page
    assert "player-stat-val--green" in page
    assert "player-stat-val--muted" in page
    assert "Season stats" in page
    assert "Recent games" in page
    assert "<svg" in page


def test_player_styling_uses_tokens_rather_than_bare_hex():
    assert "--accent: #ffb86c" in image_generator._APP_TOKENS_CSS
    assert "var(--accent)" in image_generator._PLAYER_DETAIL_CSS_EXTRA
    assert not re.search(r"#[0-9a-fA-F]{3,6}", image_generator._PLAYER_DETAIL_CSS_EXTRA)
