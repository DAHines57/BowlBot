"""Inspect Season 13 week 8 Gutter vs Spare — raw facts and game totals."""
from league_data import create_league_data

data = create_league_data()
md = data.get_week_matchups(8, "Season 13")

print("=== Matchup summary (compute) ===")
for m in md.get("matchups", []):
    h, a = m["home"], m.get("away")
    if not a:
        continue
    if "Gutter" not in h["name"] and "Gutter" not in a["name"]:
        continue
    print(f"{h['name']} {h['result']} ({h['wins']}W) vs {a['name']} {a['result']} ({a['wins']}W)")
    print(f"  pins {h['pins']} - {a['pins']}")
    for i, gr in enumerate(m.get("game_results") or [], 1):
        print(f"  game {i}: home {gr[0]} {gr[2]} vs away {gr[1]} {gr[3]}")

# Raw facts if PostgresLeagueData
facts_src = getattr(data, "facts", None) or getattr(data, "_facts", None)
if facts_src is None and hasattr(data, "load_facts"):
    facts_src = data.load_facts()

if facts_src:
    from stats.compute import filter_facts, parse_season_number, games_list

    sn = parse_season_number("Season 13")
    rows = filter_facts(facts_src, season_num=sn, week=8)
    for label in ("Spare", "Gutter"):
        print(f"\n=== Rows containing '{label}' ===")
        for f in rows:
            team = str(f.get("team") or "")
            if label.lower() not in team.lower():
                continue
            g5 = f.get("game5_winner")
            print(
                f"  {f.get('player_display_name')} team={team!r} opp={f.get('opponent')!r} "
                f"g5_winner={g5!r} games={games_list(f)}"
            )
