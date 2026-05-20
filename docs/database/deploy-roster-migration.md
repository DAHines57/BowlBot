# Deploying `team_roster_members` (live database)

This migration adds `team_roster_members` and does **not** remove or change `player_weeks`. Weekly scores and substitutes work the same; season rosters are stored explicitly.

## Local (dev)

```powershell
# From project root, with Docker Postgres up and .env set
alembic upgrade head
python scripts/backfill_team_roster.py
```

Optional: re-sync one season from Excel (also backfills roster for that season):

```powershell
python sync_db.py --season 13
```

Restart or `POST /refresh?key=...` if the app is already running.

## Production (e.g. Railway)

Do this **once per environment** when deploying code that includes migration `008_team_roster_members`.

### 1. Backup (recommended)

Use Railway Postgres backups or a manual dump before schema changes. See [phase-10-security-and-backups.md](phase-10-security-and-backups.md).

### 2. Deploy code

Push or deploy the branch that contains the new migration and app code.

### 3. Run migrations against production `DATABASE_URL`

Point your shell at the **production** URL (Railway → Postgres → Connect → copy `DATABASE_URL`), then:

**PowerShell (one-off from your machine):**

```powershell
$env:DATABASE_URL = "postgresql://..."   # production URL
alembic upgrade head
python scripts/backfill_team_roster.py
```

**Or Railway one-off command** (if your service has the repo and Python):

```bash
alembic upgrade head && python scripts/backfill_team_roster.py
```

Use the same `DATABASE_URL` the web service uses (often the private/internal URL on Railway).

### 4. Deploy / restart the web service

No new env vars are required. After deploy, hit `/health` and open season admin to confirm rosters look correct.

### 5. Verify

```sql
SELECT COUNT(*) FROM team_roster_members;
SELECT s.number, COUNT(m.id)
FROM seasons s
LEFT JOIN team_roster_members m ON m.season_id = s.id
GROUP BY s.number
ORDER BY s.number;
```

Active roster for a season should match what you see under **Admin → Season setup**.

## Ongoing behavior

| Action | Roster table |
|--------|----------------|
| Admin **Save roster** | Upserts `team_roster_members`; still writes week-1 template `player_weeks` |
| `sync_db.py` (Excel import) | Replaces season rows, then `backfill_season_roster` for that season |
| `scripts/backfill_team_roster.py` | Repair / initial fill from earliest-week `player_weeks` |
| Weekly score entry | Unchanged (`player_weeks` only) |

## Rollback

```powershell
alembic downgrade 007_drop_game5_winner
```

This drops `team_roster_members`. `player_weeks` data is unchanged.

## Troubleshooting

- **Empty rosters in admin after migrate:** Run `python scripts/backfill_team_roster.py`.
- **Roster looks right but week 1 templates missing:** Save roster once in admin or run backfill after sync.
- **Captain column:** Stored as `is_captain`; admin UI can add captain picks later. API accepts `captain` on each team in `save_season_roster` payload when wired in the form.
