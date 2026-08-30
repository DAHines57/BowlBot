"""JSON endpoints backing the unified stats page.

The legacy report routes in ``app/routes.py`` return rendered HTML documents.
These return data, so ``static/app.js`` can re-render without a page load.
"""
from __future__ import annotations

from typing import Optional, Tuple

from flask import Blueprint, current_app, jsonify, request

from db.team_colors import lookup_team_color, readable_hex
from playoff_champion import champion_from_playoff_snapshots
from stats import compute, playoffs
from stats.bests import get_bests
from stats.range_stats import (
    get_player_range_detail,
    get_range_stats,
    get_team_range_detail,
)
from stats.scope import (
    MODE_RANGE,
    MODES,
    PLAYOFF_MODES,
    PLAYOFFS_BOTH,
    PLAYOFFS_REGULAR,
    Scope,
    parse_position,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Sentinel used as an open-ended upper week bound within a season.
WEEK_MAX = 10**6


def _svc():
    return current_app.config.get("LEAGUE_SERVICE")


def _facts():
    svc = _svc()
    if not svc:
        return None
    return svc.data._facts_list()


def _overrides():
    """Matchup overrides when the data source keeps them, else an empty list.

    The sheets-backed source has no override table, so this stays optional
    rather than being part of the ``LeagueDataSource`` contract.
    """
    svc = _svc()
    if not svc:
        return []
    getter = getattr(svc.data, "_overrides_list", None)
    return list(getter()) if callable(getter) else []


# The filter used to be a checkbox, so links and saved sessions still carry
# these. On means both halves of the schedule, off means regular season.
_LEGACY_PLAYOFFS = {
    "1": PLAYOFFS_BOTH,
    "true": PLAYOFFS_BOTH,
    "yes": PLAYOFFS_BOTH,
    "on": PLAYOFFS_BOTH,
    "0": PLAYOFFS_REGULAR,
    "false": PLAYOFFS_REGULAR,
    "no": PLAYOFFS_REGULAR,
    "off": PLAYOFFS_REGULAR,
}


def _playoffs_arg() -> Tuple[Optional[str], Optional[str]]:
    """The ``playoffs`` filter, or an error message for an unknown value."""
    raw = request.args.get("playoffs")
    if raw is None:
        return PLAYOFFS_BOTH, None
    text = str(raw).strip().lower()
    if text in PLAYOFF_MODES:
        return text, None
    if text in _LEGACY_PLAYOFFS:
        return _LEGACY_PLAYOFFS[text], None
    return None, (
        f"Unknown playoffs filter '{raw}'. Expected one of: "
        f"{', '.join(PLAYOFF_MODES)}."
    )


def _season_number(label: Optional[str]) -> Optional[int]:
    if not label:
        return None
    return compute.parse_season_number(label)


def _scope_from_args() -> Tuple[Optional[Scope], Optional[str]]:
    """Build a Scope from ``from``/``to``/``mode``/``playoffs`` query params.

    ``from``/``to`` are ``season.week`` (e.g. ``14.3``). When absent, the scope
    falls back to the current season so a bare request still returns something
    useful.
    """
    mode = (request.args.get("mode") or MODE_RANGE).strip().lower()
    if mode not in MODES:
        return None, f"Unknown mode '{mode}'. Expected one of: {', '.join(MODES)}."

    playoffs, err = _playoffs_arg()
    if err:
        return None, err

    start = parse_position(request.args.get("from"))
    end = parse_position(request.args.get("to"))

    if start is None and end is None:
        svc = _svc()
        season_num = _season_number(svc.data.get_current_season()) if svc else None
        if season_num is None:
            return Scope(mode=mode, playoffs=playoffs), None
        return (
            Scope(
                start=(season_num, 1),
                end=(season_num, WEEK_MAX),
                mode=mode,
                playoffs=playoffs,
            ),
            None,
        )

    if start is not None and end is not None and start > end:
        start, end = end, start

    return (
        Scope(start=start, end=end, mode=mode, playoffs=playoffs),
        None,
    )


def _team_color(name: Optional[str]) -> Optional[str]:
    """Display colour for a team name, ``None`` when it has none set.

    Resolved in this layer rather than in ``stats/range_stats.py`` so
    aggregation stays free of presentation concerns.
    """
    key = (name or "").strip()
    if not key:
        return None
    return readable_hex(lookup_team_color(key))


def _attach_team_colors(data: dict) -> None:
    """Add the display colour for each row's team.

    Cached per team name because a leaderboard repeats the same handful of
    teams across every player row.
    """
    cache: dict = {}

    def color_for(team: str):
        key = (team or "").strip()
        if key not in cache:
            cache[key] = _team_color(key)
        return cache[key]

    for row in data.get("players", []):
        row["color"] = color_for(row.get("team", ""))
    for row in data.get("teams", []):
        row["color"] = color_for(row.get("team", ""))
    # Highlight cards name a team too. Entries are None when the range has no
    # qualifying games, so skip those rather than assuming a dict.
    for card in (data.get("highlights") or {}).values():
        if isinstance(card, dict):
            card["color"] = color_for(card.get("team", ""))


def _attach_bests_colors(data: dict) -> None:
    """Add the display colour to every record row, across all categories."""
    cache: dict = {}

    for entries in (data.get("categories") or {}).values():
        for row in entries:
            key = (row.get("team") or "").strip()
            if key not in cache:
                cache[key] = _team_color(key)
            row["color"] = cache[key]


@api_bp.errorhandler(Exception)
def _api_error(err):  # pragma: no cover - defensive
    return jsonify({"error": str(err)}), 500


@api_bp.route("/meta")
def meta():
    """Seasons, weeks, playoff-week flags, and name catalogs for the filter UI."""
    svc = _svc()
    if not svc:
        return jsonify({"error": "Database not ready."}), 503

    seasons = svc.seasons_sorted()
    out_seasons = []
    for label in seasons:
        season_num = _season_number(label)
        weeks = svc.data.list_weeks_for_season(label)
        playoff_weeks = svc.data.list_playoff_weeks_for_season(label)
        out_seasons.append(
            {
                "label": label,
                "number": season_num,
                "weeks": weeks,
                "playoff_weeks": playoff_weeks,
            }
        )

    current = svc.data.get_current_season()
    return jsonify(
        {
            "seasons": out_seasons,
            "current_season": current,
            "current_season_number": _season_number(current),
            "latest_week": svc.data.get_latest_week(current) if current else None,
            "modes": list(MODES),
        }
    )


@api_bp.route("/leaderboard")
def leaderboard():
    """Player and team leaderboards, league totals, and highlight cards."""
    facts = _facts()
    if facts is None:
        return jsonify({"error": "Database not ready."}), 503

    scope, err = _scope_from_args()
    if err:
        return jsonify({"error": err}), 400

    data = get_range_stats(facts, scope)
    _attach_team_colors(data)

    # PAR is only defined inside a single season, so attach it there and leave
    # it null otherwise rather than showing a misleading cross-season number.
    season_num = scope.single_season
    if season_num is not None:
        par = compute.compute_player_par(facts, season_num=season_num)
        for row in data["players"]:
            row["par"] = par.get(row["player"])
    else:
        for row in data["players"]:
            row["par"] = None
    data["par_available"] = season_num is not None

    return jsonify(data)


@api_bp.route("/bests")
def bests():
    """Record lists for the range, for the Bests tab.

    Its own endpoint rather than more keys on ``/leaderboard`` so opening the
    page does not pay for records until the tab is actually used.
    """
    facts = _facts()
    if facts is None:
        return jsonify({"error": "Database not ready."}), 503

    scope, err = _scope_from_args()
    if err:
        return jsonify({"error": err}), 400

    # The consistency list reuses the leaderboard's own player rows so its
    # standard deviations cannot drift from the ones shown on the board.
    board = get_range_stats(facts, scope)
    data = get_bests(facts, scope, board["players"])
    _attach_bests_colors(data)

    return jsonify(data)


@api_bp.route("/player/<path:name>")
def player_detail(name: str):
    """Stat block plus individual games for one player over the range."""
    facts = _facts()
    if facts is None:
        return jsonify({"error": "Database not ready."}), 503

    scope, err = _scope_from_args()
    if err:
        return jsonify({"error": err}), 400

    detail = get_player_range_detail(facts, name, scope)
    if detail is None:
        return jsonify({"error": f"No games for '{name}' in this range."}), 404

    season_num = scope.single_season
    if season_num is not None:
        par = compute.compute_player_par(facts, season_num=season_num)
        detail["par"] = par.get(detail["player"])
    else:
        detail["par"] = None

    return jsonify(detail)


def _week_game_pins(info: dict) -> list:
    """Per-game team totals for one week, each marked W/L/T against the opponent.

    Mirrors the weekly results image, which compares the two sides game by game
    from the raw pins. An overridden week record can therefore disagree with
    these marks; the W-L column is what carries the override.
    """
    ours = info.get("game_totals") or {}
    theirs = info.get("opp_game_totals") or {}
    slots = [
        slot
        for slot in sorted(set(ours) | set(theirs))
        if (ours.get(slot) or 0) > 0 or (theirs.get(slot) or 0) > 0
    ]
    out = []
    for slot in slots:
        mine = int(ours.get(slot) or 0)
        opp = int(theirs.get(slot) or 0)
        if not opp:
            result = None
        elif mine > opp:
            result = "W"
        elif mine < opp:
            result = "L"
        else:
            result = "T"
        out.append({"pins": mine, "opp_pins": opp, "result": result})
    return out


def _merge_week_records(detail: dict, *, per_game: bool) -> bool:
    """Layer opponent and W-L onto each week row. ``True`` when any merged.

    Matchups are per-season, so the weeks are grouped by the season they came
    from and looked up a season at a time. A team absent from one season of the
    range leaves those weeks unmerged rather than failing the rest. Weeks
    outside the range have no row to merge onto, so a sub-range such as W1-W2
    needs no extra filtering.
    """
    svc = _svc()
    if not svc:
        return False

    seasons = sorted({w["season"] for w in detail["weeks"] if w.get("season")})
    merged = False
    for season_num in seasons:
        summary = svc.data.get_team_weekly_summary(
            detail["team"], compute.season_label(season_num)
        )
        if not summary or summary.get("error"):
            continue

        weekly = summary.get("weekly_summary") or {}
        for row in detail["weeks"]:
            if row.get("season") != season_num:
                continue
            info = weekly.get(row["week"])
            if not info:
                continue
            opponent = info.get("opponent") or None
            row["opponent"] = opponent
            row["opponent_color"] = _team_color(opponent)
            row["wins"] = info.get("wins", 0)
            row["losses"] = info.get("losses", 0)
            row["ties"] = info.get("ties", 0)
            row["record_overridden"] = bool(info.get("record_overridden"))
            row["pins_against"] = info.get("pins_against")
            # Per-game marks compare one matchup, so they stay within a season.
            if per_game:
                row["game_pins"] = _week_game_pins(info)
            merged = True
    return merged


def _record_string(weeks: list) -> Optional[str]:
    """``6-4`` or ``6-4-1`` over the merged weeks only."""
    wins = sum(w.get("wins") or 0 for w in weeks)
    losses = sum(w.get("losses") or 0 for w in weeks)
    ties = sum(w.get("ties") or 0 for w in weeks)
    if not (wins or losses or ties):
        return None
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


@api_bp.route("/team/<path:name>")
def team_detail(name: str):
    """Stat block plus a week-by-week breakdown for one team over the range."""
    facts = _facts()
    if facts is None:
        return jsonify({"error": "Database not ready."}), 503

    scope, err = _scope_from_args()
    if err:
        return jsonify({"error": err}), 400

    detail = get_team_range_detail(facts, name, scope)
    if detail is None:
        return jsonify({"error": f"No games for '{name}' in this range."}), 404

    detail["color"] = _team_color(detail["team"])

    records = _merge_week_records(detail, per_game=scope.single_season is not None)
    detail["records_available"] = records
    detail["record"] = _record_string(detail["weeks"]) if records else None

    return jsonify(detail)


# Champions for a completed season never change, so they are memoized by season
# label to avoid re-deriving every bracket on each page view. The current season
# is excluded because its playoff weeks are still being entered.
_CHAMPION_CACHE: dict = {}


def _champion_for_season(svc, season: str, *, cacheable: bool) -> Optional[str]:
    if cacheable and season in _CHAMPION_CACHE:
        return _CHAMPION_CACHE[season]
    _, snapshots = svc.playoff_snapshots_for_season(season)
    champion = champion_from_playoff_snapshots(snapshots)
    if cacheable:
        _CHAMPION_CACHE[season] = champion
    return champion


def _attach_playoff_colors(data: dict) -> None:
    """Add display colours to every team name in seeds, rounds, and history."""
    cache: dict = {}

    def color_for(team):
        key = (team or "").strip()
        if not key:
            return None
        if key not in cache:
            cache[key] = _team_color(key)
        return cache[key]

    for row in (data.get("seeds") or []) + (data.get("standings") or []):
        row["color"] = color_for(row.get("team"))

    groups = list(data.get("rounds") or [])
    if data.get("upcoming"):
        groups.append(data["upcoming"])
    for group in groups:
        for m in group.get("matchups") or []:
            m["home_color"] = color_for(m.get("home"))
            m["away_color"] = color_for(m.get("away"))

    for row in data.get("history") or []:
        row["champion_color"] = color_for(row.get("champion"))


@api_bp.route("/playoffs")
def playoff_bracket():
    """Seeding, projected upcoming matchups, played rounds, and champions.

    Season-scoped rather than range-scoped: a bracket only makes sense within
    one season, so the shared ``from``/``to`` filters are ignored here.
    """
    svc = _svc()
    facts = _facts()
    if not svc or facts is None:
        return jsonify({"error": "Database not ready."}), 503

    current = svc.data.get_current_season()
    season = svc.resolve_season(request.args.get("season")) or current
    if season == "all":
        season = current
    season_num = _season_number(season)
    if season_num is None:
        return jsonify({"error": f"Unknown season '{season}'."}), 400

    overrides = _overrides()
    last_regular = playoffs.last_regular_week(facts, season_num)
    all_weeks = compute.list_weeks_for_season(facts, season, season_num=season_num)
    last_week = max(all_weeks) if all_weeks else None
    seeds = playoffs.season_seeding(
        facts,
        season_num,
        matchup_overrides=overrides,
        through_week=last_regular,
    )

    playoff_weeks, snapshots = svc.playoff_snapshots_for_season(season)

    next_week = (last_regular + 1) if last_regular else None
    record_weeks = list(playoff_weeks)
    if next_week and next_week not in record_weeks:
        record_weeks.append(next_week)
    records = playoffs.records_before_weeks(
        facts, season_num, record_weeks, matchup_overrides=overrides
    )

    data = {
        "season": season,
        "season_number": season_num,
        "last_regular_week": last_regular,
        "last_week": last_week,
        "playoff_weeks": playoff_weeks,
        "seeds": seeds,
        "standings": playoffs.standings_through_latest(
            facts, season_num, seeds, matchup_overrides=overrides
        ),
        "rounds": playoffs.played_rounds(
            playoff_weeks, snapshots, seeds, records=records
        ),
        "upcoming": playoffs.upcoming_round(
            playoff_weeks,
            snapshots,
            seeds,
            next_week=next_week,
            records=records,
        ),
        "champion": champion_from_playoff_snapshots(snapshots),
        "history": [
            {
                "season": label,
                "season_number": _season_number(label),
                "champion": _champion_for_season(
                    svc, label, cacheable=label != current
                ),
            }
            for label in svc.seasons_sorted()
        ],
    }
    _attach_playoff_colors(data)

    return jsonify(data)
