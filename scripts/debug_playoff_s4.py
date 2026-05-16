"""Debug Season 4 playoff bracket fill."""
from __future__ import annotations

from league_data import create_league_data
from stats.compute import sort_teams_for_playoff_seeding
from image_generator import (
    _best_w3_groups,
    _eight_team_week3_path_band_column,
    _eight_team_week3_placement_column,
    _pick_best_eight_team_placement_model,
    _playoff_matchups_with_opponent,
    _semis_week_parallel_shape,
    _week3_match_count,
    compute_bracket_rounds,
)


def main() -> None:
    season = "Season 4"
    data = create_league_data()
    weeks = data.list_weeks_for_season(season)
    pweeks = sorted(data.list_playoff_weeks_for_season(season))
    print("all weeks:", weeks)
    print("playoff weeks:", pweeks)
    sw = min(pweeks) - 1 if pweeks else None
    print("seeding week:", sw)
    td = data.get_team_scores(None, season, through_week=sw)
    st = sort_teams_for_playoff_seeding(td)[:8]
    print("seeds:")
    for i, (n, s) in enumerate(st, 1):
        print(f"  {i} {n} W={s.get('wins')} pins={s.get('pins_for')}")
    seeded = [n for n, _ in st]
    rounds = compute_bracket_rounds(seeded)
    print("expected QF pairs (standard):", rounds[0])

    snaps = []
    for w in pweeks:
        md = data.get_week_matchups(w, season)
        snaps.append(md)
        ms = md.get("matchups", []) if md else []
        played = [m for m in ms if m.get("away")]
        print(f"\nweek {w}: {len(played)} h2h")
        for m in played:
            h, a = m["home"]["name"], m["away"]["name"]
            print(f"  {h} ({m['home'].get('result')}) vs {a} ({m['away'].get('result')})")

    if len(snaps) < 3:
        print("\nNeed 3 playoff weeks for full bracket logic.")
        return

    qf, ms1, ms2 = snaps[0]["matchups"], snaps[1]["matchups"], snaps[2]["matchups"]
    ms2p = _playoff_matchups_with_opponent(ms2)
    model = _pick_best_eight_team_placement_model(qf, ms1, ms2, rounds[0])
    print("\nmodel kind:", (model or {}).get("kind"))
    w3g = (model or {}).get("w3_groups") or []
    best = _best_w3_groups(qf, ms1, ms2p, rounds[0])
    print("w3 groups from model:", len(w3g))
    for g in w3g:
        print(" ", g[1], sorted(g[0]))
    print("best w3 match hits:", _week3_match_count(ms2p, best))
    for g in best:
        print(" ", g[1], sorted(g[0]))
    print("parallel semis shape:", _semis_week_parallel_shape(qf, ms1))
    w3html = _eight_team_week3_placement_column(snaps[2], snaps, {}, rounds)
    pathhtml = _eight_team_week3_path_band_column(snaps[2], snaps, {})
    print("placement column built:", bool(w3html))
    print("path band column built:", bool(pathhtml))


def sheet_weeks() -> None:
    from db.sheet_factory import get_handler_from_env
    from sheets_handler import ExcelHandler

    h = get_handler_from_env()
    if not isinstance(h, ExcelHandler):
        print("Not Excel handler")
        return
    rows = list(h.iter_player_week_rows(season_filter="Season 4"))
    print("sheet weeks:", sorted({r["week"] for r in rows}))
    for w in sorted({r["week"] for r in rows if r["week"] >= 7}):
        wrows = [r for r in rows if r["week"] == w]
        print(
            f"  week {w}: rows={len(wrows)} playoffs={any(r.get('playoffs') for r in wrows)}"
        )


if __name__ == "__main__":
    main()
    print()
    sheet_weeks()
