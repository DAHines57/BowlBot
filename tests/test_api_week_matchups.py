"""The week-matchup feed behind the Matchups tab."""

import pytest
from flask import Flask

from app import api
from league_service import LeagueService
from stats import compute
from test_api_leaderboard import _FakeData, _fact


def _matchup_facts():
    """Two paired teams over one week, plus a third team left unpaired."""
    out = []
    for name, team, opp, games in (
        ("Alice", "Team A", "Team B", (200, 190, 210, 180)),
        ("Bob", "Team A", "Team B", (170, 160, 150, 165)),
        ("Cara", "Team B", "Team A", (150, 140, 220, 160)),
        ("Dan", "Team B", "Team A", (145, 155, 165, 175)),
    ):
        row = _fact(name, 14, 1, games=games, team=team)
        row["opponent"] = opp
        out.append(row)
    return out


FACTS = _matchup_facts()


class _Data(_FakeData):
    def get_week_matchups(self, week, season=None):
        return compute.get_week_matchups(
            self._facts,
            week,
            season,
            season_num=compute.parse_season_number(season),
        )

    def get_latest_week(self, season=None):
        # The base fake pins this to a fixed number; the default-week path needs
        # the real answer for these facts.
        return compute.get_latest_week(
            self._facts, season, season_num=compute.parse_season_number(season)
        )


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["LEAGUE_SERVICE"] = LeagueService(_Data(FACTS))
    app.register_blueprint(api.api_bp)
    return app.test_client()


def _only_matchup(client, query="?season=Season 14&week=1"):
    data = client.get("/api/week-matchups" + query).get_json()
    assert data["matchups"], data
    return data, data["matchups"][0]


def test_carries_the_season_and_week_asked_for(client):
    data, _ = _only_matchup(client)
    assert data["season"] == "Season 14"
    assert data["season_number"] == 14
    assert data["week"] == 1
    assert data["is_playoff_week"] is False


def test_defaults_to_the_latest_week(client):
    data = client.get("/api/week-matchups").get_json()
    assert data["week"] == 1
    assert data["season"] == "Season 14"


def test_each_side_carries_the_totals_the_card_shows(client):
    _, m = _only_matchup(client)
    for side in ("home", "away"):
        assert m[side]["name"]
        assert isinstance(m[side]["pins"], (int, float))
        assert isinstance(m[side]["avg"], (int, float))
        assert isinstance(m[side]["wins"], int)
        assert m[side]["result"] in ("W", "L", "T", "\u2014")
        assert len(m[side]["game_pins"]) == 4


def test_game_results_pair_the_two_sides_per_game(client):
    _, m = _only_matchup(client)
    assert len(m["game_results"]) == 4
    for entry in m["game_results"]:
        home_result, away_result, home_pins, away_pins = entry
        assert home_result in ("W", "L", "T")
        assert away_result in ("W", "L", "T")
        assert home_pins > 0 and away_pins > 0
    # Game wins across both sides account for every game bowled.
    assert m["home"]["wins"] + m["away"]["wins"] <= len(m["game_results"])


def test_bowler_lines_come_through_for_both_sides(client):
    _, m = _only_matchup(client)
    home_names = sorted(p["name"] for p in m["home"]["players"])
    away_names = sorted(p["name"] for p in m["away"]["players"])
    assert home_names == ["Alice", "Bob"]
    assert away_names == ["Cara", "Dan"]
    for p in m["home"]["players"]:
        assert p["counts"] is True
        assert len(p["games"]) >= 4


def test_team_colors_are_attached(client):
    _, m = _only_matchup(client)
    assert "home_color" in m
    assert "away_color" in m


def test_an_unnumbered_season_is_rejected(client):
    res = client.get("/api/week-matchups?season=Fall League")
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_a_bad_week_is_rejected(client):
    res = client.get("/api/week-matchups?season=Season 14&week=abc")
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_a_week_with_no_rows_reports_rather_than_failing(client):
    data = client.get("/api/week-matchups?season=Season 14&week=9").get_json()
    assert data["matchups"] == []
    assert data["message"]


def test_needs_a_service():
    app = Flask(__name__)
    app.config["LEAGUE_SERVICE"] = None
    app.register_blueprint(api.api_bp)
    assert app.test_client().get("/api/week-matchups").status_code == 503
