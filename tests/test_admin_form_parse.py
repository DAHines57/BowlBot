"""Tests for admin roster form parsing."""
from app.admin_routes import _parse_teams_form, _players_for_team_index, _team_indices_from_form


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


def test_players_from_pick_and_new(monkeypatch):
    from app import admin_routes

    fake = _FakeForm(
        {
            "teams[0][name]": "Pins",
        },
        {
            "teams[0][player_pick][]": ["Alice", "__new__"],
            "teams[0][player_new][]": ["", "Zoe New"],
        },
    )
    monkeypatch.setattr(admin_routes, "request", type("R", (), {"form": fake})())
    assert _players_for_team_index(0) == ["Alice", "Zoe New"]


def test_parse_teams_form_with_picks(monkeypatch):
    from app import admin_routes

    fake = _FakeForm(
        {
            "teams[0][name]": "Team A",
            "teams[1][name]": "Team B",
        },
        {
            "teams[0][player_pick][]": ["Alice"],
            "teams[1][player_pick][]": ["__new__"],
            "teams[1][player_new][]": ["Brand New"],
        },
    )
    monkeypatch.setattr(admin_routes, "request", type("R", (), {"form": fake})())
    teams = _parse_teams_form()
    assert len(teams) == 2
    assert teams[0]["players"] == ["Alice"]
    assert teams[1]["players"] == ["Brand New"]
