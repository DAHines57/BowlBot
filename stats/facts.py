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


def fact_in_roster_window(fact: dict) -> bool:
    """True if this week is within roster membership bounds on the fact (if present)."""
    week = safe_int(fact.get("week"), 0)
    if week < 1:
        return False
    started = fact.get("roster_started_week")
    if started is not None and week < int(started):
        return False
    ended = fact.get("roster_ended_week")
    if ended is not None and week > int(ended):
        return False
    return True


GAME_SLOT_KEYS = ("game1", "game2", "game3", "game4", "game5")


def _game_absent(fact: dict, slot: int) -> bool:
    """True when slot uses book average (missed that game). Ignored if whole week absent."""
    if fact.get("absent"):
        return False
    return bool(fact.get(f"game{slot}_absent"))


def games_list_for_team(fact: dict) -> List[float]:
    """Positive pin totals from all game slots (team pins, matchups, league totals)."""
    out: List[float] = []
    for key in GAME_SLOT_KEYS:
        g = fact.get(key)
        if g is None or g == "":
            continue
        score = safe_float(g)
        if score > 0:
            out.append(score)
    return out


def games_list_for_player_stats(fact: dict) -> List[float]:
    """Pin totals that count toward player season average, PAR, high/low (not book-avg slots)."""
    if fact.get("absent"):
        return []
    out: List[float] = []
    for i, key in enumerate(GAME_SLOT_KEYS, start=1):
        if _game_absent(fact, i):
            continue
        g = fact.get(key)
        if g is None or g == "":
            continue
        score = safe_float(g)
        if score > 0:
            out.append(score)
    return out


def games_list(fact: dict) -> List[float]:
    """Alias for team pin totals (backward compatible)."""
    return games_list_for_team(fact)


def fact_has_play_activity(fact: dict) -> bool:
    """True if the row represents a scored or absent week (not a blank template)."""
    if fact.get("absent"):
        return True
    return len(games_list_for_team(fact)) > 0


def fact_counts_for_stats(fact: dict) -> bool:
    """Whether a fact row should affect roster season stats (not sub appearances)."""
    if fact.get("substitute"):
        return False
    if not fact_in_roster_window(fact):
        return False
    return fact_has_play_activity(fact)


def fact_counts_for_player_profile(fact: dict) -> bool:
    """Whether a row counts on a player's profile (includes sub games)."""
    if fact.get("absent"):
        return False
    if fact.get("substitute"):
        return len(games_list_for_team(fact)) > 0
    if not fact_in_roster_window(fact):
        return False
    return fact_has_play_activity(fact)


def player_profile_games(fact: dict) -> List[float]:
    """Game scores that count toward a player's profile average/history."""
    if fact.get("substitute"):
        return games_list_for_team(fact)
    return games_list_for_player_stats(fact)


def subs_by_replaced_by_team_week(
    rows: Iterable[dict],
) -> Dict[tuple[str, int], Dict[str, dict]]:
    """(team, week) -> {replaced_roster_name: sub fact row}."""
    out: Dict[tuple[str, int], Dict[str, dict]] = {}
    for f in rows:
        if not f.get("substitute"):
            continue
        team = str(f.get("team") or "").strip()
        week = safe_int(f.get("week"), 0)
        who = str(f.get("substituted_for") or "").strip()
        if team and week > 0 and who:
            out.setdefault((team, week), {})[who] = f
    return out


def counting_sub_replacements_by_team_week(
    rows: Iterable[dict],
) -> Dict[tuple[str, int], set[str]]:
    """(team, week) -> roster names replaced by a counting sub that week."""
    out: Dict[tuple[str, int], set[str]] = {}
    for f in rows:
        if not f.get("substitute") or not f.get("substitute_scores_count"):
            continue
        team = str(f.get("team") or "").strip()
        week = safe_int(f.get("week"), 0)
        who = str(f.get("substituted_for") or "").strip()
        if team and week > 0 and who:
            out.setdefault((team, week), set()).add(who)
    return out


def counting_sub_replacements_for_team_week(
    rows: Iterable[dict],
    *,
    team: str,
    week: int,
) -> set[str]:
    """Roster names on one team-week replaced by a counting sub."""
    return counting_sub_replacements_by_team_week(rows).get((team, week), set())


def fact_counts_for_team_pins(
    fact: dict,
    *,
    replaced_by_counting_sub: Optional[set[str]] = None,
) -> bool:
    """Whether a row's pin totals count toward team totals and matchups."""
    if fact.get("substitute"):
        return bool(fact.get("substitute_scores_count"))
    player = str(fact.get("player_display_name") or "").strip()
    repl = replaced_by_counting_sub or set()
    if player and player in repl:
        return False
    return True


def add_slot_pins_to_index(
    index: Dict[int, float],
    slots: List[Optional[int]],
    *,
    max_slot: int = 5,
) -> None:
    """Add pin totals by game number (1-based) into index[game_num]."""
    for i, g in enumerate(slots, start=1):
        if i > max_slot or g is None:
            continue
        index[i] = index.get(i, 0) + int(g)


def games_slots(fact: dict) -> List[Optional[int]]:
    """game1–game5 pin slots; None when blank (preserves game index for matchup tables)."""
    out: List[Optional[int]] = []
    for key in GAME_SLOT_KEYS:
        g = fact.get(key)
        if g is None or g == "":
            out.append(None)
            continue
        score = int(safe_float(g))
        out.append(score if score > 0 else None)
    return out


def name_matches_team(a: str, b: str) -> bool:
    """Loose match: roster team vs opponent or override team name."""
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
