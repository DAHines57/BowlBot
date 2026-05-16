"""Team display colors from PostgreSQL teams.color_hex."""
from __future__ import annotations

import logging
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Season, Team
from db.session import get_session
from stats.facts import canonical_team_name, name_matches_team

logger = logging.getLogger(__name__)

_CACHE: Dict[str, str] = {}


def load_team_color_map(session: Optional[Session] = None) -> Dict[str, str]:
    """Build team name -> #hex; newer seasons override older for the same name."""
    own = session is None
    if own:
        session = get_session()
    try:
        stmt = (
            select(Team.name, Team.color_hex, Season.number)
            .join(Season, Team.season_id == Season.id)
            .where(Team.color_hex.isnot(None))
            .order_by(Season.number.desc())
        )
        rows = session.execute(stmt).all()
        out: Dict[str, str] = {}
        for name, color_hex, _num in rows:
            if not color_hex:
                continue
            hex_v = str(color_hex).strip()
            if not hex_v.startswith("#"):
                hex_v = f"#{hex_v}"
            canon = canonical_team_name(name)
            for key in (canon, name.strip()):
                if key and key not in out:
                    out[key] = hex_v
        return out
    finally:
        if own and session is not None:
            session.close()


def refresh_team_colors_cache() -> Dict[str, str]:
    """Reload cache from DB and push to image_generator."""
    global _CACHE
    _CACHE = load_team_color_map()
    from image_generator import register_team_colors

    register_team_colors(_CACHE)
    logger.info("Team colors loaded: %s from DB", len(_CACHE))
    return _CACHE


def lookup_team_color(team_name: str) -> Optional[str]:
    """Resolve color for display name (uses in-memory cache)."""
    if not team_name:
        return None
    raw = team_name.strip()
    canon = canonical_team_name(raw)
    if canon in _CACHE:
        return _CACHE[canon]
    if raw in _CACHE:
        return _CACHE[raw]
    for key, hex_c in _CACHE.items():
        if name_matches_team(raw, key):
            return hex_c
    return None


def resolve_color_hex(
    team_name: str, color_map: Dict[str, str]
) -> Optional[str]:
    """Pick hex from a per-season Excel color map."""
    if not team_name or not color_map:
        return None
    canon = canonical_team_name(team_name.strip())
    if canon in color_map:
        return color_map[canon]
    raw = team_name.strip()
    if raw in color_map:
        return color_map[raw]
    for key, hex_c in color_map.items():
        if name_matches_team(raw, key):
            return hex_c
    return None
