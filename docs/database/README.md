# Database plan (BowlBot)

The app today loads league data from **Google Sheets** or a **local Excel** file via `sheets_handler.py` and serves HTML through `league_service.py`. This folder describes a phased approach to add a **relational database** (recommended: **PostgreSQL** on [Railway](https://railway.app) or similar) so production can scale reads, simplify queries, and optionally decouple from live sheet API latency.

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
| `USE_DB_READS` | If `1`, routes use DB-backed repositories when available. |
| `SHEET_HANDLER_TYPE` | Remains `gsheets` or `excel` for sync jobs and fallback. |

## Non-goals (initial phases)

- Replacing the spreadsheet UI for stat entry on day one.
- Real-time two-way sync (conflict resolution) without a defined ownership model.

## Related code

- `sheets_handler.py` — row shape (team, player, season, week, games, absent, substitute, opponent, playoffs).
- `league_service.py` — aggregates and HTML; eventually should call a data layer that can read from DB or sheets.
