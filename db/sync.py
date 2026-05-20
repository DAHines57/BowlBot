"""Sync spreadsheet rows into PostgreSQL (Phase 2)."""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.data_ownership import is_season_excel_importable
from db.excluded_seasons import is_season_excluded
from db.excel_colors import build_season_color_maps
from db.models import PlayerWeek, Season, Team
from db.players import get_or_create_player
from db.roster_members import backfill_season_roster
from db.session import get_session
from db.sheet_factory import get_handler_from_env
from db.team_colors import resolve_color_hex
from sheets_handler import ExcelHandler
from stats.facts import canonical_team_name, resolve_opponent_on_roster

logger = logging.getLogger(__name__)


def _get_or_create_season(session: Session, sheet_key: str, season_number: int) -> Season:
    season = session.scalar(select(Season).where(Season.number == season_number))
    if season is None:
        season = Season(
            id=season_number,
            number=season_number,
            label=sheet_key,
            sheet_key=sheet_key,
            sort_order=season_number,
        )
        session.add(season)
    else:
        season.label = sheet_key
        season.sheet_key = sheet_key
        season.sort_order = season_number
    session.flush()
    return season


def _replace_season_rows(
    session: Session,
    season: Season,
    rows: list[dict],
    player_cache: dict[str, int],
    *,
    season_color_map: Optional[dict[str, str]] = None,
) -> int:
    session.execute(delete(Team).where(Team.season_id == season.id))

    season_num = season.number
    for row in rows:
        if row.get("team"):
            row["team"] = canonical_team_name(
                str(row["team"]).strip(), season_num=season_num
            )

    roster = sorted({str(r["team"]).strip() for r in rows if r.get("team")})
    for row in rows:
        opp = row.get("opponent")
        if opp:
            hit = resolve_opponent_on_roster(
                str(opp).strip(), roster, season_num=season_num
            )
            if hit:
                row["opponent"] = hit

    team_ids: dict[str, int] = {}
    color_map = season_color_map or {}
    for row in rows:
        if row["team"] not in team_ids:
            hex_c = resolve_color_hex(row["team"], color_map)
            team = Team(season_id=season.id, name=row["team"], color_hex=hex_c)
            session.add(team)
            session.flush()
            team_ids[row["team"]] = team.id

    facts: list[PlayerWeek] = []
    for row in rows:
        player_id = get_or_create_player(session, player_cache, row["player_display_name"])
        facts.append(
            PlayerWeek(
                season_id=season.id,
                week=row["week"],
                team_id=team_ids[row["team"]],
                player_id=player_id,
                player_display_name=row["player_display_name"],
                game1=row["game1"],
                game2=row["game2"],
                game3=row["game3"],
                game4=row["game4"],
                game5=row["game5"],
                week_average=row["week_average"],
                absent=row["absent"],
                substitute=row["substitute"],
                playoffs=row["playoffs"],
                opponent=row["opponent"],
                source_row_fingerprint=row["source_row_fingerprint"],
            )
        )
    session.add_all(facts)
    session.flush()
    backfill_season_roster(session, season.id, clear_existing=True)
    return len(facts)


def sync_database(
    *,
    dry_run: bool = False,
    season_filter: Optional[str] = None,
    force: bool = False,
) -> dict:
    handler = get_handler_from_env()
    if not isinstance(handler, ExcelHandler):
        raise TypeError("Sync requires ExcelHandler (iter_player_week_rows)")
    started = time.perf_counter()

    by_season: dict[str, list[dict]] = defaultdict(list)
    for row in handler.iter_player_week_rows(season_filter=season_filter):
        by_season[row["sheet_key"]].append(row)

    total_rows = sum(len(v) for v in by_season.values())
    logger.info(
        "Read %s rows across %s season(s)%s",
        total_rows,
        len(by_season),
        f" (filter={season_filter!r})" if season_filter else "",
    )

    skipped_db_managed: list[str] = []
    if dry_run:
        for sheet_key in sorted(by_season, key=lambda k: by_season[k][0]["season_number"]):
            season_num = by_season[sheet_key][0]["season_number"]
            if not is_season_excel_importable(season_num, force=force):
                skipped_db_managed.append(sheet_key)
                logger.info("  %s: skipped (DB-managed season)", sheet_key)
            else:
                logger.info("  %s: %s rows", sheet_key, len(by_season[sheet_key]))
        return {
            "dry_run": True,
            "seasons": len(by_season),
            "rows": total_rows,
            "skipped_seasons": skipped_db_managed,
            "seconds": time.perf_counter() - started,
        }

    season_color_maps: dict[str, dict[str, str]] = {}
    if isinstance(handler, ExcelHandler):
        sheet_keys = list(by_season.keys())
        season_color_maps = build_season_color_maps(handler.file_path, sheet_keys)
        logger.info("Read team colors for %s season sheet(s)", len(season_color_maps))

    session = get_session()
    player_cache: dict[str, int] = {}
    written = 0
    try:
        for sheet_key in sorted(by_season, key=lambda k: by_season[k][0]["season_number"]):
            rows = by_season[sheet_key]
            season_num = rows[0]["season_number"]
            if is_season_excluded(season_num):
                logger.info("Skipping excluded season %s (%s)", sheet_key, season_num)
                continue
            if not is_season_excel_importable(season_num, force=force):
                skipped_db_managed.append(sheet_key)
                logger.info(
                    "Skipping DB-managed season %s (%s); use sync --force to overwrite from Excel",
                    sheet_key,
                    season_num,
                )
                continue
            season = _get_or_create_season(
                session, sheet_key, season_num
            )
            count = _replace_season_rows(
                session,
                season,
                rows,
                player_cache,
                season_color_map=season_color_maps.get(sheet_key),
            )
            written += count
            logger.info("Wrote %s: %s player_week rows", sheet_key, count)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    elapsed = time.perf_counter() - started
    logger.info("Sync complete: %s rows in %.1fs", written, elapsed)
    if skipped_db_managed:
        logger.info(
            "Skipped %s DB-managed season(s): %s",
            len(skipped_db_managed),
            ", ".join(skipped_db_managed),
        )
    return {
        "dry_run": False,
        "seasons": len(by_season),
        "rows": written,
        "skipped_seasons": skipped_db_managed,
        "seconds": elapsed,
    }
