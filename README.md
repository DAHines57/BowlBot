# Bowl League

Web app for bowling league stats from **PostgreSQL**. League data is imported from a local **Excel v5 workbook** via `sync_db.py` (Google Sheets is no longer used at runtime).

Pages use the same purple / amber styling as the old recap images.

## Run locally

1. Python 3.11+ recommended.
2. `python -m venv venv` then activate (`venv\Scripts\activate` on Windows).
3. `pip install -r requirements.txt`
4. `.env` at minimum:

   ```
   DATABASE_URL=postgresql://bowlbot:bowlbot@localhost:5432/bowlbot_dev
   EXCEL_FILE_PATH=Bowling-Friends League v5.xlsx
   DEBUG=true
   ```

5. Postgres + schema + import (first time):

   ```powershell
   docker compose up -d
   alembic upgrade head
   python sync_db.py
   ```

6. `python main.py` → **http://127.0.0.1:3000** (`GET /health` → `"read_source": "database"`).

After you update the workbook, run `python sync_db.py` again (or `POST /reload?key=...` if `RELOAD_SECRET` is set — that re-syncs from Excel).

## Local PostgreSQL (Docker)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) running.

1. From the project root: `docker compose up -d`
3. Check: `docker compose ps` (should show `db` as running).
4. Stop: `docker compose down` — wipe data: `docker compose down -v`

If port 5432 is already in use, change the host port in `docker-compose.yml` (e.g. `"5433:5432"`) and use `localhost:5433` in `DATABASE_URL`.

**Apply schema (Alembic):**

```powershell
pip install -r requirements.txt
alembic upgrade head
```

Check tables: `docker compose exec db psql -U bowlbot -d bowlbot_dev -c "\dt"`

New migrations: `alembic revision -m "description"` (or autogenerate with `--autogenerate` after editing `db/models.py`).

**Sync sheet → database (Phase 2):**

```powershell
python sync_db.py --dry-run    # count rows, no writes
python sync_db.py              # load all seasons into Postgres
python sync_db.py --season 13  # one season only
```

Requires `DATABASE_URL` and `EXCEL_FILE_PATH` in `.env`.

| Layer | Role |
|-------|------|
| `sync_db.py` | Excel → Postgres (run after workbook changes) |
| `db/facts_loader.py` | Load rows for the web app |
| `stats/compute.py` | Standings, players, weeks, matchups, leaders |
| `league_data.py` | `DbLeagueData` for the Flask app |

See [docs/database/phase-3-app-integration.md](docs/database/phase-3-app-integration.md).

See [docs/database/phase-2-ingest-from-sheets.md](docs/database/phase-2-ingest-from-sheets.md).

See [docs/database/phase-1-schema-and-migrations.md](docs/database/phase-1-schema-and-migrations.md).

## Production (e.g. Railway)

- **Optional PostgreSQL roadmap:** [docs/database/README.md](docs/database/README.md) (phased plan: schema → ingest → app reads → ops).
- Start with gunicorn: `gunicorn main:app --bind 0.0.0.0:$PORT`
- Set the same env vars as above.
- Optional: `RELOAD_SECRET` — if set, reload data with `POST /reload?key=<secret>`.

## Project layout

| Path | Role |
|------|------|
| `app/` | Flask app + routes |
| `league_service.py` | Stats + HTML (uses `league_data`, `image_generator`) |
| `league_data.py` | Postgres read API (`DbLeagueData`) |
| `stats/` | Fact filters + compute (DB facts and sync share the same shape) |
| `sheets_handler.py` | Excel ingest for `sync_db.py` only (`iter_player_week_rows`) |
| `image_generator.py` | HTML templates (card look) + `inject_web_chrome` |
| `templates/` | Home + error + player pick |

## Data flow

**Excel file** → `python sync_db.py` → **Postgres** → `python main.py` → website

## One-off tools

- `migrate.py` — v4 → v5 migration
- `scripts/seed_matchup_overrides.py` — load v4 matchup W/L into `matchup_overrides`
