"""Absence and sub counts on the player profile page."""

from league_service import LeagueService


class _Data:
    def __init__(self, scores=None, all_time=None):
        self._scores = scores or {}
        self._all_time = all_time or {}

    def find_player_names(self, name, season):
        return [self._scores.get("player", name)]

    def get_player_scores(self, name, season):
        return self._scores

    def get_all_time_stats(self):
        return self._all_time

    def get_player_game_history(self, name, season=None, limit=30):
        return []

    def get_league_game_stats(self, season=None, all_time=False):
        return {"league_avg": 180.0}


def _rows(view):
    return {label: value for label, value, _tone in view["stat_rows"]}


def _season_view(**overrides):
    scores = {
        "player": "Alice",
        "team": "Team A",
        "scores": [200, 210],
        "average": 205.0,
        "std_dev": 5.0,
        "highest_game": 210,
        "lowest_game": 200,
        "weeks_absent": 0,
        "weeks_subbed": 0,
    }
    scores.update(overrides)
    view, err = LeagueService(_Data(scores=scores))._player_detail_view(
        "Alice", "Season 9"
    )
    assert err == ""
    return view


def test_season_rows_always_show_absences():
    assert _rows(_season_view(weeks_absent=3))["Absences"] == "3"
    assert _rows(_season_view())["Absences"] == "0"


def test_weeks_subbed_row_only_appears_when_nonzero():
    assert "Weeks subbed" not in _rows(_season_view())
    assert _rows(_season_view(weeks_subbed=2))["Weeks subbed"] == "2"


def test_empty_scope_has_no_stat_rows():
    view = _season_view(scores=[])
    assert view["stat_rows"] is None
    assert view["empty_message"] == "No scores for this scope."


def test_all_time_rows_show_absences():
    all_time = {
        "player_averages": [
            {
                "player": "Alice",
                "team": "Team A",
                "average": 205.0,
                "std_dev": 5.0,
                "highest_game": 210,
                "lowest_game": 200,
                "games": 40,
                "absences": 4,
            }
        ]
    }
    view, err = LeagueService(_Data(all_time=all_time))._player_detail_view(
        "Alice", "all"
    )
    assert err == ""
    assert _rows(view)["Absences"] == "4"
