"""Bracket, seeding, and champion data behind the Playoffs tab."""

import pytest
from flask import Flask

from app import api
from league_service import LeagueService
from stats import compute
from test_api_leaderboard import _FakeData, _fact

TEAMS = [f"Team {i}" for i in range(1, 9)]


def _week(season, week, results, *, playoffs=False):
    """One fact per team for a week. ``results`` is (home, away, home_pins)."""
    out = []
    for home, away, home_pins in results:
        for team, opp, pins in (
            (home, away, home_pins),
            (away, home, home_pins - 10),
        ):
            out.append(
                _fact(
                    f"{team} bowler",
                    season,
                    week,
                    games=(pins, pins),
                    team=team,
                    playoffs=playoffs,
                )
            )
            out[-1]["opponent"] = opp
    return out


# Descending pins down the seed list, so the ordering is unambiguous.
_REGULAR = [
    (TEAMS[0], TEAMS[1], 250),
    (TEAMS[2], TEAMS[3], 240),
    (TEAMS[4], TEAMS[5], 230),
    (TEAMS[6], TEAMS[7], 220),
]

# Season 14 has no playoff week yet, so its bracket is entirely projected.
# Season 13 has one bowled playoff week to exercise the played-round path.
FACTS = (
    _week(14, 1, _REGULAR)
    + _week(14, 2, _REGULAR)
    + _week(13, 1, _REGULAR)
    + _week(13, 2, _REGULAR)
    + _week(
        13,
        3,
        [
            (TEAMS[0], TEAMS[7], 250),
            (TEAMS[3], TEAMS[4], 240),
            (TEAMS[1], TEAMS[6], 230),
            (TEAMS[2], TEAMS[5], 220),
        ],
        playoffs=True,
    )
)


class _Data(_FakeData):
    """Adds the week-matchup lookup the bracket needs."""

    def get_week_matchups(self, week, season=None):
        return compute.get_week_matchups(
            self._facts,
            week,
            season,
            season_num=compute.parse_season_number(season),
        )


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["LEAGUE_SERVICE"] = LeagueService(_Data(FACTS))
    app.register_blueprint(api.api_bp)
    return app.test_client()


def test_defaults_to_the_current_season(client):
    data = client.get("/api/playoffs").get_json()
    assert data["season"] == "Season 14"
    assert data["season_number"] == 14
    assert data["last_regular_week"] == 2


def test_seeds_are_ordered_and_carry_records_and_colors(client):
    seeds = client.get("/api/playoffs?season=Season 14").get_json()["seeds"]

    assert [row["seed"] for row in seeds] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert [row["team"] for row in seeds] == [
        "Team 1", "Team 3", "Team 5", "Team 7",
        "Team 2", "Team 4", "Team 6", "Team 8",
    ]
    assert seeds[0]["record"] == "4-0"
    assert all("color" in row for row in seeds)


def test_upcoming_projects_the_first_round_from_seeding(client):
    data = client.get("/api/playoffs?season=Season 14").get_json()

    assert data["playoff_weeks"] == []
    assert data["rounds"] == []
    upcoming = data["upcoming"]
    assert upcoming["projected"] is True
    assert upcoming["week"] == 3
    assert upcoming["label"] == "Quarterfinals"
    assert [(m["home"], m["away"]) for m in upcoming["matchups"]] == [
        ("Team 1", "Team 8"),
        ("Team 7", "Team 2"),
        ("Team 3", "Team 6"),
        ("Team 5", "Team 4"),
    ]
    assert all(m["projected"] for m in upcoming["matchups"])
    assert upcoming["matchups"][0]["home_seed"] == 1


def test_bowled_playoff_week_comes_back_as_a_played_round(client):
    data = client.get("/api/playoffs?season=Season 13").get_json()

    assert data["playoff_weeks"] == [3]
    assert len(data["rounds"]) == 1
    week = data["rounds"][0]
    assert week["week"] == 3
    assert week["label"] == "Finals"
    played = week["matchups"]
    assert len(played) == 4
    assert all(m["projected"] is False for m in played)
    assert all(m["home_pins"] for m in played)
    assert all("home_color" in m for m in played)
    # Every playoff week is bowled, so nothing is upcoming.
    assert data["upcoming"] is None


def test_played_matchups_carry_prior_records_and_game_wins(client):
    week = client.get("/api/playoffs?season=Season 13").get_json()["rounds"][0]

    for m in week["matchups"]:
        assert m["home_record"] and m["away_record"]
        # Both sides swept a regular week each, so nobody is 0-4 going in.
        assert m["home_game_wins"] + m["away_game_wins"] == len(m["home_games"])
    top = next(m for m in week["matchups"] if m["home"] == "Team 1")
    # Week 3 is the first playoff week, so the record is the 4-0 seeding one.
    assert top["home_record"] == "4-0"
    assert top["away_record"] == "0-4"
    assert (top["home_game_wins"], top["away_game_wins"]) == (2, 0)


def test_projected_matchups_carry_records_but_no_game_wins(client):
    upcoming = client.get("/api/playoffs?season=Season 14").get_json()["upcoming"]

    first = upcoming["matchups"][0]
    assert first["home_record"] == "4-0"
    assert first["away_record"] == "0-4"
    assert "home_game_wins" not in first


def test_standings_default_to_the_latest_week_and_count_playoffs(client):
    data = client.get("/api/playoffs?season=Season 13").get_json()
    standings = data["standings"]

    assert data["last_regular_week"] == 2
    assert data["last_week"] == 3
    assert data["standings_week"] == 3
    assert [row["seed"] for row in standings] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert all("color" in row for row in standings)
    # Team 1 swept its playoff week 3 matchup, so both games add to its record.
    seed_row = next(row for row in data["seeds"] if row["team"] == "Team 1")
    late_row = next(row for row in standings if row["team"] == "Team 1")
    assert seed_row["record"] == "4-0"
    assert late_row["wins"] == seed_row["wins"] + 2
    assert late_row["record"] == "6-0"
    # Team 5 lost its playoff matchup, so it drops behind the teams that won.
    assert next(row for row in standings if row["team"] == "Team 5")["record"] == "4-2"
    assert [row["team"] for row in standings[:2]] == ["Team 1", "Team 3"]


def test_standings_stop_at_the_asked_week(client):
    data = client.get("/api/playoffs?season=Season 13&week=1").get_json()

    assert data["standings_week"] == 1
    assert all(row["record"] in ("2-0", "0-2") for row in data["standings"])
    # The bracket below the table is still built from the frozen seeding.
    assert data["seeds"][0]["record"] == "4-0"
    assert data["last_week"] == 3


def test_standings_reorder_as_the_week_moves(client):
    week2 = client.get("/api/playoffs?season=Season 13&week=2").get_json()
    week3 = client.get("/api/playoffs?season=Season 13&week=3").get_json()

    names2 = [row["team"] for row in week2["standings"]]
    names3 = [row["team"] for row in week3["standings"]]
    assert names2[:4] == ["Team 1", "Team 3", "Team 5", "Team 7"]
    assert names2 != names3


def test_a_week_the_season_never_bowled_falls_back(client):
    late = client.get("/api/playoffs?season=Season 13&week=99").get_json()
    assert late["standings_week"] == 3

    bad = client.get("/api/playoffs?season=Season 13&week=nope")
    assert bad.status_code == 400


def test_history_lists_a_champion_per_season(client):
    data = client.get("/api/playoffs?season=Season 13").get_json()

    seasons = [row["season"] for row in data["history"]]
    assert seasons == ["Season 14", "Season 13"]
    s13 = next(row for row in data["history"] if row["season"] == "Season 13")
    assert s13["champion"]
    assert s13["champion_color"] is None or isinstance(s13["champion_color"], str)
    # Season 14 has bowled no playoff week, so it has no winner yet.
    s14 = next(row for row in data["history"] if row["season"] == "Season 14")
    assert s14["champion"] is None


def test_needs_a_service(client):
    app = Flask(__name__)
    app.config["LEAGUE_SERVICE"] = None
    app.register_blueprint(api.api_bp)
    assert app.test_client().get("/api/playoffs").status_code == 503
