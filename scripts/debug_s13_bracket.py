"""S13 bracket model selection and loss bands."""
from __future__ import annotations

from db.facts_loader import load_all_facts
from image_generator import (
    _parallel_model_from_loss_band,
    _pick_best_eight_team_placement_model,
    _playoff_losses_through_prior_rounds,
    _qf_res_candidates,
    _semis_week_parallel_shape,
    compute_bracket_rounds,
)
from league_data import create_league_data
from placement_bracket import expected_week2_groups
from stats.compute import get_team_scores, get_week_matchups, sort_teams_for_playoff_seeding

facts = load_all_facts()
data = create_league_data()
season = "Season 13"
sn = 13

svc_data = get_team_scores(facts, None, season, season_num=sn)
if isinstance(svc_data, dict) and "error" in svc_data:
    print("team scores error", svc_data)
else:
    sorted_teams = sort_teams_for_playoff_seeding(svc_data)
    rounds = compute_bracket_rounds([n for n, _ in sorted_teams])

snapshots = []
for w in (8, 9, 10):
    md = get_week_matchups(facts, w, season=season, season_num=sn)
    snapshots.append(md if "error" not in md else None)

qf_ms = list(snapshots[0]["matchups"]) if snapshots[0] else []
ms1 = list(snapshots[1]["matchups"]) if snapshots[1] else []
ms2 = list(snapshots[2]["matchups"]) if snapshots[2] else []

print("QF slot results candidates (first 3):")
for i, qf_res in enumerate(_qf_res_candidates(qf_ms, rounds[0])[:3]):
    print(f"  cand {i}:", qf_res)
    wb, lb = expected_week2_groups(qf_res)
    print(f"    parallel WB pairs:", [sorted(x) for x in wb])
    print(f"    parallel LB pairs:", [sorted(x) for x in lb])

losses = _playoff_losses_through_prior_rounds(snapshots, 1)
print("\nPlayoff losses before semis (after QF):")
for t in sorted(losses):
    print(f"  {t}: {losses[t]}")

print("\nshape_parallel:", _semis_week_parallel_shape(qf_ms, ms1, snapshots=snapshots))
par = _parallel_model_from_loss_band(snapshots, ms1, ms2, qf_ms, rounds[0])
if par:
    print("loss_par w3_hits", par.get("w3_hits"))
    for i, m in enumerate(par.get("wb_ord") or []):
        if m:
            print(f"  WB semi {i}:", m["home"]["name"], "vs", m["away"]["name"])
    for i, m in enumerate(par.get("lb_ord") or []):
        if m:
            print(f"  LB semi {i}:", m["home"]["name"], "vs", m["away"]["name"])

model = _pick_best_eight_team_placement_model(qf_ms, ms1, ms2, rounds[0], snapshots=snapshots)
print("\nPicked model:", model["kind"] if model else None)
if model and model["kind"] == "parallel":
    for i, m in enumerate(model.get("wb_ord") or []):
        if m:
            print(f"  WB {i}:", m["home"]["name"], "vs", m["away"]["name"])
    for i, m in enumerate(model.get("lb_ord") or []):
        if m:
            print(f"  LB {i}:", m["home"]["name"], "vs", m["away"]["name"])
elif model and model["kind"] == "cross":
    for i, m in enumerate(model.get("cross_ord") or []):
        if m:
            print(f"  cross {i}:", m["home"]["name"], "vs", m["away"]["name"])
