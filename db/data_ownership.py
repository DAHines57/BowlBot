"""Which seasons are Excel-importable vs DB-managed (Phase 6)."""
from __future__ import annotations

import os
from typing import Optional


def last_excel_imported_season() -> Optional[int]:
    """Highest season number fully owned by Excel import; None if unset (legacy: all sync)."""
    raw = os.environ.get("LAST_EXCEL_IMPORTED_SEASON", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def is_season_db_managed(season_number: int) -> bool:
    """True when this season must not be overwritten from Excel without --force."""
    cutoff = last_excel_imported_season()
    if cutoff is None:
        return False
    return int(season_number) > int(cutoff)


def is_season_excel_importable(season_number: int, *, force: bool = False) -> bool:
    """True when sync_db may replace this season from the workbook."""
    if force:
        return True
    return not is_season_db_managed(season_number)
