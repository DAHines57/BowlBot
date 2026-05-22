# Phase 10 — Security and backups

**Status:** Planned (not implemented).

## Goal

Harden admin access for a public deployment and define a repeatable backup/restore story so live-season Postgres data is not lost.

## Admin security (current behavior)

| Piece | Env var | Behavior today |
|-------|---------|----------------|
| Admin gate | `ADMIN_PIN` | Optional. If unset, `/admin/*` is open. If set, unlock via form, session `admin_pin_ok`, or `?pin=` / `?key=` / `X-Admin-Pin`. |
| Session signing | `FLASK_SECRET_KEY` | Signs the session cookie; default dev key must not be used in production. Forged cookies can bypass PIN if secret is known. |
| Cache reload | `RELOAD_SECRET` | If set, `POST /refresh?key=…` required; if unset, reload is open. |

See `app/admin_auth.py`, `app/admin_routes.py`, `app/__init__.py`.

### Gaps to address

- [ ] Fail closed in production: require `ADMIN_PIN` when `DEBUG` is false (or refuse admin routes).
- [ ] Document: do not use `?pin=` in URLs (logs, history, Referer); use `POST /admin/unlock` only.
- [ ] Session cookie flags: `SESSION_COOKIE_SECURE`, `HTTPONLY`, `SAMESITE` (HTTPS).
- [ ] CSRF tokens on admin POST forms (save week, delete week/season, unlock).
- [ ] Admin logout route (clear `admin_pin_ok`).
- [ ] Rate limit `/admin/unlock` (or edge proxy).
- [ ] Optional: re-prompt PIN for destructive actions (delete season/week).
- [ ] Remove or gate admin hints on public `home.html` in production.
- [ ] Optional: restrict `/admin` at edge (IP allowlist, Cloudflare Access, etc.).

### Production checklist

- [ ] `ADMIN_PIN` — long random value (password manager), not a short PIN.
- [ ] `FLASK_SECRET_KEY` — separate long random secret; never commit.
- [ ] `RELOAD_SECRET` — set if app is on the public internet.
- [ ] HTTPS only (platform default on Railway).

## Backups (current behavior)

- **Source of truth:** PostgreSQL (`DATABASE_URL`).
- **Local dev:** Docker volume `bowlbot_pgdata`; `docker compose down -v` wipes data.
- **Frozen seasons:** Excel + `sync_db.py` can re-import seasons ≤ `LAST_EXCEL_IMPORTED_SEASON`.
- **Live season:** DB-only after cutoff; Excel sync does not replace without `--force`.

See [phase-4-production-and-ops.md](phase-4-production-and-ops.md), [phase-6-data-ownership.md](phase-6-data-ownership.md).

### Backup plan (operator)

| Layer | Action |
|-------|--------|
| Hosted Postgres (e.g. Railway) | Enable provider automatic backups; know restore procedure. |
| Logical dumps | Scheduled `pg_dump -Fc` to off-site storage (weekly + retention). |
| Excel workbook | Dated copies when closing a season (partial DR for frozen seasons only). |
| Before risky ops | Manual dump before migrations, `delete_season`, or `sync_db.py --force`. |

### Example commands

```powershell
# Production / local (DATABASE_URL set)
$ts = Get-Date -Format "yyyy-MM-dd_HHmm"
pg_dump $env:DATABASE_URL -Fc -f "backups/bowlbot_$ts.dump"

# Local Docker
docker compose exec -T db pg_dump -U bowlbot -d bowlbot_dev -Fc > "backups/local_$ts.dump"

# Remote (e.g. Railway PG 18) when local pg_dump version does not match:
# .\scripts\backup_db.ps1   # uses postgres:18-alpine via Docker
```

### Restore drill (do once)

1. Empty DB → `alembic upgrade head`.
2. `pg_restore -d $DATABASE_URL backups/your.dump` (or provider restore).
3. Restart app or `POST /refresh?key=…`.
4. Spot-check a known week on site and admin.

## Code / docs touchpoints (when implementing)

| Area | Notes |
|------|--------|
| `app/__init__.py` | Session config, prod guard for missing `ADMIN_PIN` |
| `app/admin_auth.py` | Logout, optional stricter checks |
| `templates/admin_*.html` | CSRF hidden fields |
| [phase-4-production-and-ops.md](phase-4-production-and-ops.md) | Cross-link; expand backup section |
| `SETUP.md` / `README.md` | Env var table for `FLASK_SECRET_KEY` purpose |

## References

- `FLASK_SECRET_KEY` signs session cookies (e.g. `admin_pin_ok`); does not encrypt DB or replace `ADMIN_PIN`.
- `ADMIN_PIN` proves unlock; `FLASK_SECRET_KEY` prevents forging the “already unlocked” cookie.
