"""PostgreSQL availability checks for the web app."""
from __future__ import annotations

from sqlalchemy import func, select

from db.models import PlayerWeek
from db.session import get_session


def db_has_data() -> bool:
    try:
        session = get_session()
        try:
            count = session.scalar(select(func.count()).select_from(PlayerWeek))
            return bool(count and count > 0)
        finally:
            session.close()
    except Exception:
        return False
