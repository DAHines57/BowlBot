"""Tests for DB player-week write helpers (Phase 7)."""
import pytest

from db.player_week_writes import _normalize_row, compute_week_average


def test_compute_week_average_from_games():
    avg = compute_week_average((200.0, 210.0, None, 220.0, 190.0))
    assert avg == pytest.approx(205.0)


def test_compute_week_average_honors_provided():
    assert compute_week_average((200.0, 210.0), 199.0) == 199.0


def test_compute_week_average_empty():
    assert compute_week_average((None, None, None, None, None)) is None


def test_compute_week_average_excludes_per_game_absent():
    avg = compute_week_average(
        (190.0, 220.0, 210.0, 200.0, None),
        game_absent=(True, False, False, False, False),
    )
    assert avg == pytest.approx((220 + 210 + 200) / 3)


def test_normalize_row_canonical_team_and_opponent():
    row = {
        "team": "Team A",
        "player_display_name": "Alice",
        "week": 2,
        "game1": 200,
        "game2": 210,
        "game3": None,
        "game4": None,
        "game5": None,
        "absent": False,
        "substitute": False,
        "substitute_scores_count": False,
        "substituted_for": None,
        "playoffs": False,
        "opponent": "team b",
    }
    out = _normalize_row(row, 9, ["Team A", "Team B"])
    assert out["team"] == "Team A"
    assert out["opponent"] == "Team B"
    assert out["week_average"] == pytest.approx(205.0)


def test_normalize_row_substitute_fields():
    row = {
        "team": "Team A",
        "player_display_name": "Jane",
        "week": 2,
        "game1": 200,
        "game2": 210,
        "game3": None,
        "game4": None,
        "game5": None,
        "absent": False,
        "substitute": True,
        "substitute_scores_count": True,
        "substituted_for": "Alice",
        "playoffs": False,
        "opponent": None,
    }
    out = _normalize_row(row, 9, ["Team A"])
    assert out["substitute"] is True
    assert out["substitute_scores_count"] is True
    assert out["substituted_for"] == "Alice"
