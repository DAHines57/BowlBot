# Database plan (BowlBot)

The app serves league stats from **PostgreSQL** (`db/facts_loader.py` + `stats/compute.py`).

## Source of truth

| Data | Canonical source |
|------|------------------|
| **Closed seasons** | Excel v5 → imported via `sync_db.py` (repair/re-import only) |
| **Current & future seasons** | **PostgreSQL** (entered via write API — Phase 8) |

Excel is **not** the live scorebook after you set `LAST_EXCEL_IMPORTED_SEASON` and open a new season in the DB.

```
Historical:  Excel (v5)  ──sync──►  Postgres (frozen seasons)
Live:        Admin/API writes  ──►  Postgres (player_weeks)
                      │
                      ▼
              facts_loader  →  stats/compute  →  Flask pages
```

| Phase | Focus | Status |
|-------|--------|--------|
| 1 | Schema, migrations, local Postgres | Done — [phase-1](phase-1-schema-and-migrations.md) |
| 2 | Ingest / sync from Excel → DB | Done — [phase-2](phase-2-ingest-from-sheets.md) |
| 3 | App reads from DB | Done — [phase-3](phase-3-app-integration.md) |
| 4 | Production, ops | [phase-4](phase-4-production-and-ops.md) |
| 5 | Player PAR (Other stats) | Done — [phase-5](phase-5-player-par.md) |
| 6 | Data ownership & sync policy | In progress — [phase-6](phase-6-data-ownership.md) |
| 7 | Player week writes (DB layer) | In progress — [phase-7](phase-7-player-week-writes.md) |
| 8 | Score entry HTTP + UI | Done — [phase-8](phase-8-score-entry.md) |
| 9 | Matchup W/L/T entry (if needed) | Planned — [phase-9](phase-9-matchup-entry.md) |
| 10 | Admin hardening, backups, restore drill | Planned — [phase-10](phase-10-security-and-backups.md) |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection (web app + `sync_db.py`) |
| `EXCEL_FILE_PATH` | v5 workbook for `sync_db.py` (frozen seasons only) |
| `LAST_EXCEL_IMPORTED_SEASON` | Highest season number imported from Excel; seasons above are DB-managed (sync skipped) |
| `RELOAD_SECRET` | Optional; `POST /refresh?key=…` (or `/reload`) clears in-process fact cache after DB changes |
| `ADMIN_PIN` | Optional alphanumeric password for `/admin` (session after unlock) |
| `FLASK_SECRET_KEY` | Signs admin session cookies (set in production) |
| `DEBUG` | Flask debug mode locally |

## Non-goals

- Two-way Excel ↔ DB sync for the live season.
- Google Sheets as a runtime data source.

## Related code

- `db/data_ownership.py` — frozen vs live season policy.
- `db/player_week_writes.py` — upsert `player_weeks` (Phase 7).
- `db/sync.py` / `sync_db.py` — Excel import for frozen seasons.
- `sheets_handler.py` — Excel row iterator (sync only).
- `db/facts_loader.py` — load facts for the app.
- `league_data.py` — `DbLeagueData` for Flask.
