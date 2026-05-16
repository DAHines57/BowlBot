"""Playoff bracket column layout (classic 8-team placement finals)."""
from __future__ import annotations

from image_generator import (
    _best_w3_groups,
    _eight_team_week3_placement_column,
    _week3_match_count,
    compute_bracket_rounds,
)


def _m(home: str, away: str, hr: str, ar: str) -> dict:
    return {
        "home": {"name": home, "result": hr, "pins": 0, "avg": 0, "game_pins": [], "wins": 0},
        "away": {"name": away, "result": ar, "pins": 0, "avg": 0, "game_pins": [], "wins": 0},
    }


def _solo(name: str) -> dict:
    return {"home": {"name": name, "result": "W", "pins": 0, "avg": 0, "game_pins": [], "wins": 0}}


def test_week3_classic_four_placement_games_parallel_semis():
    """Parallel semis → four labeled finals blocks (S11-style layout)."""
    teams = [f"T{i}" for i in range(1, 9)]
    rounds = compute_bracket_rounds(teams)
    qf = [
        _m("T1", "T8", "W", "L"),
        _m("T4", "T5", "W", "L"),
        _m("T2", "T7", "W", "L"),
        _m("T3", "T6", "W", "L"),
    ]
    ms1 = [
        _m("T1", "T4", "W", "L"),
        _m("T2", "T3", "W", "L"),
        _m("T8", "T5", "W", "L"),
        _m("T7", "T6", "W", "L"),
    ]
    ms2 = [
        _m("T1", "T2", "W", "L"),
        _m("T4", "T3", "L", "W"),
        _m("T8", "T7", "W", "L"),
        _m("T5", "T6", "L", "W"),
    ]
    w3 = _best_w3_groups(qf, ms1, ms2, rounds[0])
    assert _week3_match_count(ms2, w3) == 4

    snaps = [{"matchups": qf}, {"matchups": ms1}, {"matchups": ms2}]
    html = _eight_team_week3_placement_column(
        {"matchups": ms2}, snaps, {}, rounds
    )
    assert html is not None
    assert "1st &amp; 2nd place" in html or "1st & 2nd place" in html
    assert "bracket-cl-match" in html
    assert "bracket-pair-wrap" not in html


def test_week3_ignores_solo_rows_and_still_classic():
    """Extra lone 'advances' rows must not force the hover-card fallback UI."""
    teams = [f"S{i}" for i in range(1, 9)]
    rounds = compute_bracket_rounds(teams)
    qf = [
        _m("S1", "S8", "W", "L"),
        _m("S4", "S5", "W", "L"),
        _m("S2", "S7", "W", "L"),
        _m("S3", "S6", "W", "L"),
    ]
    ms1 = [
        _m("S1", "S4", "W", "L"),
        _m("S2", "S3", "W", "L"),
        _m("S8", "S5", "W", "L"),
        _m("S7", "S6", "W", "L"),
    ]
    ms2 = [
        _solo("S5"),
        _m("S1", "S2", "W", "L"),
        _m("S4", "S3", "L", "W"),
        _solo("S8"),
        _m("S7", "S6", "W", "L"),
        _m("S5", "S6", "L", "W"),
    ]
    snaps = [{"matchups": qf}, {"matchups": ms1}, {"matchups": ms2}]
    html = _eight_team_week3_placement_column(
        {"matchups": ms2}, snaps, {}, rounds
    )
    assert html is not None
    assert "bracket-subsec-h--title" in html
    assert html.count("bracket-cl-outer") >= 4
