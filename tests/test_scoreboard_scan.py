"""Unit tests for scoreboard scan validation (no API / images)."""
from scoreboard_scan import extract_score_rows, validate_extract

SWEET_PIN_EXTRACT = {
    "player_rows": [
        {"games": [181, 159, 200, 166]},
        {"games": [150, 135, 160, 199]},
        {"games": [177, 177, 177, 177]},
        {"games": [173, 173, 173, 173]},
    ],
    "team_scratch_by_game": [681, 644, 710, 715],
    "team_grand_scratch": 2750,
}


def test_validate_extract_passes_for_consistent_board():
    assert validate_extract(SWEET_PIN_EXTRACT) == []


def test_validate_extract_catches_team_game_sum():
    bad = {**SWEET_PIN_EXTRACT, "team_scratch_by_game": [680, 644, 710, 715]}
    errors = validate_extract(bad)
    assert any("Team game 1" in e for e in errors)


def test_validate_extract_catches_grand_scratch():
    bad = {**SWEET_PIN_EXTRACT, "team_grand_scratch": 2700}
    errors = validate_extract(bad)
    assert any("grand scratch" in e for e in errors)


def test_extract_score_rows():
    rows = extract_score_rows(SWEET_PIN_EXTRACT)
    assert len(rows) == 4
    assert rows[0]["row_index"] == 0
    assert rows[0]["game1"] == 181 and rows[0]["game4"] == 166
    assert rows[3]["game1"] == 173
