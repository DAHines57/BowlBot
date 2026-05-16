"""Debug Season 9 week 8: The Damned vs Rolling Stoned."""
from __future__ import annotations

from db.facts_loader import load_all_facts
from stats.compute import games_list, get_week_matchups

facts = load_all_facts()
s9w8 = [f for f in facts if f.get("season_number") == 9 and f.get("week") == 8]
teams = ["The Damned", "Rolling Stoned"]
for t in teams:
    rows = [f for f in s9w8 if f.get("team") == t and not f.get("substitute")]
    print("===", t, "rows", len(rows))
    opp = {str(f.get("opponent") or "") for f in rows}
    g5w = {str(f.get("game5_winner") or "") for f in rows if f.get("game5_winner")}
    pins = [0] * 5
    for f in rows:
        if f.get("absent"):
            continue
        for i, g in enumerate(games_list(f)):
            if i < 5:
                pins[i] += int(g)
    print("  opponents", opp)
    print("  game5_winner", g5w)
    print("  team game_pins", pins, "sum", sum(pins))

md = get_week_matchups(facts, 8, season="Season 9", season_num=9)
for m in md.get("matchups", []):
    h, a = m["home"], m.get("away")
    if not a:
        continue
    names = {h["name"], a["name"]}
    if "Damned" in str(names) or "Rolling" in str(names):
        print(
            "MATCHUP:",
            h["name"],
            h["wins"],
            h["result"],
            "|",
            a["name"],
            a["wins"],
            a["result"],
        )
        print("  game_pins h", h.get("game_pins"), "a", a.get("game_pins"))
        print("  game_results", m.get("game_results"))
        print("  g5 note", m.get("game5_series_note"))
