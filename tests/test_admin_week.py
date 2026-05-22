"""Tests for Phase 8 score entry."""
import pytest

from app import create_app
from league_admin import (
    assess_week_completion,
    build_absent_fill_averages,
    default_entry_week,
    get_week_entry,
    list_public_seasons,
    list_public_weeks_for_season,
    list_season_week_completion,
    parse_game_score,
    parse_week_rows_payload,
    team_show_game5_default,
    _template_week_rows,
    fact_to_entry_row,
)


def _fact(**kwargs):
    base = {
        "season_number": 10,
        "season_label": "Season 10",
        "team": "Team A",
        "player_display_name": "Alice",
        "week": 1,
        "game1": 200.0,
        "game2": 210.0,
        "game3": None,
        "game4": None,
        "game5": None,
        "absent": False,
        "substitute": False,
        "playoffs": False,
        "opponent": "Team B",
    }
    base.update(kwargs)
    return base


class _FakeData:
    def __init__(self, facts):
        self._facts = facts

    def _facts_list(self):
        return self._facts

    def get_seasons(self):
        nums = sorted({int(f["season_number"]) for f in self._facts})
        return [f"Season {n}" for n in nums]

    def get_current_season(self):
        seasons = self.get_seasons()
        return seasons[-1] if seasons else None

    def get_latest_week(self, season):
        from stats import compute

        return compute.get_latest_week(self._facts, season=season)

    def list_weeks_for_season(self, season):
        from stats import compute

        return compute.list_weeks_for_season(self._facts, season=season)


def test_parse_game_score():
    assert parse_game_score(None) == (None, None)
    assert parse_game_score("") == (None, None)
    assert parse_game_score(200) == (200.0, None)
    assert parse_game_score("210")[0] == 210.0
    assert parse_game_score(0)[1] is not None
    assert parse_game_score(301)[1] is not None
    assert parse_game_score("abc")[1] is not None
    assert parse_game_score(180.5)[1] is not None


def test_parse_week_rows_payload():
    rows, err = parse_week_rows_payload(
        {
            "playoffs": True,
            "team_opponents": {"Team A": "Team B"},
            "rows": [
                {
                    "team": "Team A",
                    "player_display_name": "Bob",
                    "absent": True,
                }
            ],
        }
    )
    assert err is None
    assert rows[0]["team"] == "Team A"
    assert rows[0]["absent"] is True
    assert rows[0]["game1"] is None
    assert rows[0]["playoffs"] is True
    assert rows[0]["opponent"] == "Team B"


def test_parse_week_rows_payload_absent_with_scores():
    rows, err = parse_week_rows_payload(
        {
            "rows": [
                {
                    "team": "Team A",
                    "player_display_name": "Bob",
                    "game1": 180,
                    "absent": True,
                }
            ],
        }
    )
    assert err is None
    assert rows[0]["absent"] is True
    assert rows[0]["game1"] == 180.0


def test_parse_week_rows_payload_rejects_invalid_score():
    _, err = parse_week_rows_payload(
        {
            "rows": [
                {
                    "team": "Team A",
                    "player_display_name": "Alice",
                    "game1": 0,
                }
            ],
        }
    )
    assert err is not None
    assert "game1" in err


def test_parse_week_rows_payload_mirrors_opponents():
    rows, err = parse_week_rows_payload(
        {
            "rows": [
                {
                    "team": "Team A",
                    "player_display_name": "Alice",
                    "game1": 200,
                }
            ],
            "team_opponents": {"Team A": "Team B"},
        }
    )
    assert err is None
    assert rows[0]["opponent"] == "Team B"


def test_get_week_entry_team_filter():
    facts = [
        _fact(),
        _fact(team="Team B", player_display_name="Bob", opponent="Team A"),
    ]
    data = _FakeData(facts)
    payload, err = get_week_entry(data, "Season 10", 1, team="Team A")
    assert err is None
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["player_display_name"] == "Alice"


def test_assess_week_completion_not_started():
    rows = [fact_to_entry_row(_fact(game1=None, game2=None, game3=None, game4=None, game5=None))]
    comp = assess_week_completion(rows, templated=True, season_teams=["Team A", "Team B"])
    assert comp["status"] == "not_started"


def test_assess_week_completion_incomplete_scores():
    rows = [
        fact_to_entry_row(_fact(game3=None, game4=None, game5=None)),
        fact_to_entry_row(
            _fact(
                team="Team B",
                player_display_name="Bob",
                opponent="Team A",
                game1=190,
                game2=190,
                game3=190,
                game4=190,
                game5=190,
            )
        ),
    ]
    comp = assess_week_completion(rows, templated=False, season_teams=["Team A", "Team B"])
    assert comp["status"] == "incomplete"
    assert len(comp["incomplete_players"]) == 1
    assert comp["incomplete_players"][0]["player_display_name"] == "Alice"


def test_assess_week_completion_game5_optional():
    rows = [
        fact_to_entry_row(
            _fact(game1=200, game2=200, game3=200, game4=200, game5=None)
        ),
        fact_to_entry_row(
            _fact(
                team="Team B",
                player_display_name="Bob",
                opponent="Team A",
                game1=190,
                game2=190,
                game3=190,
                game4=190,
                game5=None,
            )
        ),
    ]
    comp = assess_week_completion(rows, templated=False, season_teams=["Team A", "Team B"])
    assert comp["status"] == "complete"


def test_assess_week_completion_complete():
    rows = [
        fact_to_entry_row(_fact(game1=200, game2=200, game3=200, game4=200, game5=200)),
        fact_to_entry_row(
            _fact(
                team="Team B",
                player_display_name="Bob",
                opponent="Team A",
                game1=190,
                game2=190,
                game3=190,
                game4=190,
                game5=190,
            )
        ),
    ]
    comp = assess_week_completion(rows, templated=False, season_teams=["Team A", "Team B"])
    assert comp["status"] == "complete"


def test_list_public_weeks_hides_incomplete_current_season():
    facts = [
        _fact(season_number=10),
        _fact(team="Team B", player_display_name="Bob", opponent="Team A"),
    ]
    data = _FakeData(facts)
    weeks = list_public_weeks_for_season(data, "Season 10")
    assert weeks == []


def test_list_public_weeks_keeps_prior_season_weeks():
    facts = [
        _fact(season_number=9, game3=None),
        _fact(season_number=10, game1=200, game2=200, game3=200, game4=200, game5=200),
        _fact(
            season_number=10,
            team="Team B",
            player_display_name="Bob",
            opponent="Team A",
            game1=190,
            game2=190,
            game3=190,
            game4=190,
            game5=190,
        ),
    ]
    data = _FakeData(facts)
    assert list_public_weeks_for_season(data, "Season 9") == [1]
    assert list_public_weeks_for_season(data, "Season 10") == [1]


def test_list_public_seasons_excludes_empty_current_season():
    facts = [
        _fact(season_number=9, game1=200, game2=200, game3=200, game4=200, game5=200),
        _fact(season_number=10),
    ]
    data = _FakeData(facts)
    public = list_public_seasons(data)
    assert "Season 9" in public
    assert "Season 10" not in public


def test_default_entry_week_skips_ahead_when_earlier_incomplete():
    facts = [
        _fact(game3=None, game4=None, game5=None),
        _fact(team="Team B", player_display_name="Bob", opponent="Team A"),
    ]
    data = _FakeData(facts)
    assert default_entry_week(data, "Season 10", season_teams=["Team A", "Team B"]) == 1


def test_default_entry_week_opens_next_not_started():
    facts = [
        _fact(
            game1=200,
            game2=200,
            game3=200,
            game4=200,
            game5=200,
        ),
        _fact(
            team="Team B",
            player_display_name="Bob",
            opponent="Team A",
            game1=190,
            game2=190,
            game3=190,
            game4=190,
            game5=190,
        ),
    ]
    data = _FakeData(facts)
    assert default_entry_week(data, "Season 10", season_teams=["Team A", "Team B"]) == 2


def test_list_season_week_completion():
    facts = [
        _fact(),
        _fact(team="Team B", player_display_name="Bob", opponent="Team A"),
    ]
    data = _FakeData(facts)
    statuses = list_season_week_completion(data, "Season 10", season_teams=["Team A", "Team B"])
    assert statuses[0]["week"] == 1
    assert statuses[0]["status"] in ("incomplete", "complete")
    assert any(s["status"] == "not_started" for s in statuses)


def test_get_week_entry_includes_completion():
    facts = [_fact(game3=None)]
    data = _FakeData(facts)
    payload, err = get_week_entry(data, "Season 10", 1)
    assert err is None
    assert payload["completion"]["status"] == "incomplete"


def test_get_week_entry_existing_week():
    facts = [_fact(), _fact(player_display_name="Carl", game1=190)]
    data = _FakeData(facts)
    payload, err = get_week_entry(data, "Season 10", 1)
    assert err is None
    assert len(payload["rows"]) == 2
    assert payload["templated"] is False


def test_template_from_prior_season():
    facts = [_fact(season_number=9, week=1), _fact(season_number=9, player_display_name="Carl", week=1)]
    rows = _template_week_rows(facts, 10, 1)
    assert len(rows) == 2


def test_build_absent_fill_uses_current_season_after_three_weeks():
    facts = [
        _fact(week=1, game1=180, game2=180, game3=180, game4=180),
        _fact(week=2, game1=200, game2=200, game3=200, game4=200),
        _fact(week=3, game1=220, game2=220, game3=220, game4=220),
    ]
    avgs = build_absent_fill_averages(facts, 10, 4, ["Alice"])
    assert avgs["Alice"] == 200


def test_build_absent_fill_truncates_not_rounds():
    """187.92 pin avg must fill as 187, not round(avg) → 188."""
    facts = [
        _fact(week=1, game1=188, game2=188, game3=188, game4=188),
        _fact(week=2, game1=188, game2=188, game3=188, game4=188),
        _fact(week=3, game1=188, game2=188, game3=188, game4=187),
    ]
    avgs = build_absent_fill_averages(facts, 10, 4, ["Alice"])
    assert avgs["Alice"] == 187


def test_build_absent_fill_uses_prior_season_when_few_weeks():
    facts = [
        _fact(season_number=9, week=1, game1=150, game2=150, game3=150, game4=150),
        _fact(season_number=9, week=2, game1=170, game2=170, game3=170, game4=170),
        _fact(season_number=10, week=1, game1=190, game2=190, game3=190, game4=190),
        _fact(season_number=10, week=2, game1=210, game2=210, game3=210, game4=210),
    ]
    avgs = build_absent_fill_averages(facts, 10, 3, ["Alice"])
    assert avgs["Alice"] == 160


def test_get_week_entry_includes_absent_fill_averages():
    facts = [_fact(game3=200, game4=200)]
    data = _FakeData(facts)
    payload, err = get_week_entry(data, "Season 10", 2)
    assert err is None
    assert "absent_fill_averages" in payload
    assert isinstance(payload["absent_fill_averages"], dict)


def test_team_show_game5_default():
    assert team_show_game5_default([{"game5": None}]) is False
    assert team_show_game5_default([{"game5": 195}]) is True


def test_get_week_entry_team_game5_visible():
    facts = [_fact(game5=180)]
    data = _FakeData(facts)
    payload, err = get_week_entry(data, "Season 10", 1)
    assert err is None
    assert payload["team_game5_visible"]["Team A"] is True


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("ADMIN_PIN", "4242")
    application = create_app()
    application.config["TESTING"] = True
    return application


def test_admin_requires_pin(app):
    with app.test_client() as client:
        rv = client.get("/admin/enter?season=Season+10&week=1")
        assert rv.status_code == 302
        assert rv.headers["Location"].endswith("/admin") or "/admin?" in rv.headers["Location"]


def test_admin_pin_in_url_shows_menu(app):
    app.config["LEAGUE_SERVICE"] = type("S", (), {"seasons_sorted": lambda self: [], "data": None})()
    with app.test_client() as client:
        rv = client.get("/admin?pin=4242")
        assert rv.status_code == 200
        assert b"Enter scores" in rv.data
        assert b"Season setup" in rv.data


def test_admin_unlock_and_enter(app):
    facts = [_fact(), _fact(team="Team B", player_display_name="Bob", opponent="Team A")]
    fake = _FakeData(facts)

    class _Svc:
        data = fake

        def resolve_season(self, raw):
            return raw or "Season 10"

        def refresh_data(self):
            return True, "ok"

        def seasons_sorted(self):
            return ["Season 10"]

    app.config["LEAGUE_SERVICE"] = _Svc()

    with app.test_client() as client:
        client.post("/admin/unlock", data={"pin": "4242", "next": "/admin/enter?season=Season+10&week=1&team=Team+A"})
        rv = client.get("/admin/enter?season=Season+10&week=1&team=Team+A")
        assert rv.status_code == 200
        assert b"Alice" in rv.data
        assert b"Bob" not in rv.data


def test_admin_week_post_saves(app, monkeypatch):
    facts = [_fact()]
    fake = _FakeData(facts)
    saved = {}

    def fake_save(data, season, week, rows, *, refresh):
        saved["rows"] = rows
        return refresh()

    monkeypatch.setattr("app.admin_routes.save_week_entry", fake_save)

    class _Svc:
        data = fake

        def resolve_season(self, raw):
            return str(raw)

        def refresh_data(self):
            return True, "refreshed"

    app.config["LEAGUE_SERVICE"] = _Svc()

    with app.test_client() as client:
        client.post("/admin/unlock", data={"pin": "4242"})
        rv = client.post(
            "/admin/week",
            json={
                "season": "Season 10",
                "week": 2,
                "rows": [
                    {
                        "team": "Team A",
                        "player_display_name": "Alice",
                        "game1": 201,
                    }
                ],
            },
            content_type="application/json",
        )
        assert rv.status_code == 200
        assert saved["rows"][0]["game1"] == 201.0


def test_admin_week_post_rejects_invalid_score(app, monkeypatch):
    monkeypatch.setattr("app.admin_routes.save_week_entry", lambda *a, **k: (True, "ok"))

    class _Svc:
        def resolve_season(self, raw):
            return str(raw)

        def refresh_data(self):
            return True, "ok"

    app.config["LEAGUE_SERVICE"] = _Svc()

    with app.test_client() as client:
        client.post("/admin/unlock", data={"pin": "4242"})
        rv = client.post(
            "/admin/week",
            json={
                "season": "Season 10",
                "week": 1,
                "rows": [
                    {
                        "team": "Team A",
                        "player_display_name": "Alice",
                        "game1": 999,
                    }
                ],
            },
            content_type="application/json",
        )
        assert rv.status_code == 400
        assert "error" in rv.get_json()


def test_admin_week_post_form_validation_redirects(app, monkeypatch):
    monkeypatch.setattr("app.admin_routes.save_week_entry", lambda *a, **k: (True, "ok"))

    class _Svc:
        def resolve_season(self, raw):
            return str(raw)

        def refresh_data(self):
            return True, "ok"

    app.config["LEAGUE_SERVICE"] = _Svc()

    with app.test_client() as client:
        client.post("/admin/unlock", data={"pin": "4242"})
        rv = client.post(
            "/admin/week",
            data={
                "payload": '{"season": "Season 10", "week": 1, "rows": [{"team": "Team A", "player_display_name": "Alice", "game1": 0}]}'
            },
            follow_redirects=False,
        )
        assert rv.status_code == 302
        assert "error=" in rv.headers["Location"]
