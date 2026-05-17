# Phase 1 — Schema and migrations

**Goal:** Define tables that mirror the v5 sheet tall model and support the stats the site already computes, with versioned migrations and a reproducible local dev database.

## Outcomes

- PostgreSQL running locally (Docker or native) and on Railway (dev/staging).
- Migration tool chosen (e.g. **Alembic** with SQLAlchemy, or **Flyway**-style SQL folders).
- Initial schema applied with empty or seed data optional.

## Entity sketch

Align names and semantics with `sheets_handler.py` / workbook columns:

1. **seasons** — `id` equals league `number` (e.g. both `11` for Season 11), plus `sheet_key`, `label`, optional `sort_order`.
2. **teams** — `id`, `season_id`, `name` (unique per season).
3. **players** — `id`, optional canonical `display_name`; link to teams is **per season** via roster or derive from weekly rows.
4. **player_weeks** (fact table) — one row per player per week per season:
   - `season_id`, `week`, `team_id` (or denormalized team name at ingest time),
   - `game1` … `game5` (nullable numeric),
   - `week_average` (optional denormalized),
   - `absent`, `substitute`, `playoffs` (booleans or char flags to match sheet),
   - `opponent` (text or FK to `teams` if normalized later),
   - **Ingest metadata:** `source_row_fingerprint` or `updated_at` for sync idempotency.

Start **denormalized** where it matches the sheet (e.g. store opponent string) to keep Phase 2 ingest simple; normalize in a later sub-phase if needed.

## Indexes

- `(season_id, week)` for weekly views.
- `(season_id, player_id)` or `(season_id, player_display_name)` depending on whether `players` is populated in Phase 1.
- Consider partial indexes for `absent = false` if large seasons.

## Deliverables

- [ ] `DATABASE_URL` documented in README / SETUP for local copy-paste.
- [ ] Migration `001_initial` creating tables above.
- [ ] Optional `make db-up` or `docker compose` snippet for Postgres only.
- [ ] CI step that runs migrations against a throwaway DB (optional but valuable).

## Risks / notes

- **Player identity:** Sheet uses display names; matching “same person across seasons” may stay string-based until you add stable player IDs.
- **Ingest:** Excel via `sync_db.py` is the only ingest path; row shape is defined in `sheets_handler.py`.
