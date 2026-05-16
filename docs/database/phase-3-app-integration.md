# Phase 3 — App integration (read path)

**Goal:** Let `LeagueService` (or a thin repository layer) answer queries from PostgreSQL when enabled, with **fallback** to the current sheet handler if the flag is off or DB is empty.

## Outcomes

- `USE_DB_READS=1` (or similar) switches read implementations.
- Parity milestone: key routes return equivalent data to sheet-backed paths for at least:
  - Team standings
  - Player list / averages
  - Single player detail
  - Leaders / top games (may still compute from facts in SQL or in Python after one wide fetch)

## Suggested layering

```
app/routes.py
  → league_service.LeagueService
      → StatsRepository (protocol / ABC)
          → DbStatsRepository
          → SheetStatsRepository (wraps today’s SheetHandler calls)
```

Avoid copying SQL into every route; centralize “one season facts” and “all seasons facts” loaders.

## Query strategy

- **v1:** SQL returns raw `player_weeks` + dimension tables; reuse existing Python aggregation in `league_service` to minimize logic drift.
- **v2 (optional):** Move heavy aggregates (standings, leaders) into SQL / views for performance.

## Deliverables

- [ ] `DbStatsRepository` implementing the same operations `LeagueService` needs (inventory methods by grepping `self.h.` in `league_service.py`).
- [ ] Integration tests with a small fixture DB (Docker Postgres in CI or sqlite in-memory only if dialect-compatible — prefer real Postgres).
- [ ] Feature flag documented in `docs/database/README.md` and root README.

## Rollout

1. Deploy with `USE_DB_READS=0`, run sync on schedule.
2. Compare HTML or JSON snapshots in staging.
3. Flip `USE_DB_READS=1` for staging, then production.

## Risks

- Subtle differences in rounding, absent/substitute rules, or playoff filtering vs sheet code — the validation step in Phase 2 is critical.
