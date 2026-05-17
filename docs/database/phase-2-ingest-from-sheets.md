# Phase 2 — Ingest from Excel

**Status:** Done (`sync_db.py`, `db/sync.py`).

**Goal:** Load or refresh the database from the local v5 workbook so Postgres reflects the spreadsheet after a sync run.

## Outcomes

- A scripted **ETL** (CLI command or Celery-less cron-friendly script) that:
  1. Opens the workbook via `db/sheet_factory.py` (`ExcelHandler`).
  2. Enumerates seasons and walks rows in the same way as `get_player_scores` / `get_team_scores` inputs (or a dedicated “export iterator” in code to avoid triple-scanning).
  3. **Upserts** into `player_weeks` (and `seasons` / `teams` / `players` as needed).
- Idempotent runs: re-running sync does not duplicate weeks; optionally delete-and-reload per season for simplicity in v1.

## Design choices

| Approach | Pros | Cons |
|----------|------|------|
| **Truncate season + bulk insert** | Simple, always consistent | Brief empty window; harder if multiple readers |
| **Upsert on `(season_id, player_key, week)`** | No full wipe | Needs stable keys and conflict rules |
| **Change log from sheet** (advanced) | Minimal writes | Not used; full season replace per sync |

Recommendation for v1: **per-season replace** inside a transaction (delete facts for season `N`, insert fresh rows).

## Triggers

- **Manual:** `python sync_db.py` (`--dry-run`, `--season N`).
- **HTTP:** `POST /reload?key=...` runs `sync_database()` when `RELOAD_SECRET` is set.
- **Scheduled:** Railway cron or GitHub Action hitting the sync endpoint with secret (if publicly deployed).

## Deliverables

- [x] `ExcelHandler.iter_player_week_rows` yields normalized row dicts.
- [x] `sync_db.py` / `db/sync.py` with logging.
- [x] `--dry-run` and `--season` filters.

## Risks

- **Stale cache:** After sync, call `DbLeagueData.reload_workbook()` (or restart the app) so fact caches refresh; `/reload` does both sync and cache clear.
