"""S13 semis loss-band split detail."""
from __future__ import annotations

from db.facts_loader import load_all_facts
from image_generator import (
    _parallel_model_from_loss_band,
    _playoff_losses_through_prior_rounds,
    _split_semis_by_playoff_loss_band,
    compute_bracket_rounds,
)
from league_data import create_league_data
from placement_bracket import winner_loser_from_matchup
from stats.compute import get_week_matchups, get_team_scores, sort_teams_for_playoff_seeding

facts = load_all_facts()
create_league_data()
season, sn = "Season 13", 13

snapshots = []
for w in (8, 9, 10):
    md = get_week_matchups(facts, w, season=season, season_num=sn)
    snapshots.append(md if "error" not in md else None)

ms1 = list(snapshots[1]["matchups"])
losses = _playoff_losses_through_prior_rounds(snapshots, 1)
print("Losses before semis:")
for t in sorted(losses):
    print(f"  {t}: {losses[t]}")

print("\nWeek 9 matchups:")
for m in ms1:
    away = m.get("away")
    if not away:
        continue
    h, a = m["home"]["name"], away["name"]
    hr, ar = m["home"].get("result"), away.get("result")
    lh, la = losses.get(h, 0), losses.get(a, 0)
    wl = winner_loser_from_matchup(m)
    print(f"  {h} ({hr}) vs {a} ({ar})  losses {lh}/{la}  wl={wl}")

wb, lb, other = _split_semis_by_playoff_loss_band(snapshots, ms1)
print(f"\nSplit: wb={len(wb)} lb={len(lb)} other={len(other)}")
for label, group in [("WB", wb), ("LB", lb), ("OTHER", other)]:
    for m in group:
        h, a = m["home"]["name"], m["away"]["name"]
        print(f"  {label}: {h} vs {a}")

qf_ms = list(snapshots[0]["matchups"])
ms2 = list(snapshots[2]["matchups"]) if snapshots[2] else []
svc = get_team_scores(facts, None, season, season_num=sn)
sorted_teams = sort_teams_for_playoff_seeding(svc)
rounds = compute_bracket_rounds([n for n, _ in sorted_teams])
par = _parallel_model_from_loss_band(snapshots, ms1, ms2, qf_ms, rounds[0])
print("\nparallel model:", "yes" if par else "no", par.get("w3_hits") if par else "")
