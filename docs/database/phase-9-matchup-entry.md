# Phase 9 — Matchup results (optional)

**Status:** Planned.

## Goal

When the live season no longer uses Excel, decide how **weekly W/L/T** is recorded if not fully derivable from pins + `opponent`.

Today:

1. `matchup_overrides` for older seasons (v4 seed).
2. Pin comparison in `stats/compute.py` when no override exists.

## Options

| Approach | When to use |
|----------|-------------|
| **Derive only** | Pin totals + opponent are enough for your league rules |
| **Override table** | Extend `matchup_overrides` with admin entry per `(season, week, team)` |
| **New `matchup_results` table** | Cleaner than overloading overrides |

## Deliverables

- [ ] Product decision documented
- [ ] Write path + tests if overrides are manual

## Related

- [Phase 8 — Score entry](phase-8-score-entry.md)
