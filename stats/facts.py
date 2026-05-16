"""Normalize and filter player-week fact rows."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from utils import safe_float, safe_int


def normalize(text: str) -> str:
    """Lowercase and flatten curly quotes for comparison."""
    return (
        text.lower()
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def games_list(fact: dict) -> List[float]:
    """Positive pin totals from game1–game5 on a fact row."""
    out: List[float] = []
    for key in ("game1", "game2", "game3", "game4", "game5"):
        g = fact.get(key)
        if g is None or g == "":
            continue
        score = safe_float(g)
        if score > 0:
            out.append(score)
    return out


def games_slots(fact: dict) -> List[Optional[int]]:
    """game1–game5 pin slots; None when blank (preserves game index for matchup tables)."""
    out: List[Optional[int]] = []
    for key in ("game1", "game2", "game3", "game4", "game5"):
        g = fact.get(key)
        if g is None or g == "":
            out.append(None)
            continue
        score = int(safe_float(g))
        out.append(score if score > 0 else None)
    return out


def name_matches_team(a: str, b: str) -> bool:
    """Loose match: roster team vs opponent / Game 5 winner string."""
    if not a or not b:
        return False
    na = normalize(str(a).strip())
    nb = normalize(str(b).strip())
    return na == nb or na in nb or nb in na


# Season 11 only: roster vs opponent column used different names for one franchise.
# Dict keys are the canonical roster/display name for that season.
TEAM_ALIASES_SEASON = 11
TEAM_ALIASES: Dict[str, List[str]] = {
    "Strike It Deep": ["Bowls Deep"],
}


def team_aliases_for_season(season_num: Optional[int]) -> Dict[str, List[str]]:
    if season_num == TEAM_ALIASES_SEASON:
        return TEAM_ALIASES
    return {}


def _alias_names(name: str, *, season_num: Optional[int] = None) -> List[str]:
    out = [name]
    for canonical, alts in team_aliases_for_season(season_num).items():
        if name_matches_team(name, canonical):
            out.extend(alts)
        elif any(name_matches_team(name, a) for a in alts):
            out.append(canonical)
            out.extend(a for a in alts if not name_matches_team(name, a))
    return list(dict.fromkeys(out))


def canonical_team_name(name: str, *, season_num: Optional[int] = None) -> str:
    """Preferred display/roster name when a season has known alias spellings."""
    if not name:
        return name
    n = str(name).strip()
    for canonical, alts in team_aliases_for_season(season_num).items():
        if name_matches_team(n, canonical):
            return canonical
        for alt in alts:
            if name_matches_team(n, alt):
                return canonical
    return n


def resolve_opponent_on_roster(
    opponent_name: str,
    roster: Iterable[str],
    *,
    season_num: Optional[int] = None,
) -> Optional[str]:
    """Map opponent text from the sheet onto a team name present this week."""
    if not opponent_name:
        return None
    names = list(roster)
    for candidate in names:
        if name_matches_team(opponent_name, candidate):
            return canonical_team_name(candidate, season_num=season_num)
    for alias in _alias_names(opponent_name, season_num=season_num):
        for candidate in names:
            if name_matches_team(alias, candidate):
                return canonical_team_name(candidate, season_num=season_num)
    return None


def fifth_game_pins_decisive(td: Dict, opp: Dict) -> bool:
    """True if Game 5 has full-roster pin totals for both teams and they differ.

    Absent teammates often have no game5 in the DB; comparing team sums then
    skews the series (e.g. 3 bowlers vs 4). Require every active player to have
    game 5 pins before pins decide the matchup.
    """
    gp_h = td.get("game_pins") or []
    gp_a = opp.get("game_pins") or []
    if len(gp_h) < 5 or len(gp_a) < 5:
        return False
    h_active = int(td.get("active_player_count") or td.get("player_count") or 0)
    a_active = int(opp.get("active_player_count") or opp.get("player_count") or 0)
    h_g5 = int(td.get("game5_bowler_count") or 0)
    a_g5 = int(opp.get("game5_bowler_count") or 0)
    # Uneven active rosters (e.g. absent bowler) — do not award a fifth game on pins.
    if h_active and a_active and h_active != a_active:
        return False
    if h_active and h_g5 < h_active:
        return False
    if a_active and a_g5 < a_active:
        return False
    hp = int(gp_h[4])
    ap = int(gp_a[4])
    if hp <= 0 or ap <= 0:
        return False
    return hp != ap


def filter_facts(
    facts: Iterable[dict],
    *,
    season_num: Optional[int] = None,
    week: Optional[int] = None,
    through_week: Optional[int] = None,
    exclude_playoffs: bool = False,
    team: Optional[str] = None,
    player_substr: Optional[str] = None,
) -> List[dict]:
    """Return fact rows matching optional season/week/team/player filters."""
    result: List[dict] = []
    for f in facts:
        if season_num is not None and f.get("season_number") != season_num:
            continue
        w = safe_int(f.get("week"), 0)
        if week is not None and w != week:
            continue
        if through_week is not None:
            if w < 1 or w > through_week:
                continue
        if exclude_playoffs and f.get("playoffs"):
            continue
        if team is not None:
            t = str(f.get("team") or "")
            if not (
                normalize(team) in normalize(t)
                or normalize(t) in normalize(team)
            ):
                continue
        if player_substr is not None:
            p = str(f.get("player_display_name") or "")
            ns = normalize(player_substr)
            np = normalize(p)
            if ns not in np and np not in ns:
                continue
        result.append(f)
    return result
