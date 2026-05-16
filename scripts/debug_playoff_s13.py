"""Debug Season 13 playoff week matchups vs bracket expectations."""
from image_generator import champion_from_playoff_snapshots
from league_data import create_league_data
from league_service import LeagueService

data = create_league_data()
if not data:
    raise SystemExit("No data source")
svc = LeagueService(data)
season = "Season 13"
pweeks, snaps = svc._playoff_snapshots_for_season(season)
print("playoff weeks:", pweeks)
for i, s in enumerate(snaps):
    pw = pweeks[i]
    if not s:
        print(f"\nWeek {pw}: (no data)")
        continue
    print(f"\n=== Week {pw} ===")
    for j, m in enumerate(s.get("matchups", [])):
        h = m.get("home", {})
        a = m.get("away")
        if a:
            print(
                f"  {j}: {h.get('name')} ({h.get('result')}) vs "
                f"{a.get('name')} ({a.get('result')})"
            )
        else:
            print(f"  {j}: {h.get('name')} only")

print("\nchampion_from_snapshots:", repr(champion_from_playoff_snapshots(snaps)))
