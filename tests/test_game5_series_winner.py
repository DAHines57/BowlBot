"""Matchup series scoring via matchup_overrides (legacy game5_winner column removed)."""
from stats.compute import get_week_matchups


def _matchup(
    facts,
    home: str,
    away: str,
    *,
    week: int,
    season_num: int,
    matchup_overrides=None,
):
    md = get_week_matchups(
        facts, week, season_num=season_num, matchup_overrides=matchup_overrides
    )
    for m in md["matchups"]:
        h, a = m["home"], m.get("away")
        if not a:
            continue
        if {h["name"], a["name"]} == {home, away}:
            return m, h, a
    raise AssertionError(f"no matchup {home} vs {away}")


def test_s9_w8_matchup_override_record():
    """Rolling Stoned 3-2 vs The Damned (sheet override, not pin totals)."""
    from db.facts_loader import load_all_facts, load_all_matchup_overrides

    facts = load_all_facts()
    overrides = load_all_matchup_overrides()
    m, h, a = _matchup(
        facts,
        "Rolling Stoned",
        "The Damned",
        week=8,
        season_num=9,
        matchup_overrides=overrides,
    )
    assert h["name"] == "Rolling Stoned"
    assert h["wins"] == 3 and h["result"] == "W"
    assert a["wins"] == 2 and a["result"] == "L"
    assert m["record_overridden"] is True


def test_s13_w8_spare_wins_via_override():
    """2-2 on pins; matchup_overrides awards Spare 3-2."""
    from db.facts_loader import load_all_facts, load_all_matchup_overrides

    facts = load_all_facts()
    overrides = load_all_matchup_overrides()
    _, h, a = _matchup(
        facts,
        "Can't Believe it's not Gutter",
        "Spare me the drama",
        week=8,
        season_num=13,
        matchup_overrides=overrides,
    )
    assert h["wins"] == 2 and a["wins"] == 3
    assert h["result"] == "L" and a["result"] == "W"


def test_s7_w10_absent_bowlers_count_in_game_pins():
    """Absent bowler scores count toward per-game team totals and pin sums."""
    from db.facts_loader import load_all_facts, load_all_matchup_overrides

    facts = load_all_facts()
    overrides = load_all_matchup_overrides()
    _, h, a = _matchup(
        facts,
        "Rolling Stoned",
        "Spare Parts",
        week=10,
        season_num=7,
        matchup_overrides=overrides,
    )
    assert h["game_pins"] == [656, 578, 715, 701]
    assert a["game_pins"] == [657, 627, 640, 605]
    assert h["pins"] == 2650
    assert a["pins"] == 2529
