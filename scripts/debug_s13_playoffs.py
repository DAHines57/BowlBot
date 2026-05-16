"""Debug Season 13 playoff W/L and bracket placement."""
from __future__ import annotations

from db.facts_loader import load_all_facts
from placement_bracket import winner_loser_from_matchup
from stats.compute import get_week_matchups

facts = load_all_facts()
WEEKS = (8, 9, 10)

for w in WEEKS:
    md = get_week_matchups(facts, w, season="Season 13", season_num=13)
    print(f"\n=== Week {w} matchups ===")
    for m in md.get("matchups", []):
        away = m.get("away")
        if not away:
            print(f"  SOLO {m['home']['name']}")
            continue
        h, a = m["home"], away
        wl = winner_loser_from_matchup(m)
        print(
            f"  {h['name']} {h['wins']}{h['result']} vs {a['name']} {a['wins']}{a['result']}"
            f"  -> winner_loser={wl}"
        )
