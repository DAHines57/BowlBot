# BowlBot — open review notes

Actionable items for the **current** codebase (Flask + Postgres + Excel sync).

---

## Performance (acceptable for current scale)

- `stats/compute.py` builds aggregates from in-memory fact lists; DB facts are cached per process in `DbLeagueData`.
- Re-run `sync_db.py` after workbook changes; `POST /refresh` if the web app is already running.

---

## Docs / ops

- **Excel** = historical import/repair; **Postgres** = source of truth for the live season (phases 6–8 in `docs/database/`).
- **`matchup_overrides`** — seeded from v4 for older seasons; used for W/L when rows exist.
- Phase docs: [docs/database/README.md](docs/database/README.md)

---

## Optional later

- Slim `SheetHandler` / `ExcelHandler` to `iter_player_week_rows` only (sync path); drop unused compute wrappers on the handler class.
- Extend `/health` with `SELECT 1` (see phase-4 doc).

---

## Resolved (kept for history)

- Google Sheets runtime (`gspread`, `GOOGLE_*` env) — removed.
- `USE_DB_READS` / `HybridLeagueData` — app is DB-only.
- `game5_winner` on `player_weeks` — dropped; use `matchup_overrides`.
- WhatsApp bot (`command_parser`, `bot_logic`) — removed.
- `add_score` on `SheetHandler` — removed.
- `db/matchup_overrides.py` — removed; constant lives in seed script.
- Debug scripts under `scripts/` — removed (batch C).
