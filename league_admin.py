"""Week score entry — load/save player_week rows (Phase 8)."""
from __future__ import annotations

from typing import Any, Callable, List, Optional, Tuple

from sqlalchemy import func, select

from db.data_ownership import is_season_db_managed
from db.models import Season, TeamRosterMember
from db.player_week_writes import save_week_rows, sync_week_team_opponents
from db.session import get_session
from league_data import LeagueDataSource
from stats import compute
from stats.facts import (
    fact_counts_for_stats,
    games_list_for_player_stats,
    games_list_for_team,
    games_slots,
    filter_facts,
)
from utils import safe_int

GAME_SCORE_MIN = 1
GAME_SCORE_MAX = 300
_GAME_SCORE_ERROR = (
    f"Score must be a whole number from {GAME_SCORE_MIN} to {GAME_SCORE_MAX}, or leave blank."
)


def _is_empty_game_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def parse_game_score(value: Any) -> Tuple[Optional[float], Optional[str]]:
    """Return (score, None) or (None, error message). Empty input is valid (no score)."""
    if _is_empty_game_value(value):
        return None, None
    if isinstance(value, bool):
        return None, _GAME_SCORE_ERROR
    try:
        if isinstance(value, int):
            n = value
        elif isinstance(value, float):
            if not value.is_integer():
                return None, _GAME_SCORE_ERROR
            n = int(value)
        elif isinstance(value, str):
            s = value.strip()
            if "." in s:
                f = float(s)
                if not f.is_integer():
                    return None, _GAME_SCORE_ERROR
                n = int(f)
            else:
                n = int(s)
        else:
            return None, _GAME_SCORE_ERROR
    except (ValueError, TypeError, OverflowError):
        return None, _GAME_SCORE_ERROR
    if n < GAME_SCORE_MIN or n > GAME_SCORE_MAX:
        return None, _GAME_SCORE_ERROR
    return float(n), None


def _bool_field(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def _row_needs_scores(row: dict) -> bool:
    if row.get("substitute") or row.get("absent"):
        return False
    return True


def _row_missing_game_count(row: dict) -> int:
    if not _row_needs_scores(row):
        return 0
    missing = 0
    for i in range(1, 5):
        if row.get(f"game{i}") is None:
            missing += 1
    return missing


def assess_week_completion(
    rows: List[dict],
    *,
    templated: bool,
    season_teams: Optional[List[str]] = None,
    require_full_roster: bool = True,
) -> dict:
    """Return status for a week: not_started, incomplete, or complete."""
    teams_expected = (
        [str(t).strip() for t in (season_teams or []) if str(t).strip()]
        if require_full_roster
        else []
    )
    teams_in_week = sorted({str(r.get("team") or "").strip() for r in rows if r.get("team")})
    team_opponents: dict[str, str] = {}
    for r in rows:
        t = str(r.get("team") or "").strip()
        opp = r.get("opponent")
        if t and opp and t not in team_opponents:
            team_opponents[t] = str(opp).strip()

    if not rows:
        return {
            "status": "not_started",
            "summary": "No roster for this week.",
            "missing_opponents": [],
            "teams_not_entered": teams_expected,
            "incomplete_players": [],
        }

    if templated:
        return {
            "status": "not_started",
            "summary": "Not saved yet — showing roster template only.",
            "missing_opponents": [],
            "teams_not_entered": [],
            "incomplete_players": [],
        }

    missing_opponents = [
        t for t in teams_in_week if not team_opponents.get(t)
    ]
    teams_not_entered = [t for t in teams_expected if t not in teams_in_week]
    incomplete_players: List[dict] = []
    for r in rows:
        missing = _row_missing_game_count(r)
        if missing:
            incomplete_players.append(
                {
                    "team": r.get("team"),
                    "player_display_name": r.get("player_display_name"),
                    "missing_games": missing,
                }
            )

    if missing_opponents or teams_not_entered or incomplete_players:
        parts: List[str] = []
        if teams_not_entered:
            parts.append(f"{len(teams_not_entered)} team(s) not entered")
        if missing_opponents:
            parts.append(f"{len(missing_opponents)} team(s) missing opponent")
        if incomplete_players:
            parts.append(f"{len(incomplete_players)} player(s) missing scores")
        return {
            "status": "incomplete",
            "summary": "Incomplete — " + ", ".join(parts) + ".",
            "missing_opponents": missing_opponents,
            "teams_not_entered": teams_not_entered,
            "incomplete_players": incomplete_players,
        }

    return {
        "status": "complete",
        "summary": "All teams and scores entered for this week.",
        "missing_opponents": [],
        "teams_not_entered": [],
        "incomplete_players": [],
    }


def list_season_week_completion(
    data: LeagueDataSource,
    season_label: str,
    *,
    season_teams: Optional[List[str]] = None,
    through_week: Optional[int] = None,
    require_full_roster: bool = True,
) -> List[dict]:
    """Per-week completion status for the enter-scores week picker."""
    season_num = compute.parse_season_number(season_label)
    if season_num is None:
        return []

    facts = _facts_for_data(data)
    season_rows = filter_facts(facts, season_num=season_num)
    latest = compute.get_latest_week(facts, season=season_label)
    existing = compute.list_weeks_for_season(facts, season=season_label)
    max_week = max([latest + 1, *(existing or []), through_week or 0, 1])
    max_week = min(max_week, 99)

    if require_full_roster:
        teams = season_teams
        if teams is None:
            teams = list_season_teams_from_db(season_num)
        if not teams:
            teams = sorted({str(f.get("team") or "").strip() for f in season_rows if f.get("team")})
    else:
        teams = []

    out: List[dict] = []
    for week in range(1, max_week + 1):
        entry_rows, templated = _full_week_entry_rows(facts, season_num, week)
        comp = assess_week_completion(
            entry_rows,
            templated=templated,
            season_teams=teams,
            require_full_roster=require_full_roster,
        )
        out.append({"week": week, **comp})
    return out


def list_complete_weeks_for_season(
    data: LeagueDataSource,
    season_label: str,
) -> List[int]:
    """Week numbers fully entered (for public site; teams in that week only)."""
    statuses = list_season_week_completion(
        data, season_label, season_teams=None, require_full_roster=False
    )
    return [int(s["week"]) for s in statuses if s["status"] == "complete"]


def _public_weeks_use_completion_gate(
    data: LeagueDataSource,
    season_num: int,
) -> bool:
    """Live / DB-managed seasons only expose fully entered weeks publicly."""
    if is_season_db_managed(season_num):
        return True
    try:
        facts = _facts_for_data(data)
    except TypeError:
        return False
    season_nums = {
        safe_int(f.get("season_number"), 0) for f in facts if f.get("season_number") is not None
    }
    season_nums.discard(0)
    return bool(season_nums) and season_num == max(season_nums)


def list_public_weeks_for_season(
    data: LeagueDataSource,
    season_label: str,
) -> List[int]:
    """Weeks shown on the public home page."""
    season_num = compute.parse_season_number(season_label)
    if season_num is None:
        return []
    if _public_weeks_use_completion_gate(data, season_num):
        return list_complete_weeks_for_season(data, season_label)
    return data.list_weeks_for_season(season_label)


def list_public_seasons(data: LeagueDataSource) -> List[str]:
    """Seasons with at least one public week (newest first)."""
    labels = [
        s
        for s in data.get_seasons()
        if str(s).startswith("Season")
    ]

    def sort_key(name: str) -> int:
        num = compute.parse_season_number(name)
        return num if num is not None else 0

    public: List[str] = []
    for label in sorted(labels, key=sort_key, reverse=True):
        if list_public_weeks_for_season(data, label):
            public.append(label)
    return public


def public_latest_week(data: LeagueDataSource, season_label: str) -> int:
    weeks = list_public_weeks_for_season(data, season_label)
    return weeks[-1] if weeks else 1


def playoff_weeks_by_season(
    data: LeagueDataSource,
    season_labels: List[str],
) -> dict[str, List[int]]:
    """Playoff weeks per season (playoffs flag only — for public UI gating)."""
    facts = _facts_for_data(data)
    out: dict[str, List[int]] = {}
    for label in season_labels:
        out[label] = compute.list_flagged_playoff_weeks_for_season(facts, label)
    return out


ABSENT_FILL_MIN_PLAYED_WEEKS = 3


def _player_played_weeks_before(
    rows: List[dict], player: str, before_week: int
) -> int:
    """Weeks with scored games (not absent/sub) strictly before before_week."""
    weeks: set[int] = set()
    for f in rows:
        if str(f.get("player_display_name") or "").strip() != player:
            continue
        if not fact_counts_for_stats(f) or f.get("absent"):
            continue
        wk = safe_int(f.get("week"), 0)
        if wk < 1 or wk >= before_week or not games_list_for_player_stats(f):
            continue
        weeks.add(wk)
    return len(weeks)


def _player_pin_average(rows: List[dict], player: str) -> Optional[float]:
    """Per-game pin average from non-absent scored weeks."""
    games: List[float] = []
    for f in rows:
        if str(f.get("player_display_name") or "").strip() != player:
            continue
        if not fact_counts_for_stats(f) or f.get("absent"):
            continue
        games.extend(games_list_for_player_stats(f))
    if not games:
        return None
    return sum(games) / len(games)


def build_absent_fill_averages(
    facts: List[dict],
    season_num: int,
    week: int,
    players: List[str],
) -> dict[str, int]:
    """Truncated per-game pin average to pre-fill absent rows on score entry."""
    season_rows = filter_facts(facts, season_num=season_num)
    prior_rows_by_season: dict[int, List[dict]] = {}
    for f in facts:
        sn = safe_int(f.get("season_number"), 0)
        if sn < 1 or sn >= season_num:
            continue
        prior_rows_by_season.setdefault(sn, []).append(f)
    prior_season_nums = sorted(prior_rows_by_season.keys(), reverse=True)

    out: dict[str, int] = {}
    for raw_name in players:
        player = str(raw_name or "").strip()
        if not player:
            continue
        played = _player_played_weeks_before(season_rows, player, week)
        if played >= ABSENT_FILL_MIN_PLAYED_WEEKS:
            scope = [
                f
                for f in season_rows
                if safe_int(f.get("week"), 0) < week
            ]
        else:
            scope = []
            for sn in prior_season_nums:
                candidate = prior_rows_by_season[sn]
                if _player_pin_average(candidate, player) is not None:
                    scope = candidate
                    break
        avg = _player_pin_average(scope, player)
        if avg is not None:
            out[player] = int(avg)
    return out


def team_show_game5_default(team_rows: List[dict]) -> bool:
    """True when this team already has game 5 scores for the week being entered."""
    return any(r.get("game5") is not None for r in team_rows)


def fact_to_entry_row(f: dict) -> dict:
    games = games_slots(f)
    return {
        "team": str(f.get("team") or "").strip(),
        "player_display_name": str(f.get("player_display_name") or "").strip(),
        "opponent": str(f.get("opponent") or "").strip() or None,
        "game1": games[0],
        "game2": games[1],
        "game3": games[2],
        "game4": games[3],
        "game5": games[4],
        "absent": bool(f.get("absent")),
        "game1_absent": bool(f.get("game1_absent")),
        "game2_absent": bool(f.get("game2_absent")),
        "game3_absent": bool(f.get("game3_absent")),
        "game4_absent": bool(f.get("game4_absent")),
        "game5_absent": bool(f.get("game5_absent")),
        "substitute": bool(f.get("substitute")),
        "playoffs": bool(f.get("playoffs")),
    }


def _template_week_rows_from_facts(
    facts: List[dict], season_num: int, week: int
) -> List[dict]:
    """Blank entry rows copied from prior week in facts (no DB roster)."""
    season_rows = filter_facts(facts, season_num=season_num)
    prior_weeks = sorted(
        {safe_int(f.get("week"), 0) for f in season_rows if safe_int(f.get("week"), 0) < week}
    )
    source_week = prior_weeks[-1] if prior_weeks else None
    if source_week is None:
        all_weeks = sorted(
            {safe_int(f.get("week"), 0) for f in season_rows if safe_int(f.get("week"), 0) > 0}
        )
        source_week = all_weeks[-1] if all_weeks else None
    if source_week is None:
        prev_season_rows = filter_facts(facts, season_num=season_num - 1, week=week)
        if season_num > 1 and prev_season_rows:
            template = []
            for f in prev_season_rows:
                if f.get("substitute"):
                    continue
                row = fact_to_entry_row(f)
                row["game1"] = row["game2"] = row["game3"] = row["game4"] = row["game5"] = None
                row["absent"] = False
                row["game1_absent"] = row["game2_absent"] = row["game3_absent"] = False
                row["game4_absent"] = row["game5_absent"] = False
                row["playoffs"] = False
                template.append(row)
            return template
        return []

    template: List[dict] = []
    for f in filter_facts(season_rows, week=source_week):
        if f.get("substitute"):
            continue
        row = fact_to_entry_row(f)
        row["game1"] = row["game2"] = row["game3"] = row["game4"] = row["game5"] = None
        row["absent"] = False
        row["game1_absent"] = row["game2_absent"] = row["game3_absent"] = False
        row["game4_absent"] = row["game5_absent"] = False
        row["playoffs"] = False
        template.append(row)
    return template


def _template_week_rows(facts: List[dict], season_num: int, week: int) -> List[dict]:
    """Roster lines for score entry (membership-aware, else prior-week copy)."""
    from db.roster_members import template_rows_for_week

    with get_session() as session:
        has_members = bool(
            session.scalar(
                select(func.count())
                .select_from(TeamRosterMember)
                .join(Season, TeamRosterMember.season_id == Season.id)
                .where(Season.number == season_num)
            )
        )
        if has_members:
            rows = template_rows_for_week(session, season_num, week)
            session.commit()
            if rows:
                return rows

    return _template_week_rows_from_facts(facts, season_num, week)


def _entry_row_key(row: dict) -> tuple[str, str]:
    return (
        str(row.get("team") or "").strip(),
        str(row.get("player_display_name") or "").strip(),
    )


def _merge_saved_with_template(
    saved_rows: List[dict],
    template_rows: List[dict],
) -> List[dict]:
    """Saved rows win; template fills missing (team, player) pairs for partial weeks."""
    merged: dict[tuple[str, str], dict] = {}
    for row in saved_rows:
        team, player = _entry_row_key(row)
        if team and player:
            merged[(team, player)] = row
    for row in template_rows:
        key = _entry_row_key(row)
        if key[0] and key[1] and key not in merged:
            merged[key] = row
    return sorted(
        merged.values(),
        key=lambda r: (str(r.get("team") or ""), str(r.get("player_display_name") or "")),
    )


def _full_week_entry_rows(
    facts: List[dict],
    season_num: int,
    week: int,
) -> Tuple[List[dict], bool]:
    """Rows for score entry; templated=True only when nothing saved for this week."""
    season_rows = filter_facts(facts, season_num=season_num)
    week_rows = filter_facts(season_rows, week=week)
    template_rows = _template_week_rows(facts, season_num, week)
    if not week_rows:
        return template_rows, True
    saved_rows = [fact_to_entry_row(f) for f in week_rows]
    if not template_rows:
        return saved_rows, False
    return _merge_saved_with_template(saved_rows, template_rows), False


def _facts_for_data(data: LeagueDataSource) -> List[dict]:
    if hasattr(data, "_facts_list"):
        return data._facts_list()
    raise TypeError("Score entry requires DbLeagueData")


def get_week_entry(
    data: LeagueDataSource,
    season_label: str,
    week: int,
    *,
    team: Optional[str] = None,
) -> Tuple[Optional[dict], Optional[str]]:
    season_num = compute.parse_season_number(season_label)
    if season_num is None:
        return None, f"Invalid season: {season_label!r}"
    if week < 1:
        return None, "Week must be at least 1."

    facts = _facts_for_data(data)
    full_entry_rows, templated = _full_week_entry_rows(facts, season_num, week)

    all_teams = sorted({r["team"] for r in full_entry_rows if r.get("team")})
    db_teams = list_season_teams_from_db(season_num)
    season_teams = sorted(set(all_teams) | set(db_teams))
    completion = assess_week_completion(
        full_entry_rows, templated=templated, season_teams=season_teams
    )

    entry_rows = full_entry_rows
    if team:
        team = team.strip()
        entry_rows = [r for r in entry_rows if r.get("team") == team]

    for r in entry_rows:
        r["missing_games"] = _row_missing_game_count(r)

    team_opponents: dict[str, str] = {}
    for r in full_entry_rows:
        t = str(r.get("team") or "").strip()
        opp = r.get("opponent")
        if t and opp and t not in team_opponents:
            team_opponents[t] = str(opp).strip()

    teams_grouped: list[tuple[str, list[dict]]] = []
    if entry_rows:
        if team:
            teams_grouped = [(team, entry_rows)]
        else:
            for t in sorted({str(r.get("team") or "").strip() for r in entry_rows if r.get("team")}):
                team_rows = [r for r in entry_rows if r.get("team") == t]
                teams_grouped.append((t, team_rows))

    players = sorted(
        {
            str(r.get("player_display_name") or "").strip()
            for r in full_entry_rows
            if str(r.get("player_display_name") or "").strip()
        }
    )
    absent_fill_averages = build_absent_fill_averages(
        facts, season_num, week, players
    )
    team_game5_visible = {
        team_name: team_show_game5_default(team_rows)
        for team_name, team_rows in teams_grouped
    }

    return (
        {
            "season": season_label,
            "season_number": season_num,
            "week": week,
            "rows": entry_rows,
            "teams": all_teams,
            "teams_grouped": teams_grouped,
            "team_opponents": team_opponents,
            "week_playoffs": any(r.get("playoffs") for r in full_entry_rows),
            "selected_team": team or "",
            "templated": templated,
            "completion": completion,
            "absent_fill_averages": absent_fill_averages,
            "team_game5_visible": team_game5_visible,
        },
        None,
    )


def list_season_teams_from_db(season_number: int) -> List[str]:
    from sqlalchemy import select

    from db.models import Season, Team
    from db.session import get_session

    session = get_session()
    try:
        season = session.scalar(select(Season).where(Season.number == season_number))
        if season is None:
            return []
        teams = session.scalars(
            select(Team.name).where(Team.season_id == season.id).order_by(Team.name)
        ).all()
        return list(teams)
    finally:
        session.close()


def default_entry_week(
    data: LeagueDataSource,
    season_label: str,
    *,
    season_teams: Optional[List[str]] = None,
) -> int:
    """First week that still needs scores (incomplete or not saved yet)."""
    statuses = list_season_week_completion(
        data, season_label, season_teams=season_teams
    )
    for item in statuses:
        if item["status"] in ("incomplete", "not_started"):
            return int(item["week"])
    latest = data.get_latest_week(season_label)
    return max(latest + 1, 1)


def default_entry_target(data: LeagueDataSource) -> Tuple[str, int]:
    season = data.get_current_season() or "Season 1"
    return season, default_entry_week(data, season)


def mirror_team_opponents(team_opponents: dict[str, str]) -> dict[str, str]:
    """If team A faces B, ensure B faces A."""
    mirrored = dict(team_opponents)
    for team, opp in team_opponents.items():
        t = str(team).strip()
        o = str(opp).strip()
        if t and o:
            mirrored[o] = t
    return mirrored


def parse_week_rows_payload(body: dict) -> Tuple[Optional[List[dict]], Optional[str]]:
    raw_rows = body.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        return None, "Payload must include a non-empty 'rows' array."

    week_playoffs = _bool_field(body.get("playoffs"))
    raw_opponents = body.get("team_opponents")
    team_opponents: dict[str, str] = {}
    if isinstance(raw_opponents, dict):
        for key, val in raw_opponents.items():
            if val:
                team_opponents[str(key).strip()] = str(val).strip()
    team_opponents = mirror_team_opponents(team_opponents)

    parsed: List[dict] = []
    for i, raw in enumerate(raw_rows):
        if not isinstance(raw, dict):
            return None, f"rows[{i}] must be an object."
        team = str(raw.get("team") or "").strip()
        player = str(raw.get("player_display_name") or raw.get("player") or "").strip()
        if not team or not player:
            return None, f"rows[{i}] requires team and player_display_name."
        opponent = raw.get("opponent")
        if opponent:
            opponent = str(opponent).strip() or None
        elif team in team_opponents:
            opponent = team_opponents[team]
        else:
            opponent = None
        absent = _bool_field(raw.get("absent"))
        substitute = _bool_field(raw.get("substitute"))
        label = f"rows[{i}] ({player})"
        games: dict[str, Optional[float]] = {}
        game_absent: dict[str, bool] = {}
        for gn in range(1, 6):
            key = f"game{gn}"
            score, score_err = parse_game_score(raw.get(key))
            if score_err:
                return None, f"{label} {key}: {score_err}"
            games[key] = score
            miss_key = f"game{gn}_absent"
            game_absent[miss_key] = False if absent else _bool_field(raw.get(miss_key))
        parsed.append(
            {
                "team": team,
                "player_display_name": player,
                "opponent": opponent,
                "game1": games["game1"],
                "game2": games["game2"],
                "game3": games["game3"],
                "game4": games["game4"],
                "game5": games["game5"],
                "absent": absent,
                "game1_absent": game_absent["game1_absent"],
                "game2_absent": game_absent["game2_absent"],
                "game3_absent": game_absent["game3_absent"],
                "game4_absent": game_absent["game4_absent"],
                "game5_absent": game_absent["game5_absent"],
                "substitute": substitute,
                "playoffs": week_playoffs,
            }
        )
    return parsed, None


def save_week_entry(
    data: LeagueDataSource,
    season_label: str,
    week: int,
    rows: List[dict],
    *,
    refresh: Callable[[], Tuple[bool, str]],
) -> Tuple[bool, str]:
    season_num = compute.parse_season_number(season_label)
    if season_num is None:
        return False, f"Invalid season: {season_label!r}"
    if week < 1:
        return False, "Week must be at least 1."

    team_opponents: dict[str, str] = {}
    for row in rows:
        team = str(row.get("team") or "").strip()
        opp = row.get("opponent")
        if team and opp:
            team_opponents[team] = str(opp).strip()
    team_opponents = mirror_team_opponents(team_opponents)
    for row in rows:
        team = str(row.get("team") or "").strip()
        if team in team_opponents:
            row["opponent"] = team_opponents[team]

    sheet_key = (
        season_label if season_label.startswith("Season") else f"Season {season_num}"
    )
    session = get_session()
    try:
        count = save_week_rows(
            session,
            season_num,
            week,
            rows,
            sheet_key=sheet_key,
        )
        sync_week_team_opponents(
            session, season_num, week, team_opponents, sheet_key=sheet_key
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        return False, str(exc)
    finally:
        session.close()

    miss_flags = sum(
        1
        for row in rows
        if not row.get("absent")
        for n in range(1, 6)
        if row.get(f"game{n}_absent")
    )
    summary = f"Saved {count} row(s) for {season_label} week {week}."
    if miss_flags:
        summary += f" {miss_flags} missed-game flag(s) recorded."

    ok, msg = refresh()
    if not ok:
        return True, f"{summary} Site cache refresh failed: {msg}"
    return True, summary
