# Phase 3 — App reads from the database

**Status:** Done. The web app reads **only** from PostgreSQL.

## Architecture

```
Excel (v5)  →  sync_db.py  →  Postgres   (frozen seasons — see phase-6)
Admin/API   →  player_week_writes  →  Postgres   (live season — phase-7+)
                                    ↓
                         db/facts_loader.py  →  stats/compute.py
                                    ↓
                         league_data.DbLeagueData  →  league_service.py  →  Flask routes
```

- **`create_league_data()`** returns `DbLeagueData` when `DATABASE_URL` is set and `player_weeks` has rows; otherwise the app shows a “run sync” error.
- **`read_source`** is always `"database"` (see `GET /health`).
- There is no feature flag and no in-process sheet cache for HTTP requests.

## Facts shape

One dict per `player_weeks` row: `team`, `player_display_name`, `season_number`, `week`, `game1`–`game5`, `week_average`, `absent`, `substitute`, `playoffs`, `opponent`, etc. See `db/facts_loader.py`.

Weekly **W/L/T** for display:

1. **`matchup_overrides`** when a row exists for `(season, week, team)`.
2. Otherwise pin-by-game comparison in `stats/compute.py`.

## Refreshing data

| Mechanism | Behavior |
|-----------|----------|
| `python sync_db.py` | Import/repair **frozen** seasons from Excel → Postgres (skips DB-managed unless `--force`) |
| `POST /refresh?key=…` | Re-read facts from Postgres into process cache (`RELOAD_SECRET`; `/reload` is an alias) |
| DB write API | Phase 7–8 — upsert `player_weeks`, then `POST /refresh` or restart |

## Deliverables (complete)

- [x] `DbLeagueData` implements `LeagueDataSource`.
- [x] All pages use `stats/compute` on loaded facts.
- [x] `matchup_overrides` loaded for override-aware standings and matchups.
- [x] Health endpoint reports `read_source: database`.

## Non-goals

- Reading Google Sheets or Excel at request time in the web process.
- Hybrid fallback if the DB is empty (fail fast with setup instructions instead).
