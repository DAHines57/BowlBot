# Phase 4 — Production and operations

**Goal:** Run Postgres reliably beside the Flask app on Railway (or another host), secure connections, and define how operators back up and recover.

## Railway checklist

- [ ] Create **PostgreSQL** plugin; copy `DATABASE_URL` into the web service.
- [ ] Use **SSL** (Railway URLs typically require TLS; ensure SQLAlchemy / driver uses `sslmode=require` if needed).
- [ ] **Networking:** DB not publicly exposed if possible; service-to-service private URL on Railway.
- [ ] **Health:** Extend `/health` with a DB `SELECT 1` (today it reports `read_source: database` only).

## Migrations in deploy

- Run `alembic upgrade head` (or equivalent) as a **release phase** before or after new code starts — pick one strategy and document it.
- Never assume empty DB on first boot without migration (crash-loop risk).

## Backups and restore

- Enable Railway **automatic backups** for Postgres if available.
- Document how to download a dump and restore to local Postgres for debugging.
- Define retention (e.g. keep weekly dumps for N weeks).

Details and checklist: [phase-10-security-and-backups.md](phase-10-security-and-backups.md).

## Data entry (Phases 6–9)

Live scores are **DB-first**; Excel is for historical import/repair only. See [phase-6](phase-6-data-ownership.md), [phase-7](phase-7-player-week-writes.md), [phase-8](phase-8-score-entry.md).

## Observability

- Log sync duration, rows affected, last successful sync timestamp (store in a small `meta` table or Redis).
- Alert if sync job fails N times in a row (Railway metrics, UptimeRobot on `/health`, etc.).

## Security

- `DATABASE_URL` in secrets only; never commit.
- Read-only DB user for the web app if migrations run from a different role (advanced).
