"""Inspect Season 11 playoff opponent fields in DB facts."""
from __future__ import annotations

from db.facts_loader import load_all_facts
from league_data import create_league_data


def main() -> None:
    facts = load_all_facts()
    s11 = [f for f in facts if f.get("season_number") == 11 and f.get("week") in (8, 9, 10)]
    teams = sorted({str(f["team"]) for f in s11})
    print("S11 teams in DB (weeks 8-10):", teams)
    for w in (8, 9, 10):
        print(f"--- week {w}")
        by_team: dict[str, dict] = {}
        for f in s11:
            if f.get("week") != w:
                continue
            t = str(f["team"])
            if t not in by_team:
                by_team[t] = {"opp": set(), "n": 0}
            by_team[t]["n"] += 1
            o = f.get("opponent")
            if o:
                by_team[t]["opp"].add(str(o).strip())
        for t in sorted(by_team):
            print(f"  {t}: player_rows={by_team[t]['n']} opponents={by_team[t]['opp']}")

    data = create_league_data()
    for w in (8, 9, 10):
        md = data.get_week_matchups(w, "Season 11")
        ms = md.get("matchups", [])
        print(f"\nmatchups API week {w}: {len(ms)} rows")
        for m in ms:
            away = m.get("away")
            if away:
                print(f"  {m['home']['name']} vs {away['name']}")
            else:
                print(f"  SOLO: {m['home']['name']}")


if __name__ == "__main__":
    main()
