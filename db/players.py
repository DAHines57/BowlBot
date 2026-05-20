"""Player row helpers (shared by sync, roster, and score writes)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Player


def get_or_create_player(session: Session, cache: dict[str, int], display_name: str) -> int:
    if display_name in cache:
        return cache[display_name]
    player = session.scalar(select(Player).where(Player.display_name == display_name))
    if player is None:
        player = Player(display_name=display_name)
        session.add(player)
        session.flush()
    cache[display_name] = player.id
    return player.id
