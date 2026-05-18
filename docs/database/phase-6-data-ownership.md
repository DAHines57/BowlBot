# Phase 6 — Data ownership (Excel historical, DB live)

**Status:** In progress.

## Goal

Define and enforce **two eras** of league data:

| Era | Source of truth | How data gets into Postgres |
|-----|-----------------|-----------------------------|
| **Frozen** (closed seasons) | Excel v5 (one-time / repair) | `sync_db.py` per-season replace |
| **Live** (current season onward) | **PostgreSQL** | App/API writes (`db/player_week_writes.py`) |

Historical scores stay in the DB after the final Excel import. **Do not** run Excel sync on a live season unless you intend to overwrite DB edits.

## Cutoff

Set after the last season fully imported from the workbook:

```env
LAST_EXCEL_IMPORTED_SEASON=13
```

| `season_number` | Excel sync (`sync_db.py`) | DB writes |
|-----------------|---------------------------|-----------|
| ≤ cutoff | Allowed (repair / re-import) | Allowed (corrections) |
| > cutoff | **Skipped** unless `--force` | **Primary** entry path |

If `LAST_EXCEL_IMPORTED_SEASON` is unset, behavior matches Phase 2 (all seasons sync from Excel) until you set the cutoff.

## Code

| Module | Responsibility |
|--------|----------------|
| `db/data_ownership.py` | `is_season_excel_importable`, `is_season_db_managed`, `last_excel_imported_season` |
| `db/sync.py` | Skip DB-managed seasons; `force=True` overrides |
| `sync_db.py` | `--force` flag |

## Operator workflow

1. **One-time:** Full sync of all closed seasons from v5 (`python sync_db.py`).
2. **Set** `LAST_EXCEL_IMPORTED_SEASON` to the highest imported season number.
3. **Open new season** in DB (create `Season` row when first week is saved — Phase 7).
4. **Weekly:** Enter scores via write API/UI (Phase 8); never sync the live season from Excel.
5. **Repair frozen season:** Edit Excel → `python sync_db.py --season N` only if `N ≤ cutoff`.

## Cache refresh (not Excel sync)

`POST /refresh` (and legacy `POST /reload`) only clear in-process caches and re-read from Postgres. They **do not** open the workbook. After `sync_db.py` or score entry, call refresh or restart the app.

## Deliverables

- [x] `db/data_ownership.py` + env `LAST_EXCEL_IMPORTED_SEASON`
- [x] Sync skips DB-managed seasons; `--force` on CLI
- [x] Update `docs/database/README.md`, `SETUP.md`, Phase 3 reload table
- [x] Document cutoff in `SETUP.md` / `README.md` env examples

## Non-goals

- Export-to-Excel (optional later).
- Changing `matchup_overrides` entry model (Phase 9).

## Related

- [Phase 2 — Ingest from Excel](phase-2-ingest-from-sheets.md) (frozen path)
- [Phase 7 — Player week writes](phase-7-player-week-writes.md)
