"""PostgreSQL availability checks for the web app."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from db.models import PlayerWeek
from db.session import get_session


def db_status() -> dict[str, Any]:
    """Diagnostics for /health (no secrets)."""
    try:
        session = get_session()
        try:
            count = session.scalar(select(func.count()).select_from(PlayerWeek))
            count = int(count or 0)
            return {
                "connected": True,
                "player_weeks": count,
                "has_data": count > 0,
            }
        finally:
            session.close()
    except Exception as exc:
        return {
            "connected": False,
            "player_weeks": 0,
            "has_data": False,
            "error": type(exc).__name__,
        }


def db_has_data() -> bool:
    return db_status()["has_data"]
