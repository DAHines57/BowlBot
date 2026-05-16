"""Inspect playoff weeks for seasons 2-4."""
from __future__ import annotations

from league_data import create_league_data


def main() -> None:
    data = create_league_data()
    for sn in (2, 3, 4):
        season = f"Season {sn}"
        weeks = data.list_weeks_for_season(season)
        pweeks = sorted(data.list_playoff_weeks_for_season(season))
        print(f"=== {season} ===")
        print("  weeks:", weeks, "playoff:", pweeks)
        for w in pweeks:
            md = data.get_week_matchups(w, season)
            ms = md.get("matchups", []) if md else []
            played = [m for m in ms if m.get("away")]
            print(f"  week {w}: {len(played)} h2h")
            for m in played:
                h, a = m["home"]["name"], m["away"]["name"]
                print(f"    {h} ({m['home'].get('result')}) vs {a} ({m['away'].get('result')})")
        print()


if __name__ == "__main__":
    main()
