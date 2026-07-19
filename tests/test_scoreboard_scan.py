"""Unit tests for scoreboard scan validation and roster matching."""
from scoreboard_scan import (
    build_scan_response,
    extract_score_rows,
    match_player_name,
    match_scan_to_rosters,
    match_team_name,
    validate_extract,
)

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

DUAL_MONITOR_EXTRACT = {
    "teams": [
        {
            "name": "SPLITTIN SIDEWAYS",
            "players": [
                {"name": "BRANDON BARNES", "games": [144, 207, 188, 187]},
                {"name": "MINGO", "games": [191, 204, 179, 155]},
                {"name": "JOHNNY MCCORM...", "games": [174, 149, 157, 187]},
                {"name": "DANNY MCCORMACK", "games": [190, 161, 205, 159]},
            ],
            "team_scratch_by_game": [699, 721, 729, 688],
            "team_grand_scratch": 2837,
        },
        {
            "name": "CAN'T BELIEVE IT'S NOT GUTTER",
            "players": [
                {"name": "JAD ELAWAR", "games": [117, 152, 148, 125]},
                {"name": "DAVID CHALUH", "games": [149, 171, 127, 153]},
                {"name": "DYLAN HINES", "games": [222, 190, 216, 197]},
                {"name": "MIKE NASSIF", "games": [170, 170, 170, 170]},
            ],
            "team_scratch_by_game": [658, 683, 661, 645],
            "team_grand_scratch": 2647,
        },
    ]
}

ROSTERS = {
    "Splittin Sideways": [
        "Brandon Barnes",
        "Mingo",
        "Johnny McCormack",
        "Danny McCormack",
    ],
    "Can't Believe It's Not Gutter": [
        "Jad Elawar",
        "David Chaluh",
        "Dylan Hines",
        "Mike Nassif",
    ],
    "Other Team": ["Alice", "Bob", "Carol", "Dave"],
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


def test_validate_dual_monitor_passes():
    assert validate_extract(DUAL_MONITOR_EXTRACT) == []


def test_validate_dual_monitor_catches_footer():
    bad = {
        "teams": [
            {
                **DUAL_MONITOR_EXTRACT["teams"][0],
                "team_grand_scratch": 2800,
            },
            DUAL_MONITOR_EXTRACT["teams"][1],
        ]
    }
    errors = validate_extract(bad)
    assert any("grand scratch" in e for e in errors)


def test_match_truncated_player_name():
    name, score = match_player_name(
        "JOHNNY MCCORM",
        ["Johnny McCormack", "Danny McCormack", "Brandon Barnes"],
    )
    assert name == "Johnny McCormack"
    assert score >= 0.9


def test_match_team_name_loose():
    assert (
        match_team_name(
            "SPLITTIN SIDEWAYS",
            list(ROSTERS.keys()),
        )
        == "Splittin Sideways"
    )


def test_match_scan_to_rosters_dual():
    matched = match_scan_to_rosters(DUAL_MONITOR_EXTRACT, ROSTERS)
    assert len(matched) == 2
    assert matched[0]["matched_team"] == "Splittin Sideways"
    assert matched[0]["suggested_opponent"] == "Can't Believe It's Not Gutter"
    assert matched[0]["players"][2]["suggested_player"] == "Johnny McCormack"
    assert matched[0]["players"][0]["game1"] == 144
    assert matched[1]["matched_team"] == "Can't Believe It's Not Gutter"
    assert matched[1]["suggested_opponent"] == "Splittin Sideways"
    assert matched[1]["players"][2]["suggested_player"] == "Dylan Hines"


def test_build_scan_response():
    body = build_scan_response(DUAL_MONITOR_EXTRACT, ROSTERS)
    assert body["validation_errors"] == []
    assert len(body["teams"]) == 2
    assert len(body["score_rows"]) == 8


def test_admin_enter_shows_scan_without_team():
    from pathlib import Path

    text = Path("templates/admin_enter.html").read_text(encoding="utf-8")
    assert "{% if scoreboard_scan_enabled %}" in text
    assert "Select a team above to scan" not in text
    assert 'id="scan-teams-review"' in text
    assert "x: 0, y: 0, w: 1, h: 1" in text
    assert 'fd.append("team"' not in text
    assert "scan-opponent-assign" in text
    assert "suggested_opponent" in Path("scoreboard_scan.py").read_text(encoding="utf-8")
