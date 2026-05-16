# Phase 2 — Ingest from sheets

**Goal:** Load or refresh the database from the existing SheetHandler pipeline so the DB always reflects the spreadsheet after a sync run.

## Outcomes

- A scripted **ETL** (CLI command or Celery-less cron-friendly script) that:
  1. Opens the workbook / sheet via current `SheetHandler` factory.
  2. Enumerates seasons and walks rows in the same way as `get_player_scores` / `get_team_scores` inputs (or a dedicated “export iterator” in code to avoid triple-scanning).
  3. **Upserts** into `player_weeks` (and `seasons` / `teams` / `players` as needed).
- Idempotent runs: re-running sync does not duplicate weeks; optionally delete-and-reload per season for simplicity in v1.

## Design choices

| Approach | Pros | Cons |
|----------|------|------|
| **Truncate season + bulk insert** | Simple, always consistent | Brief empty window; harder if multiple readers |
| **Upsert on `(season_id, player_key, week)`** | No full wipe | Needs stable keys and conflict rules |
| **Change log from sheet** (advanced) | Minimal writes | Sheets API may not expose row-level revision easily |

Recommendation for v1: **per-season replace** inside a transaction (delete facts for season `N`, insert fresh rows).

## Triggers

- **Manual:** `python -m bowlbot.sync_db` (name TBD).
- **HTTP:** Extend existing `POST /reload?key=...` to optionally run DB sync after in-memory sheet reload, or add `POST /sync-db?key=...`.
- **Scheduled:** Railway cron or GitHub Action hitting the sync endpoint with secret (if publicly deployed).

## Deliverables

- [ ] `SheetHandler` method or shared module that yields normalized **PlayerWeek** dicts (one dict per row).
- [ ] Sync script with logging (rows read, seasons written, duration).
- [ ] Dry-run mode (`--dry-run`) counting rows without writing.
- [ ] Basic validation: compare aggregated season averages against existing `get_league_stats` output in a one-off test.

## Risks

- **Stale cache:** If only in-memory reload runs and DB sync fails silently, app could show mixed sources; Phase 3 should make source explicit.
- **Rate limits:** Google Sheets API quotas during full re-scan; batch reads if using `gspread` range fetch instead of cell-by-cell.
