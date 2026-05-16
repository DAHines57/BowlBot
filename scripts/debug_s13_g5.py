from db.facts_loader import load_all_facts
from stats.compute import filter_facts, get_week_matchups
from stats.facts import fifth_game_pins_decisive, games_list, safe_float

facts = load_all_facts()
week, sn = 8, 13
rows = filter_facts(facts, season_num=sn, week=week)
teams: dict = {}
for f in rows:
    team = str(f.get("team") or "").strip()
    player = str(f.get("player_display_name") or "").strip()
    if not team or not player:
        continue
    is_absent = bool(f.get("absent"))
    is_sub = bool(f.get("substitute"))
    if team not in teams:
        teams[team] = {
            "game_pins": [],
            "player_count": 0,
            "active_player_count": 0,
            "game5_bowler_count": 0,
        }
    if not is_sub:
        teams[team]["player_count"] += 1
        if not is_absent:
            teams[team]["active_player_count"] += 1
            if safe_float(f.get("game5")) > 0:
                teams[team]["game5_bowler_count"] += 1
        for i, g in enumerate(games_list(f)):
            gi = int(g)
            if i >= len(teams[team]["game_pins"]):
                teams[team]["game_pins"].append(gi)
            else:
                teams[team]["game_pins"][i] += gi

gutter_name = "Can't Believe it's not Gutter"
g, s = teams[gutter_name], teams["Spare me the drama"]
print("gutter", g)
print("spare", s)
print("decisive", fifth_game_pins_decisive(g, s))
print("first4 totals", sum(g["game_pins"][:4]), sum(s["game_pins"][:4]))

h, a = None, None
md = get_week_matchups(facts, week, season_num=sn)
for m in md["matchups"]:
    if m["home"]["name"] == gutter_name:
        h, a = m["home"], m["away"]
print("matchup", h["wins"], h["result"], a["wins"], a["result"])

for f in filter_facts(facts, season_num=sn, week=week):
    t = f.get("team")
    if t not in (gutter_name, "Spare me the drama"):
        continue
    g5 = f.get("game5_winner")
    if g5:
        print("g5_winner fact:", t, f.get("player_display_name"), g5)
