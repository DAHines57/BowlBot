# Phase 7 — Player week writes (DB entry layer)

**Status:** Done.

## Goal

Single **write path** for live data: upsert rows into `player_weeks` with the same normalization as Excel sync (team names, opponents, player/team entities).

Derived stats (averages, PAR, standings) stay in `stats/compute.py` — nothing new stored except facts.

## Row model

One row = unique `(season_id, week, team_id, player_display_name)` (existing constraint).

Payload fields (per player-week):

| Field | Notes |
|-------|--------|
| `team` | Canonicalized via `canonical_team_name` |
| `player_display_name` | Required |
| `week` | Integer ≥ 1 |
| `game1`–`game5` | Optional floats; omit or null = no score |
| `absent`, `substitute`, `playoffs` | Booleans |
| `opponent` | Resolved against season roster when possible |
| `week_average` | Optional; computed from games if omitted |

`source_row_fingerprint` is **null** for DB-entered rows (Excel sync keeps fingerprints).

## API surface (library)

| Function | Behavior |
|----------|----------|
| `upsert_player_week(session, season_number, row)` | One row upsert; returns `PlayerWeek` |
| `save_week_rows(session, season_number, week, rows)` | Upsert many rows for one week (league night) |

Season/team/player creation mirrors `db/sync.py` (`_get_or_create_season`, `_get_or_create_player`, team row per season).

## Cache invalidation

After any write, callers must clear `DbLeagueData` fact caches:

```python
data.reload_workbook()  # or POST /refresh after external DB changes
```

Phase 8 HTTP handlers will call this (or hit `/refresh`) after successful saves.

## Deliverables

- [x] `db/player_week_writes.py`
- [x] Unit tests (normalization / week average)
- [ ] Refactor shared season/team helpers out of `sync.py` if duplication hurts (optional)

## Non-goals

- HTTP routes or HTML forms (Phase 8).
- Bulk delete season / replace entire season from API (use frozen Excel sync for that).

## Related

- [Phase 6 — Data ownership](phase-6-data-ownership.md)
- [Phase 8 — Score entry UI](phase-8-score-entry.md)
