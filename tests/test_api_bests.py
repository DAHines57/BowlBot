"""Record lists behind the Bests tab."""

import pytest
from flask import Flask

from app import api
from league_service import LeagueService
from stats.bests import MIN_GAMES_FOR_SEASON_BEST
from test_api_leaderboard import _FakeData, _fact


def _weeks(player, season, first, last, games, team="Team A"):
    """One fact per week over an inclusive week range."""
    return [
        _fact(player, season, wk, games=games, team=team)
        for wk in range(first, last + 1)
    ]


# Steady bowls a full S14; Spike bowls a full S13 and a much better S14, so
# most-improved has something to find. Cameo bowls two weeks only, to prove the
# per-season minimum keeps a tiny sample off the season lists.
FACTS = (
    _weeks("Steady", 14, 1, 8, (190, 200))
    + _weeks("Spike", 13, 1, 8, (150, 160), team="Team B")
    + _weeks("Spike", 14, 1, 8, (230, 240), team="Team B")
    + _weeks("Cameo", 14, 1, 2, (280, 290), team="Team C")
)


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["LEAGUE_SERVICE"] = LeagueService(_FakeData(FACTS))
    app.register_blueprint(api.api_bp)
    return app.test_client()


def _cats(client, query="from=13.1&to=14.9"):
    return client.get("/api/bests?" + query).get_json()["categories"]


def test_every_category_is_present(client):
    cats = _cats(client)
    for key in [
        "games", "weeks", "seasons", "most_200s", "streaks", "consistent",
        "career_nights", "improved", "team_weeks", "team_seasons",
    ]:
        assert key in cats, key


def test_best_games_are_ordered_high_to_low(client):
    scores = [e["score"] for e in _cats(client)["games"]]
    assert scores == sorted(scores, reverse=True)
    # Cameo's 290 is a real game and belongs here even though his sample is too
    # small for the season lists.
    assert scores[0] == 290


def test_best_weeks_use_the_week_average_and_name_the_week(client):
    top = _cats(client)["weeks"][0]
    assert top["player"] == "Cameo"
    assert top["score"] == 285.0
    assert top["when"] == "S14 W1"
    assert top["games"] == 2


def test_best_seasons_excludes_a_short_sample(client):
    seasons = _cats(client)["seasons"]
    assert "Cameo" not in {e["player"] for e in seasons}
    # Four games is well under the minimum, so the gate is what excluded him.
    assert 4 < MIN_GAMES_FOR_SEASON_BEST
    top = seasons[0]
    assert top["player"] == "Spike"
    assert top["score"] == 235.0
    assert top["when"] == "S14"


def test_most_200s_counts_every_qualifying_game(client):
    counts = {e["player"]: e["score"] for e in _cats(client)["most_200s"]}
    # Spike: 16 games in S14 all at 230/240. Steady: eight 200s, the 190s miss.
    assert counts["Spike"] == 16
    assert counts["Steady"] == 8
    assert counts["Cameo"] == 4


def test_streaks_run_across_week_boundaries(client):
    streaks = {e["player"]: e for e in _cats(client)["streaks"]}
    # Spike's whole S14 is 200+, so the streak spans every game of it.
    assert streaks["Spike"]["score"] == 16
    # And the span reported is the first and last week of that run.
    assert "\u2192" in streaks["Spike"]["when"]
    # Steady alternates 190/200, so no two in a row ever qualify.
    assert "Steady" not in streaks


def test_career_night_is_measured_against_the_players_own_average(client):
    nights = {e["player"]: e for e in _cats(client)["career_nights"]}
    # Spike ranges 150-240 across two seasons, so his best night stands out
    # much further from his own average than Steady's does.
    assert nights["Spike"]["score"] > nights["Steady"]["score"]
    # Every S14 week is 230/240 against a 195 average over both seasons.
    assert nights["Spike"]["average"] == 235.0
    assert nights["Spike"]["games"] == 2
    assert nights["Spike"]["score"] == 40.0
    assert nights["Spike"]["when"].startswith("S14")
    # Four games is under the minimum behind the baseline average.
    assert "Cameo" not in nights


def test_career_night_ignores_a_one_game_week():
    """A per-game absence can leave one score, which is not a night's work."""
    facts = (
        _weeks("Solo", 14, 1, 8, (170, 180))
        + [_fact("Solo", 14, 9, games=(300,))]
    )
    app = Flask(__name__)
    app.config["LEAGUE_SERVICE"] = LeagueService(_FakeData(facts))
    app.register_blueprint(api.api_bp)

    cats = app.test_client().get("/api/bests?from=14.1&to=14.9").get_json()["categories"]
    night = {e["player"]: e for e in cats["career_nights"]}["Solo"]
    assert night["games"] == 2
    assert night["average"] == 175.0


def test_most_improved_compares_consecutive_bowled_seasons(client):
    improved = _cats(client)["improved"]
    assert [e["player"] for e in improved] == ["Spike"]
    entry = improved[0]
    assert entry["from_average"] == 155.0
    assert entry["to_average"] == 235.0
    assert entry["score"] == 80.0
    assert entry["when"] == "S13 \u2192 S14"


def test_most_improved_is_empty_within_one_season(client):
    assert _cats(client, "from=14.1&to=14.9")["improved"] == []


def test_most_improved_skips_a_season_the_player_sat_out():
    """The comparison is to the previous season bowled, not the previous number."""
    facts = (
        _weeks("Returner", 12, 1, 8, (160, 170))
        + _weeks("Returner", 14, 1, 8, (200, 210))
    )
    app = Flask(__name__)
    app.config["LEAGUE_SERVICE"] = LeagueService(_FakeData(facts))
    app.register_blueprint(api.api_bp)

    cats = app.test_client().get("/api/bests?from=12.1&to=14.9").get_json()["categories"]
    entry = cats["improved"][0]
    assert entry["player"] == "Returner"
    assert entry["when"] == "S12 \u2192 S14"
    assert entry["score"] == 40.0


def test_consistency_matches_the_leaderboard_figures(client):
    """The list reuses the board's own rows, so the numbers must agree."""
    q = "from=13.1&to=14.9"
    board = client.get("/api/leaderboard?" + q).get_json()["players"]
    by_player = {p["player"]: p for p in board}
    for entry in _cats(client, q)["consistent"]:
        assert entry["score"] == by_player[entry["player"]]["std_dev"]


def test_team_records_name_the_team_and_when(client):
    cats = _cats(client)
    week = cats["team_weeks"][0]
    assert week["team"]
    assert week["when"].startswith("S")
    season = cats["team_seasons"][0]
    assert season["when"].startswith("S")


def test_rows_carry_a_team_color(client, monkeypatch):
    monkeypatch.setattr("app.api.lookup_team_color", lambda team: "#FF8800")
    cats = _cats(client)
    for entries in cats.values():
        for row in entries:
            assert row["color"] == "#FF8800"


def test_scope_reports_the_seasons_covered(client):
    data = client.get("/api/bests?from=13.1&to=14.9").get_json()
    assert data["scope"]["seasons_covered"] == [13, 14]
    assert data["scope"]["single_season"] is None


def test_unknown_playoffs_filter_is_rejected(client):
    r = client.get("/api/bests?from=14.1&to=14.9&playoffs=semifinals")
    assert r.status_code == 400


def test_frontend_sections_match_the_api_categories(client):
    """A mistyped key renders nothing at all, silently, so pin the two together."""
    import os
    import re

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(root, "static", "app.js"), encoding="utf-8").read()
    block = js[js.index("var BEST_SECTIONS = ["):js.index("var BESTS_PREVIEW")]
    rendered = set(re.findall(r'\{ key: "([a-z0-9_]+)"', block))

    assert rendered == set(_cats(client)), rendered.symmetric_difference(_cats(client))


def test_endpoint_reports_unavailable_without_service():
    app = Flask(__name__)
    app.config["LEAGUE_SERVICE"] = None
    app.register_blueprint(api.api_bp)
    assert app.test_client().get("/api/bests").status_code == 503
