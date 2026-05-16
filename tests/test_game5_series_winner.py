"""Matchup series scoring edge cases."""
from stats.compute import get_week_matchups


def _matchup(facts, home: str, away: str, *, week: int, season_num: int):
    md = get_week_matchups(facts, week, season_num=season_num)
    for m in md["matchups"]:
        h, a = m["home"], m.get("away")
        if not a:
            continue
        if {h["name"], a["name"]} == {home, away}:
            return h, a
    raise AssertionError(f"no matchup {home} vs {away}")


def test_s9_w8_uses_game5_winner_when_pins_disagree():
  """Rolling Stoned won 3-2 on sheet; G1-4 pins favored The Damned without G5 scores."""
  from db.facts_loader import load_all_facts

  facts = load_all_facts()
  h, a = _matchup(facts, "Rolling Stoned", "The Damned", week=8, season_num=9)
  assert h["name"] == "Rolling Stoned"
  assert h["wins"] == 3 and h["result"] == "W"
  assert a["wins"] == 2 and a["result"] == "L"


def test_s13_w8_spare_wins_when_rosters_uneven_for_game5():
    """2-2 after four games; sheet game5_winner column awards Spare (not pin G5)."""
    from db.facts_loader import load_all_facts

    facts = load_all_facts()
    h, a = _matchup(
        facts,
        "Can't Believe it's not Gutter",
        "Spare me the drama",
        week=8,
        season_num=13,
    )
    assert h["wins"] == 2 and a["wins"] == 3
    assert h["result"] == "L" and a["result"] == "W"


def test_s7_w10_absent_bowlers_count_in_game_pins():
  """Absent bowler scores count toward per-game team totals and pin sums."""
  from db.facts_loader import load_all_facts

  facts = load_all_facts()
  h, a = _matchup(facts, "Rolling Stoned", "Spare Parts", week=10, season_num=7)
  assert h["game_pins"] == [656, 578, 715, 701]
  assert a["game_pins"] == [657, 627, 640, 605]
  assert h["pins"] == 2650
  assert a["pins"] == 2529
  assert h["wins"] == 2 and a["wins"] == 2
  assert h["result"] == "W" and a["result"] == "L"
