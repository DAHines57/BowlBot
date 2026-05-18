# Phase 8 — Score entry (HTTP)

**Status:** Done.

## Goal

Protected **HTTP API** (and minimal UI) so operators enter a week’s scores without Excel.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/admin` | PIN gate → hub |
| `GET` | `/admin/hub` | Links + delete week |
| `GET` | `/admin/enter?season=…&week=…&team=…` | HTML week grid (team filter) |
| `GET` | `/admin/season?season=…` | Create/edit season roster |
| `GET` | `/admin/week?season=…&week=…` | JSON week payload |
| `POST` | `/admin/week` | Save week (JSON or form `payload`) |
| `POST` | `/admin/week/delete` | Delete all rows for a week |
| `POST` | `/admin/season` | Create season / save roster / delete season |

Auth: `ADMIN_PIN` (alphanumeric) at `/admin`. Session cookie after unlock; optional `?pin=` or `?key=` per request. Set `FLASK_SECRET_KEY` in production.

## JSON payload (`POST`)

```json
{
  "season": "Season 14",
  "week": 3,
  "rows": [
    {
      "team": "Team A",
      "player_display_name": "Alice",
      "opponent": "Team B",
      "game1": 200,
      "game2": 210,
      "game3": null,
      "game4": null,
      "game5": null,
      "absent": false,
      "substitute": false,
      "playoffs": false
    }
  ]
}
```

After save, the app calls `refresh_data()` so stats pages see new facts.

## Roster template

`GET` for a week with no rows yet:

1. Copy roster from the latest prior week in the same season (blank scores), or
2. If the season is new, copy from the same week in season **N − 1**.

## Code

| Module | Role |
|--------|------|
| `app/admin_auth.py` | `ADMIN_PIN` check |
| `db/season_admin.py` | Create season, roster, deletes |
| `league_admin.py` | Load/save week entry |
| `app/admin_routes.py` | Routes |
| `templates/admin_enter.html` | Entry UI |

## Deliverables

- [x] `ADMIN_PIN` env + session gate
- [x] Team dropdown filter on enter page
- [x] Season setup (create, roster, delete season/week)
- [x] JSON week payload + validation
- [x] `POST /admin/week` → `save_week_rows` + cache refresh
- [x] `/admin/enter` form
- [x] Tests (`tests/test_admin_week.py`)

## Related

- [Phase 7 — Player week writes](phase-7-player-week-writes.md)
