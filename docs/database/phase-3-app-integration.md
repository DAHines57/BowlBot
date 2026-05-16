# Phase 3 — App integration (read path)

**Goal:** Serve league stats from PostgreSQL when enabled, with fallback to live sheets.

## Architecture (fact-based)

```
app/routes.py → league_service.LeagueService
                    → league_data.LeagueDataSource
                        → SheetLeagueData  (iter_player_week_rows → stats.compute)
                        → DbLeagueData     (load_all_facts → stats.compute)
                        → HybridLeagueData (USE_DB_READS + db_has_data)
```

- **Facts:** one dict per player-week row (`team`, `player_display_name`, `season_number`, `week`, `game1`–`game5`, `week_average`, `absent`, `substitute`, `playoffs`, `opponent`, optional `game5_winner`).
- **Compute:** all aggregation lives in `stats/compute.py` so sheet and DB paths stay aligned.
- **No fake workbook:** DB reads do not rebuild an Excel proxy.

## Env

- `USE_DB_READS=1` — prefer Postgres when `player_weeks` has rows.
- `DATABASE_URL` — required for DB reads and sync.

## Outcomes

- [x] `LeagueDataSource` + `create_league_data(handler)`
- [x] Parity for team standings, players, leaders, weeks, matchups (via shared compute)
- [x] `GET /health` → `read_source`

## Rollout

1. Deploy with `USE_DB_READS=0`, run sync on schedule.
2. Compare staging HTML/JSON vs sheets.
3. Flip `USE_DB_READS=1` in staging, then production.

## Risks

- Rounding, absent/substitute, playoff filtering — validate with `sync_db.py` + spot checks after sheet changes.
