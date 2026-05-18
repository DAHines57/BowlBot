# Database plan (BowlBot)

The app serves league stats from **PostgreSQL** (`db/facts_loader.py` + `stats/compute.py`). Data is imported from a local **Excel v5** file via `sync_db.py`. This folder documents the database rollout.

**Source of truth:** The spreadsheet (edited in Excel) is canonical for scores; Postgres is a **materialized cache** refreshed by sync.

| Phase | Focus | Status |
|-------|--------|--------|
| 1 | Schema, migrations, local Postgres | Done — [phase-1](phase-1-schema-and-migrations.md) |
| 2 | Ingest / sync from Excel → DB | Done — [phase-2](phase-2-ingest-from-sheets.md) |
| 3 | App reads from DB | Done — [phase-3](phase-3-app-integration.md) |
| 4 | Production, ops | [phase-4](phase-4-production-and-ops.md) |
| 5 | Player PAR (Other stats) | Done — [phase-5](phase-5-player-par.md) |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection (web app + `sync_db.py`) |
| `EXCEL_FILE_PATH` | v5 workbook for `sync_db.py` (default `Bowling-Friends League v5.xlsx`) |
| `RELOAD_SECRET` | Optional; `POST /reload?key=…` re-syncs from Excel |
| `DEBUG` | Flask debug mode locally |

## Non-goals (initial phases)

- Replacing the spreadsheet UI for stat entry on day one.
- Real-time two-way sync without a defined ownership model.
- Google Sheets as a runtime data source.

## Related code

- `sheets_handler.py` — normalized rows for sync (Excel only).
- `db/facts_loader.py` — load facts and `matchup_overrides` for the app.
- `league_data.py` — `DbLeagueData` for Flask.
- `league_service.py` — pages and HTML.
