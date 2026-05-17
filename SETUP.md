# BowlBot setup

The app is a **Flask website** backed by **PostgreSQL**. League data is imported from a local **Excel v5 workbook** (`sync_db.py`). See **[README.md](README.md)** for install, Docker, and run instructions.

## Environment (`.env`)

```env
DATABASE_URL=postgresql://bowlbot:bowlbot@localhost:5432/bowlbot_dev
EXCEL_FILE_PATH=Bowling-Friends League v5.xlsx
DEBUG=true
# RELOAD_SECRET=...   # optional: POST /reload?key=... re-syncs from Excel
```

Google Sheets credentials are not used. The web app does not read the workbook directly.

## Excel workbook (v5)

One sheet per season (e.g. `Season 13`), one row per player per week:

| Column | Notes |
|--------|--------|
| Team, Player, Season, Week | Identifiers |
| Game 1–5 | Pin scores |
| Average | Usually a formula in the sheet |
| Playoffs? | Y/N |
| Game 5 winner | Legacy column; may be blank (W/L uses `matchup_overrides` in DB) |
| Absent?, Substitute? | Y/N |
| Opponent | Opponent team name for the week |

After editing the file: `python sync_db.py` (or `POST /reload` if `RELOAD_SECRET` is set).

## Historical v4 data

- `migrate.py` — build a v5-style workbook from `Bowling- Friends League v4.xlsx`
- `scripts/seed_matchup_overrides.py` — load weekly W/L/T from v4 matchup columns into `matchup_overrides`

## Project layout

| Path | Role |
|------|------|
| `main.py` | Flask entry |
| `app/` | Routes |
| `league_service.py` | Pages + HTML |
| `league_data.py` | Postgres read API |
| `sync_db.py` | Excel → Postgres |
| `sheets_handler.py` | Excel row iterator (sync only) |
| `stats/` | Facts + aggregates |
| `db/` | Models, migrations, loaders |
