# Phase 5 — Player PAR (Pins Above Replacement)

**Status:** Done.

## Goal

Add **PAR** to the All players page **Other stats** view: cumulative pins above a league baseline, per game, with season-aware baselines and career totals for **All seasons**.

PAR is **not** stored in Excel or Postgres; it is computed in `stats/compute.py` from `player_weeks` facts (same source as averages and std dev).

## Definition

| Term | Meaning |
|------|--------|
| **PAR** | Sum over counted games: `game_score − baseline` |
| **Baseline** | League average pin level for that game’s season/week window |
| **Replacement** | Operational name only; baseline = **league mean**, not a below-average scrub level |

Display as integer pins (e.g. `+142`, `−38`).

## Counting rules (aligned with player averages)

**Player games (numerator):**

- Include each pin in `game1`–`game5` on a row where the player is **not absent** (same as `get_player_scores` `scores` list).
- **Substitute** rows are included if they contribute games (matches current `get_player_scores`).

**League baseline pool (denominator for averages):**

- Non-**absent** rows with at least one positive game score.
- **Substitute** rows **excluded** from league averages (stable “regular league” bar).
- Playoff weeks **included** (same as general season stats unless changed later).

## Baseline by week (per season)

Constant: `PAR_EARLY_WEEK_CUTOFF = 4` (weeks 1–3 vs 4+).

For a game in **season** `S`, **week** `W`:

| Week | Baseline |
|------|----------|
| **W &lt; 4** | **Full-season** league average for season **S − 1** (all countable games in that prior season). |
| **W ≥ 4** | **Year-to-date** league average for season **S**: mean of all countable games with `week ≤ W`. |

**First season** (no `S − 1` in data): for weeks 1–3, use **current-season YTD** through that week (same formula as week 4+, may be noisy early).

**End of season:** YTD through the last week equals the full-season average for that year.

## All seasons scope

Do **not** use one blended all-time league average.

- Compute PAR **per season** using the rules above.
- **Career PAR** = sum of seasonal PAR totals per player (canonical `player_display_name`).

## UI

- **Main stats:** unchanged (#, Player, Team, Avg, High, Low, Weeks/Games).
- **Other stats:** Weeks/Games, Std dev, **PAR**, Absences (sortable).
- Short footnote near the table, e.g.  
  `PAR: weeks 1–3 vs prior season avg; week 4+ vs season avg (YTD).`

Existing league summary blocks (high/low, league avg) stay as-is.

## API / code layout

| Layer | Responsibility |
|-------|----------------|
| `stats/compute.py` | `build_par_baselines(facts)`, `compute_player_par(facts, …)` |
| `league_data.py` | `get_player_par(season)` |
| `league_service.py` | Merge `par` into `pdata` on `players_page` (and top-players if applicable) |
| `image_generator.py` | PAR column + footnote in `build_players_html` |

## Tests

- Prior-season baseline for week 2.
- Week 4+ uses season YTD, not prior season.
- First season fallback (no S−1).
- Career sum across two seasons.
- Absent week contributes no player games.

## Non-goals (this phase)

- Converting PAR to team **wins** (WAR-style).
- Per-week PAR column on player detail page.
- Median baseline or fixed pin floor (mean only unless spec changes).

## Related

- [Phase 3 — App reads from DB](phase-3-app-integration.md)
- `get_league_game_stats` — weekly/season league average for summary cards
- `get_player_scores` — player game list for averages
