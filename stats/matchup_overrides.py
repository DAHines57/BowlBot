"""Lookup helpers for matchup_overrides rows."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from stats.facts import name_matches_team


def group_overrides_by_season(
    overrides: Optional[List[dict]],
) -> Dict[int, List[dict]]:
    if not overrides:
        return {}
    out: Dict[int, List[dict]] = {}
    for row in overrides:
        sn = row.get("season_number")
        if sn is None:
            continue
        out.setdefault(int(sn), []).append(row)
    return out


def find_matchup_override(
    overrides: Optional[List[dict]],
    *,
    season_num: int,
    week: int,
    team: str,
) -> Optional[dict]:
    if not overrides or not team:
        return None
    for row in overrides:
        if int(row.get("season_number", 0)) != season_num:
            continue
        if int(row.get("week", 0)) != week:
            continue
        if name_matches_team(team, str(row.get("team") or "")):
            return row
    return None


def result_from_wlt(wins: int, losses: int, ties: int = 0) -> str:
    if wins > losses:
        return "W"
    if losses > wins:
        return "L"
    return "T"


def sides_from_overrides(
    home_name: str,
    away_name: str,
    home_row: Optional[dict],
    away_row: Optional[dict],
) -> Tuple[int, int, int, int, int, int, str, str]:
    """Return h_wins, h_losses, h_ties, a_wins, a_losses, a_ties, h_result, a_result."""
    if home_row:
        h_w = int(home_row["wins"])
        h_l = int(home_row["losses"])
        h_t = int(home_row.get("ties") or 0)
    else:
        h_w = h_l = h_t = 0
    if away_row:
        a_w = int(away_row["wins"])
        a_l = int(away_row["losses"])
        a_t = int(away_row.get("ties") or 0)
    else:
        a_w = a_l = a_t = 0
    if home_row and not away_row:
        a_w, a_l, a_t = h_l, h_w, h_t
    elif away_row and not home_row:
        h_w, h_l, h_t = a_l, a_w, a_t
    return (
        h_w,
        h_l,
        h_t,
        a_w,
        a_l,
        a_t,
        result_from_wlt(h_w, h_l, h_t),
        result_from_wlt(a_w, a_l, a_t),
    )
