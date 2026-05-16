"""Debug playoff layout for Season 10 vs 11."""
from __future__ import annotations

from league_data import create_league_data
from stats.compute import sort_teams_for_playoff_seeding
from image_generator import (
    _best_w3_groups,
    _eight_team_week3_placement_column,
    _pick_best_eight_team_placement_model,
    _playoff_matchups_with_opponent,
    _semis_week_parallel_shape,
    _week3_match_count,
    compute_bracket_rounds,
)


def main() -> None:
    data = create_league_data()
    for season in ("Season 10", "Season 11"):
        pweeks = sorted(data.list_playoff_weeks_for_season(season))
        print("===", season, "weeks", pweeks)
        snaps = []
        for w in pweeks:
            md = data.get_week_matchups(w, season)
            snaps.append(md)
            ms = md.get("matchups", []) if md else []
            played = [m for m in ms if m.get("away")]
            solo = [m["home"]["name"] for m in ms if not m.get("away")]
            print(f"  w{w}: {len(ms)} rows, {len(played)} h2h, solos={solo}")
            for m in played:
                h, a = m["home"]["name"], m["away"]["name"]
                hr = m["home"].get("result")
                ar = m["away"].get("result")
                print(f"    {h} ({hr}) vs {a} ({ar})")
        sw = min(pweeks) - 1 if pweeks else 7
        td = data.get_team_scores(None, season, through_week=sw)
        sorted_teams = sort_teams_for_playoff_seeding(td)[:8]
        seeded = [n for n, _ in sorted_teams]
        rounds = compute_bracket_rounds(seeded)
        if len(snaps) >= 3 and snaps[0] and snaps[1] and snaps[2]:
            qf, ms1, ms2 = snaps[0]["matchups"], snaps[1]["matchups"], snaps[2]["matchups"]
            model = _pick_best_eight_team_placement_model(qf, ms1, ms2, rounds[0])
            ms2p = _playoff_matchups_with_opponent(ms2)
            w3g = (model or {}).get("w3_groups") or []
            best = _best_w3_groups(qf, ms1, ms2p, rounds[0])
            w3html = _eight_team_week3_placement_column(snaps[2], snaps, {}, rounds)
            print("  parallel semis:", _semis_week_parallel_shape(qf, ms1))
            print("  model:", (model or {}).get("kind"), "w3 hits:", _week3_match_count(ms2p, w3g))
            print("  best w3 hits:", _week3_match_count(ms2p, best))
            print("  classic finals:", bool(w3html))
        print()


def seeds() -> None:
    data = create_league_data()
    for season in ("Season 10", "Season 11"):
        pweeks = sorted(data.list_playoff_weeks_for_season(season))
        sw = min(pweeks) - 1
        td = data.get_team_scores(None, season, through_week=sw)
        st = sort_teams_for_playoff_seeding(td)[:8]
        print(season, "seeds:")
        for i, (n, s) in enumerate(st, 1):
            print(
                f"  {i} {n} {s.get('wins', 0)}-{s.get('losses', 0)} "
                f"pins={s.get('pins_for', 0)} avg={s.get('avg_per_game', 0):.1f}"
            )
        rounds = compute_bracket_rounds([n for n, _ in st])
        print("  QF pairs:", rounds[0])


if __name__ == "__main__":
    main()
    seeds()
