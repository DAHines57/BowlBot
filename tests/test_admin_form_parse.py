"""Tests for admin roster form parsing."""
from app.admin_routes import (
    _admin_debug_tools_enabled,
    _parse_teams_form,
    _players_for_team_index,
    _team_indices_from_form,
)


class _FakeForm:
    def __init__(self, data: dict, lists: dict | None = None):
        self._data = data
        self._lists = lists or {}

    def get(self, key, default=""):
        return self._data.get(key, default)

    def getlist(self, key):
        return list(self._lists.get(key, []))

    def __iter__(self):
        yield from self._data
        for k in self._lists:
            yield k


def test_players_from_pick_only(monkeypatch):
    from app import admin_routes

    fake = _FakeForm(
        {"teams[0][name]": "Pins"},
        {"teams[0][player_pick][]": ["Alice", "Bob"]},
    )
    monkeypatch.setattr(admin_routes, "request", type("R", (), {"form": fake})())
    assert _players_for_team_index(0) == ["Alice", "Bob"]


def test_parse_teams_form_id_and_color(monkeypatch):
    from app import admin_routes

    fake = _FakeForm(
        {
            "teams[0][name]": "Pins",
            "teams[0][id]": "42",
            "teams[0][color_hex]": "#AABBCC",
        },
        {"teams[0][player_pick][]": ["Alice"]},
    )
    monkeypatch.setattr(admin_routes, "request", type("R", (), {"form": fake})())
    teams = _parse_teams_form()
    assert teams[0]["id"] == "42"
    assert teams[0]["color_hex"] == "#AABBCC"
    assert teams[0]["players"] == ["Alice"]


def test_parse_teams_form_captain_and_effective_week(monkeypatch):
    from app import admin_routes

    fake = _FakeForm(
        {
            "effective_week": "8",
            "teams[0][name]": "Team A",
            "teams[0][captain]": "Alice",
        },
        {"teams[0][player_pick][]": ["Alice", "Bob"]},
    )
    monkeypatch.setattr(admin_routes, "request", type("R", (), {"form": fake})())
    assert admin_routes._effective_week_from_form() == 8
    teams = admin_routes._parse_teams_form()
    assert teams[0]["captain"] == "Alice"


def test_parse_teams_form_with_picks(monkeypatch):
    from app import admin_routes

    fake = _FakeForm(
        {
            "teams[0][name]": "Team A",
            "teams[1][name]": "Team B",
        },
        {
            "teams[0][player_pick][]": ["Alice"],
            "teams[1][player_pick][]": ["Carl"],
        },
    )
    monkeypatch.setattr(admin_routes, "request", type("R", (), {"form": fake})())
    teams = _parse_teams_form()
    assert len(teams) == 2
    assert teams[0]["players"] == ["Alice"]
    assert teams[1]["players"] == ["Carl"]


def test_admin_debug_tools_follows_debug(monkeypatch):
    monkeypatch.setenv("DEBUG", "false")
    assert _admin_debug_tools_enabled() is False
    monkeypatch.setenv("DEBUG", "true")
    assert _admin_debug_tools_enabled() is True
