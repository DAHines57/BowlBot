# Database plan (BowlBot)

The app serves league stats from **PostgreSQL** (`db/facts_loader.py` + `stats/compute.py`). Data is imported from a local **Excel v5** file via `sync_db.py`. This folder documents the database rollout (schema → ingest → app → ops).

**Source of truth (decision):** Until a later phase, treat the spreadsheet as canonical and use the database as a **materialized cache** or **sync target**. That avoids a big-bang rewrite and keeps manual sheet edits valid.

| Phase | Focus | Doc |
|-------|--------|-----|
| 1 | Schema, migrations, local Postgres | [phase-1-schema-and-migrations.md](phase-1-schema-and-migrations.md) |
| 2 | Ingest / sync from sheets → DB | [phase-2-ingest-from-sheets.md](phase-2-ingest-from-sheets.md) |
| 3 | App reads from DB (feature flag) | [phase-3-app-integration.md](phase-3-app-integration.md) |
| 4 | Production, ops, and optional writes | [phase-4-production-and-ops.md](phase-4-production-and-ops.md) |

## Environment variables (preview)

Names are indicative; finalize when implementing Phase 1.

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (Railway sets this for plugins). |
| `DATABASE_URL` | Required for the web app and `sync_db.py`. |
| `EXCEL_FILE_PATH` | v5 workbook for `sync_db.py` only (default `Bowling-Friends League v5.xlsx`). |

## Non-goals (initial phases)

- Replacing the spreadsheet UI for stat entry on day one.
- Real-time two-way sync (conflict resolution) without a defined ownership model.

## Related code

- `sheets_handler.py` — row shape (team, player, season, week, games, absent, substitute, opponent, playoffs).
- `league_service.py` — aggregates and HTML; eventually should call a data layer that can read from DB or sheets.
