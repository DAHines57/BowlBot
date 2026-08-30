"""JSON API for the unified stats page."""

import pytest
from flask import Flask

from app import api
from league_service import LeagueService
from stats import compute


def _fact(player, season, week, *, games=(200, 200), team="Team A", playoffs=False,
          absent=False):
    row = {
        "season_number": season,
        "season_label": f"Season {season}",
        "week": week,
        "team": team,
        "opponent": "Team B",
        "player_display_name": player,
        "substitute": False,
        "absent": absent,
        "playoffs": playoffs,
        "week_average": sum(games) / len(games) if games else 0,
    }
    for i, g in enumerate(games, start=1):
        row[f"game{i}"] = g
    return row


FACTS = [
    _fact("Alice", 13, 1, games=(150, 150)),
    _fact("Alice", 13, 2, games=(250, 250)),
    _fact("Alice", 14, 1, games=(200, 200)),
    _fact("Alice", 14, 9, games=(100, 100), playoffs=True),
    _fact("Bob", 13, 1, games=(180, 180), team="Team B"),
    _fact("Bob", 14, 1, games=(220, 220), team="Team B"),
]


class _FakeData:
    """Minimal stand-in for DbLeagueData covering what the API touches."""

    read_source = "test"

    def __init__(self, facts):
        self._facts = list(facts)

    def _facts_list(self):
        return self._facts

    def get_seasons(self):
        return ["Season 13", "Season 14"]

    def get_current_season(self):
        return "Season 14"

    def get_latest_week(self, season=None):
        return 9

    def list_weeks_for_season(self, season=None):
        num = 14 if season and season.endswith("14") else 13
        return sorted({f["week"] for f in self._facts if f["season_number"] == num})

    def list_playoff_weeks_for_season(self, season=None):
        num = 14 if season and season.endswith("14") else 13
        return sorted(
            {
                f["week"]
                for f in self._facts
                if f["season_number"] == num and f.get("playoffs")
            }
        )

    def get_team_weekly_summary(self, team_name, season=None):
        return compute.get_team_weekly_summary(
            self._facts,
            team_name,
            season,
            season_num=compute.parse_season_number(season),
        )

    def get_player_scores(self, *a, **kw):
        return {}

    def get_team_scores(self, *a, **kw):
        return {}


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["LEAGUE_SERVICE"] = LeagueService(_FakeData(FACTS))
    app.register_blueprint(api.api_bp)
    return app.test_client()


def test_meta_lists_seasons_weeks_and_playoff_weeks(client):
    data = client.get("/api/meta").get_json()
    assert data["current_season"] == "Season 14"
    assert data["current_season_number"] == 14
    labels = [s["label"] for s in data["seasons"]]
    assert labels == ["Season 14", "Season 13"]
    s14 = next(s for s in data["seasons"] if s["number"] == 14)
    assert s14["weeks"] == [1, 9]
    assert s14["playoff_weeks"] == [9]


def test_leaderboard_defaults_to_current_season(client):
    data = client.get("/api/leaderboard").get_json()
    assert data["scope"]["single_season"] == 14
    assert data["par_available"] is True
    assert {p["player"] for p in data["players"]} == {"Alice", "Bob"}


def test_leaderboard_range_spans_seasons(client):
    data = client.get("/api/leaderboard?from=13.1&to=14.1&mode=range").get_json()
    alice = next(p for p in data["players"] if p["player"] == "Alice")
    # 150,150,250,250 (S13) + 200,200 (S14) -> 1200/6
    assert alice["average"] == 200.0
    assert alice["games"] == 6
    assert data["scope"]["seasons_covered"] == [13, 14]


def test_season_mode_differs_from_range_mode(client):
    q = "from=13.1&to=14.1"
    rng = client.get(f"/api/leaderboard?{q}&mode=range").get_json()
    per_season = client.get(f"/api/leaderboard?{q}&mode=season").get_json()
    a_rng = next(p for p in rng["players"] if p["player"] == "Alice")["average"]
    a_season = next(p for p in per_season["players"] if p["player"] == "Alice")["average"]
    assert a_rng == 200.0
    # S13 mean 200, S14 mean 200 -> equal here; Bob differs (180 vs 220)
    b_rng = next(p for p in rng["players"] if p["player"] == "Bob")["average"]
    b_season = next(p for p in per_season["players"] if p["player"] == "Bob")["average"]
    assert b_rng == b_season == 200.0
    assert a_season == 200.0


def test_par_is_null_when_range_spans_seasons(client):
    data = client.get("/api/leaderboard?from=13.1&to=14.1").get_json()
    assert data["par_available"] is False
    assert all(p["par"] is None for p in data["players"])


def test_par_present_for_single_season_range(client):
    data = client.get("/api/leaderboard?from=13.1&to=13.9").get_json()
    assert data["par_available"] is True
    assert data["scope"]["single_season"] == 13


def test_legacy_playoff_flags_still_work(client):
    """The filter used to be a checkbox; old links carry playoffs=1 and 0."""
    with_po = client.get("/api/leaderboard?from=14.1&to=14.9&playoffs=1").get_json()
    without = client.get("/api/leaderboard?from=14.1&to=14.9&playoffs=0").get_json()
    a_with = next(p for p in with_po["players"] if p["player"] == "Alice")
    a_without = next(p for p in without["players"] if p["player"] == "Alice")
    assert a_with["games"] == 4
    assert a_without["games"] == 2
    assert a_without["average"] == 200.0
    assert with_po["scope"]["playoffs"] == "both"
    assert without["scope"]["playoffs"] == "regular"


def test_playoffs_filter_has_three_settings(client):
    """Alice bowls 200s in W1 and 100s in the W9 playoff week."""
    q = "from=14.1&to=14.9&playoffs="

    both = client.get(f"/api/leaderboard?{q}both").get_json()
    regular = client.get(f"/api/leaderboard?{q}regular").get_json()
    only = client.get(f"/api/leaderboard?{q}only").get_json()

    def alice(data):
        return next(p for p in data["players"] if p["player"] == "Alice")

    assert alice(both)["games"] == 4
    assert alice(regular)["games"] == 2
    assert alice(regular)["average"] == 200.0
    assert alice(only)["games"] == 2
    assert alice(only)["average"] == 100.0
    assert only["scope"]["playoffs"] == "only"


def test_playoffs_defaults_to_both(client):
    data = client.get("/api/leaderboard?from=14.1&to=14.9").get_json()
    assert data["scope"]["playoffs"] == "both"


def test_unknown_playoffs_filter_is_rejected(client):
    r = client.get("/api/leaderboard?from=14.1&to=14.9&playoffs=semifinals")
    assert r.status_code == 400
    assert "Unknown playoffs filter" in r.get_json()["error"]


def test_reversed_range_is_normalized(client):
    forward = client.get("/api/leaderboard?from=13.1&to=14.1").get_json()
    backward = client.get("/api/leaderboard?from=14.1&to=13.1").get_json()
    assert forward["scope"]["start"] == backward["scope"]["start"]
    assert forward["scope"]["end"] == backward["scope"]["end"]


def test_unknown_mode_is_rejected(client):
    r = client.get("/api/leaderboard?mode=sideways")
    assert r.status_code == 400
    assert "Unknown mode" in r.get_json()["error"]


def test_rows_carry_a_team_color_key(client, monkeypatch):
    """The unified page tints team names, so every row needs the key present."""
    monkeypatch.setattr(
        "app.api.lookup_team_color",
        lambda team: "#001133" if team == "Team A" else None,
    )
    data = client.get("/api/leaderboard?from=14.1&to=14.9").get_json()
    by_player = {p["player"]: p for p in data["players"]}
    # Dark navy is lightened for readability rather than passed through.
    assert by_player["Alice"]["color"] == "#999FAD"
    assert by_player["Bob"]["color"] is None
    assert all("color" in t for t in data["teams"])


def test_highlight_cards_carry_a_team_color(client, monkeypatch):
    """The summary cards name a team as well, so they get tinted too."""
    monkeypatch.setattr("app.api.lookup_team_color", lambda team: "#FF8800")
    highlights = client.get("/api/leaderboard?from=14.1&to=14.9").get_json()["highlights"]
    cards = [c for c in highlights.values() if c is not None]
    assert cards, "expected at least one highlight card"
    assert all(c["color"] == "#FF8800" for c in cards)


def test_highlights_tolerate_a_missing_card(client):
    """Every card is None when no week in the range has a scored game."""
    data = client.get("/api/leaderboard?from=13.9&to=13.9").get_json()
    highlights = data["highlights"]
    assert all(highlights[k] is None for k in highlights)


def test_highlights_name_the_best_single_week(client):
    """Alice's S13 W2 pair of 250s is the best night in the range."""
    h = client.get("/api/leaderboard?from=13.1&to=14.1").get_json()["highlights"]
    assert h["high_week"]["player"] == "Alice"
    assert h["high_week"]["score"] == 250.0
    assert h["high_week"]["when"] == "S13 W2"


def test_high_week_ignores_a_single_game_fragment(client):
    """A lone scored game is a per-game absence, not a night's work."""
    app = Flask(__name__)
    facts = FACTS + [_fact("Solo", 14, 1, games=(300,), team="Team C")]
    app.config["LEAGUE_SERVICE"] = LeagueService(_FakeData(facts))
    app.register_blueprint(api.api_bp)

    data = app.test_client().get("/api/leaderboard?from=13.1&to=14.1").get_json()
    assert data["highlights"]["high_week"]["player"] == "Alice"


def test_highlights_count_the_most_200s(client):
    """Alice has 250, 250, 200, 200 in the range; Bob has 220, 220."""
    h = client.get("/api/leaderboard?from=13.1&to=14.1").get_json()["highlights"]
    assert h["most_200s"]["player"] == "Alice"
    assert h["most_200s"]["score"] == 4
    # The count describes the whole range, so there is no single week to name.
    assert h["most_200s"]["when"] is None


def test_consistency_card_needs_a_real_sample(client):
    """Six games is under MIN_GAMES_FOR_CONSISTENCY, so nobody qualifies."""
    h = client.get("/api/leaderboard?from=13.1&to=14.1").get_json()["highlights"]
    assert h["consistent"] is None


def test_consistency_card_ignores_a_short_perfect_sample():
    """A two-game player with zero spread must not beat a full-season bowler."""
    app = Flask(__name__)
    facts = [_fact("Steady", 14, w, games=(190, 210)) for w in range(1, 6)]
    facts.append(_fact("Rookie", 14, 1, games=(200, 200), team="Team B"))
    app.config["LEAGUE_SERVICE"] = LeagueService(_FakeData(facts))
    app.register_blueprint(api.api_bp)

    data = app.test_client().get("/api/leaderboard?from=14.1&to=14.5").get_json()
    card = data["highlights"]["consistent"]
    assert card["player"] == "Steady"
    assert card["score"] == 10.0


def test_single_week_scope_is_a_range_of_one(client):
    """The span flip sends from === to; nothing else about the API changes."""
    data = client.get("/api/leaderboard?from=14.1&to=14.1").get_json()
    alice = next(p for p in data["players"] if p["player"] == "Alice")
    assert alice["games"] == 2
    assert alice["weeks_played"] == 1
    assert data["scope"]["single_season"] == 14


def test_player_detail_lists_games(client):
    data = client.get("/api/player/Alice?from=13.1&to=14.1").get_json()
    assert data["player"] == "Alice"
    assert [g["score"] for g in data["games"]] == [150, 150, 250, 250, 200, 200]
    assert data["games"][0]["label"] == "S13 W1"
    assert data["summary"]["games"] == 6


def test_player_detail_unknown_player_is_404(client):
    assert client.get("/api/player/Nobody").status_code == 404


def test_team_detail_carries_records_across_seasons(client):
    """Matchups are per-season, so a cross-season range resolves them a season
    at a time rather than giving up on the record entirely."""
    data = client.get("/api/team/Team A?from=13.1&to=14.1").get_json()
    assert data["team"] == "Team A"
    assert data["records_available"] is True
    assert data["record"] is not None
    assert [w["label"] for w in data["weeks"]] == ["S13 W1", "S13 W2", "S14 W1"]
    assert [w["pins"] for w in data["weeks"]] == [300, 500, 400]
    assert all(w["opponent"] == "Team B" for w in data["weeks"])


def test_team_detail_weeks_sum_to_the_row_total(client):
    """The expansion and the leaderboard row share one accumulator, so their
    totals must agree."""
    q = "from=13.1&to=14.9"
    detail = client.get(f"/api/team/Team A?{q}").get_json()
    board = client.get(f"/api/leaderboard?{q}").get_json()
    row = next(t for t in board["teams"] if t["team"] == "Team A")
    assert sum(w["pins"] for w in detail["weeks"]) == row["total_pins"]
    assert sum(w["games"] for w in detail["weeks"]) == row["games"]
    assert detail["summary"]["total_pins"] == row["total_pins"]


def test_team_detail_carries_records_within_one_season(client):
    data = client.get("/api/team/Team A?from=13.1&to=13.9").get_json()
    assert data["records_available"] is True
    assert data["record"] is not None
    week = data["weeks"][0]
    assert week["opponent"] == "Team B"
    assert {"wins", "losses", "ties", "pins_against"} <= set(week)


def test_team_detail_marks_each_game_against_the_opponent(client):
    """The week table shows per-game totals, tinted like the weekly results."""
    data = client.get("/api/team/Team A?from=13.1&to=13.9").get_json()
    weeks = {w["label"]: w for w in data["weeks"]}
    # W1: Alice 150/150 against Bob 180/180, so both games are losses.
    assert weeks["S13 W1"]["game_pins"] == [
        {"pins": 150, "opp_pins": 180, "result": "L"},
        {"pins": 150, "opp_pins": 180, "result": "L"},
    ]
    # W2 has no opposing team, so the totals stand without a result.
    assert weeks["S13 W2"]["game_pins"] == [
        {"pins": 250, "opp_pins": 0, "result": None},
        {"pins": 250, "opp_pins": 0, "result": None},
    ]


def test_team_detail_has_no_game_pins_across_seasons(client):
    """Per-game marks need matchups, which do not span seasons."""
    data = client.get("/api/team/Team A?from=13.1&to=14.1").get_json()
    assert all("game_pins" not in w for w in data["weeks"])


def test_team_detail_skips_seasons_the_team_missed(client):
    """A team that only shows up for part of the range still gets records for
    the seasons it played, and no rows for the ones it did not."""
    app = Flask(__name__)
    facts = FACTS + [_fact("Cara", 14, 1, games=(210, 210), team="Team C")]
    app.config["LEAGUE_SERVICE"] = LeagueService(_FakeData(facts))
    app.register_blueprint(api.api_bp)

    data = app.test_client().get("/api/team/Team C?from=13.1&to=14.1").get_json()
    assert [w["label"] for w in data["weeks"]] == ["S14 W1"]
    assert data["records_available"] is True
    assert data["weeks"][0]["opponent"] == "Team B"


def test_team_detail_sub_range_keeps_records(client):
    """A window inside a season still resolves matchups, for its weeks only."""
    data = client.get("/api/team/Team A?from=13.2&to=13.2").get_json()
    assert data["records_available"] is True
    assert [w["label"] for w in data["weeks"]] == ["S13 W2"]
    assert data["weeks"][0]["opponent"] == "Team B"


def test_team_detail_unknown_team_is_404(client):
    assert client.get("/api/team/Team Z?from=14.1&to=14.9").status_code == 404


def test_team_detail_carries_a_team_color(client, monkeypatch):
    monkeypatch.setattr("app.api.lookup_team_color", lambda team: "#FF8800")
    data = client.get("/api/team/Team A?from=13.1&to=14.1").get_json()
    assert data["color"] == "#FF8800"


def test_endpoints_report_unavailable_without_service():
    app = Flask(__name__)
    app.config["LEAGUE_SERVICE"] = None
    app.register_blueprint(api.api_bp)
    c = app.test_client()
    assert c.get("/api/meta").status_code == 503
    assert c.get("/api/leaderboard").status_code == 503
    assert c.get("/api/player/Alice").status_code == 503
    assert c.get("/api/team/Team A").status_code == 503
