# Bowl League

Web app for bowling league stats backed by **Google Sheets** (or a local Excel file).  
Pages use the same purple / amber styling as the old recap images.

## Run locally

1. Python 3.11+ recommended.
2. `python -m venv venv` then activate (`venv\Scripts\activate` on Windows).
3. `pip install -r requirements.txt`
4. Copy `.env` — at minimum for Google Sheets:

   ```
   SHEET_HANDLER_TYPE=gsheets
   GOOGLE_SHEET_ID=...
   GOOGLE_CREDENTIALS={"type":"service_account",...}
   DEBUG=true
   ```

5. `python main.py` → open **http://127.0.0.1:3000** (or from your phone on Wi‑Fi: `http://<your-pc-lan-ip>:3000`).

## Production (e.g. Railway)

- **Optional PostgreSQL roadmap:** [docs/database/README.md](docs/database/README.md) (phased plan: schema → ingest → app reads → ops).
- Start with gunicorn: `gunicorn main:app --bind 0.0.0.0:$PORT`
- Set the same env vars as above.
- Optional: `RELOAD_SECRET` — if set, reload data with `POST /reload?key=<secret>`.

## Project layout

| Path | Role |
|------|------|
| `app/` | Flask app + routes |
| `league_service.py` | Stats + HTML (uses `sheets_handler`, `image_generator`) |
| `sheets_handler.py` | Excel / Google Sheets data |
| `image_generator.py` | HTML templates (card look) + `inject_web_chrome` |
| `templates/` | Home + error + player pick |

## Optional local Excel

Set `SHEET_HANDLER_TYPE=excel` and `EXCEL_FILE_PATH=...`.

## One-off tools

- `migrate.py` — v4 → v5 migration
- `extract_colors.py` — refresh `team_colors.json` from a workbook
