"""Leaderboard aggregation over a cross-season (season, week) range.

Backs the unified stats page. Kept separate from ``stats/compute.py`` because
the existing functions there are each scoped to a single season and are relied
on by the legacy report pages.

Aggregation always goes through the helpers in ``stats/facts.py`` so the
substitute, per-game-absent, and roster-window rules stay consistent with the
rest of the app. Anything keyed per team-week uses an ``S{season} W{week}``
label rather than a bare week number, because a bare week collides across
seasons (S1 W3 and S7 W3 would merge).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from stats.facts import (
    canonical_team_name,
    counting_sub_replacements_by_team_week,
    fact_counts_for_player_profile,
    fact_counts_for_stats,
    fact_counts_for_team_pins,
    filter_facts,
    games_list_for_player_stats,
    games_list_for_team,
    player_profile_game_slots,
    player_profile_games,
)
from stats.scope import (
    MODE_CAREER,
    MODE_RANGE,
    MODE_SEASON,
    Position,
    Scope,
    fact_position,
)
from utils import safe_float, safe_int


# Consistency rewards a low spread, which a tiny sample wins by accident, so a
# player needs roughly three full weeks before the card will name them.
MIN_GAMES_FOR_CONSISTENCY = 9

# Below this a "week" is a fragment left by per-game absences, not a night.
MIN_GAMES_FOR_HIGH_WEEK = 2


def position_label(pos: Position) -> str:
    """Season-qualified week label, unique across seasons."""
    return f"S{pos[0]} W{pos[1]}"


def week_label(fact: dict) -> str:
    """Season-qualified week label for a fact row, unique across seasons."""
    return position_label(fact_position(fact))


def _std_dev(games: List[float]) -> float:
    if len(games) < 2:
        return 0.0
    avg = sum(games) / len(games)
    return (sum((g - avg) ** 2 for g in games) / len(games)) ** 0.5


def _mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def absent_week_credit(fact: dict) -> Optional[float]:
    """Average an absent player was credited for the week, or None if unscored.

    Absent weeks are filled from the player's book average times a penalty, and
    those pins count for the team, so the number exists even though it never
    reaches a player average.
    """
    stored = fact.get("week_average")
    if stored is not None and stored != "":
        value = safe_float(stored)
        if value > 0:
            return value
    return _mean(games_list_for_team(fact))


class _PlayerAccumulator:
    """Per-player games, split by season so all three modes can be derived."""

    __slots__ = (
        "team",
        "games_by_season",
        "absences",
        "weeks",
        "sub_games",
        "sub_for",
        "absent_credits",
    )

    def __init__(self, team: str) -> None:
        self.team = team
        self.games_by_season: Dict[int, List[float]] = {}
        self.absences = 0
        self.weeks: set = set()
        self.sub_games: List[float] = []
        self.sub_for: List[str] = []
        # Kept out of games_by_season so a book-average fill can never reach a
        # real average; used only for display and as a last-resort sort key.
        self.absent_credits: List[float] = []

    def add(self, season_num: int, games: List[float], *, label: str) -> None:
        if not games:
            return
        self.games_by_season.setdefault(season_num, []).extend(games)
        self.weeks.add(label)

    @property
    def all_games(self) -> List[float]:
        out: List[float] = []
        for season in sorted(self.games_by_season):
            out.extend(self.games_by_season[season])
        return out

    def average(self, mode: str) -> Optional[float]:
        """Mode-dependent average.

        ``season`` averages the per-season averages so a heavy season does not
        outweigh a light one; ``range`` and ``career`` pool raw games.
        """
        if mode == MODE_SEASON:
            season_avgs = [
                avg
                for avg in (
                    _mean(games) for games in self.games_by_season.values()
                )
                if avg is not None
            ]
            return _mean(season_avgs)
        return _mean(self.all_games)


def build_player_accumulators(rows: List[dict]) -> Dict[str, _PlayerAccumulator]:
    """Per-player games, absences, and sub appearances over the given rows.

    Split out from :func:`_player_rows` so other views can reuse the counting
    rules; ``games_by_season`` in particular is what a per-season record needs.
    """
    acc: Dict[str, _PlayerAccumulator] = {}
    for f in rows:
        player = str(f.get("player_display_name") or "").strip()
        if not player:
            continue
        team = str(f.get("team") or "").strip()
        season_num, _ = fact_position(f)
        is_sub = bool(f.get("substitute"))

        if is_sub:
            if not fact_counts_for_player_profile(f):
                continue
            games = player_profile_games(f)
            entry = acc.setdefault(player, _PlayerAccumulator(team))
            entry.sub_games.extend(games)
            # A sub appearance counts like any other week here: a player who
            # sits out a season but still shows up to fill in has bowled those
            # games. The roster-only rule in fact_counts_for_stats still governs
            # PAR and the season report pages.
            entry.add(season_num, games, label=week_label(f))
            replaced = str(f.get("substituted_for") or "").strip()
            if replaced and replaced not in entry.sub_for:
                entry.sub_for.append(replaced)
            continue

        if not fact_counts_for_stats(f):
            continue
        entry = acc.setdefault(player, _PlayerAccumulator(team))
        if team:
            entry.team = team
        if f.get("absent"):
            entry.absences += 1
            credit = absent_week_credit(f)
            if credit is not None:
                entry.absent_credits.append(credit)
            continue
        entry.add(season_num, games_list_for_player_stats(f), label=week_label(f))

    return acc


def _names_by_season(rows: List[dict], name_key: str) -> List[dict]:
    """Distinct ``name_key`` values per season, oldest season first.

    Used both ways round: the players on a team, and the teams a player was on.
    A name is flagged ``sub`` only when every row behind it that season was a
    substitute appearance, which is the same "an appearance is not membership"
    rule ``build_player_accumulators`` follows. Absences stay in, since a
    rostered player who sat out is still on the roster.
    """
    by_season: Dict[int, Dict[str, dict]] = {}
    for f in rows:
        name = str(f.get(name_key) or "").strip()
        if not name:
            continue
        season_num, _ = fact_position(f)
        entry = by_season.setdefault(season_num, {}).setdefault(
            name, {"name": name, "sub": True}
        )
        if not bool(f.get("substitute")):
            entry["sub"] = False

    out: List[dict] = []
    for season_num in sorted(by_season):
        members = sorted(
            by_season[season_num].values(),
            key=lambda m: (m["sub"], m["name"].lower()),
        )
        out.append(
            {
                "season": season_num,
                "label": f"Season {season_num}",
                "members": members,
            }
        )
    return out


def _player_rows(rows: List[dict], mode: str) -> List[dict]:
    acc = build_player_accumulators(rows)

    out: List[dict] = []
    for player, entry in acc.items():
        games = entry.all_games
        # A player who only ever subbed, or whose every week was a full absence,
        # has no counting games but still belongs on the board so their sub and
        # absence record is reachable.
        if not games and not entry.sub_games and not entry.absences:
            continue
        average = entry.average(mode)
        absent_average = _mean(entry.absent_credits)
        # With nothing bowled there is no real average, so the credited figure
        # stands in purely so the row sorts into position instead of sinking.
        from_absences = average is None and absent_average is not None
        if from_absences:
            average = absent_average
        out.append(
            {
                "player": player,
                "team": entry.team,
                "average": round(average, 2) if average is not None else None,
                "absent_average": (
                    round(absent_average, 2) if absent_average is not None else None
                ),
                "average_from_absences": from_absences,
                "std_dev": round(_std_dev(games), 2) if games else None,
                "highest_game": int(max(games)) if games else None,
                "lowest_game": int(min(games)) if games else None,
                "games": len(games),
                "weeks_played": len(entry.weeks),
                "absences": entry.absences,
                "sub_games": len(entry.sub_games),
                "sub_for": list(entry.sub_for),
            }
        )
    out.sort(key=lambda r: (r["average"] is None, -(r["average"] or 0)))
    return out


def team_pins_by_week(
    rows: List[dict],
) -> Dict[str, Dict[Position, List[List[float]]]]:
    """Counting team games per ``(season, week)``, keyed by team name.

    Each week holds one list of games per player, not a single flat list, so a
    week average can be built from the players' averages rather than from the
    raw games. The two differ whenever players bowled unequal game counts.

    Shared by the team leaderboard rows and the per-team week breakdown so the
    two can never disagree about which games count toward a team's pins.
    """
    # Substitute-replacement lookup keys on (team, week), which collides across
    # seasons, so build one map per season.
    by_season: Dict[int, List[dict]] = {}
    for f in rows:
        by_season.setdefault(fact_position(f)[0], []).append(f)

    pins: Dict[str, Dict[Position, List[List[float]]]] = {}
    for season_rows in by_season.values():
        repl_map = counting_sub_replacements_by_team_week(season_rows)
        for f in season_rows:
            team = str(f.get("team") or "").strip()
            if not team:
                continue
            pos = fact_position(f)
            if pos[1] <= 0:
                continue
            repl = repl_map.get((team, pos[1]), set())
            if not fact_counts_for_team_pins(f, replaced_by_counting_sub=repl):
                continue
            games = games_list_for_team(f)
            if not games:
                continue
            pins.setdefault(team, {}).setdefault(pos, []).append(games)
    return pins


def team_week_average(player_games: List[List[float]]) -> Optional[float]:
    """Mean of the players' averages for one team-week."""
    averages = [avg for avg in (_mean(g) for g in player_games) if avg is not None]
    return _mean(averages)


def _team_row(team: str, by_week: Dict[Position, List[List[float]]]) -> Optional[dict]:
    """One team leaderboard row, or ``None`` when nothing counted.

    Win/loss records are deliberately omitted: they come from matchups, which
    are a per-season concept, and summing them across a range would be
    misleading. The unified page shows pins and averages for team rows.
    """
    all_games: List[float] = []
    # (value, position) so the best and worst weeks can be named, not just
    # measured. Totals stay for the pins column; averages drive the highlights.
    week_totals: List[Tuple[float, Position]] = []
    week_avgs: List[Tuple[float, Position]] = []
    for pos, player_games in by_week.items():
        flat = [g for games in player_games for g in games]
        if not flat:
            continue
        all_games.extend(flat)
        week_totals.append((sum(flat), pos))
        avg = team_week_average(player_games)
        if avg is not None:
            week_avgs.append((avg, pos))
    if not all_games:
        return None
    avg = _mean(all_games)
    best = max(week_totals) if week_totals else None
    worst = min(week_totals) if week_totals else None
    best_avg = max(week_avgs) if week_avgs else None
    worst_avg = min(week_avgs) if week_avgs else None
    # Week-weighted counterpart of avg_per_game; over one week it is exactly
    # the high and low week figures, so the UI shows it in single-week view.
    week_avg = _mean([v for v, _ in week_avgs])
    return {
        "team": team,
        "total_pins": int(sum(all_games)),
        "games": len(all_games),
        "avg_per_game": round(avg, 2) if avg is not None else None,
        "week_avg": round(week_avg, 2) if week_avg is not None else None,
        "weeks": len(by_week),
        "high_week": int(best[0]) if best else None,
        "high_week_label": position_label(best[1]) if best else None,
        "low_week": int(worst[0]) if worst else None,
        "high_week_avg": round(best_avg[0], 2) if best_avg else None,
        "high_week_avg_label": position_label(best_avg[1]) if best_avg else None,
        "low_week_avg": round(worst_avg[0], 2) if worst_avg else None,
        "low_week_avg_label": position_label(worst_avg[1]) if worst_avg else None,
        "high_game": int(max(all_games)),
    }


def _team_rows(rows: List[dict]) -> List[dict]:
    """Team pins and per-week totals over the range."""
    out: List[dict] = []
    for team, by_week in team_pins_by_week(rows).items():
        row = _team_row(team, by_week)
        if row is not None:
            out.append(row)
    out.sort(key=lambda r: (r["avg_per_game"] is None, -(r["avg_per_game"] or 0)))
    return out


def _league_and_highlights(rows: List[dict]) -> Tuple[dict, dict]:
    scored: List[tuple] = []
    players_with_games: set = set()
    # (average, player, team, label) for the best single night bowled.
    best_week: Optional[tuple] = None
    # player -> (count of 200+ games, team), so the leader can be named.
    over_200: Dict[str, Tuple[int, str]] = {}
    for f in rows:
        player = str(f.get("player_display_name") or "").strip()
        if not player:
            continue
        if f.get("absent"):
            continue
        team = str(f.get("team") or "Unknown").strip()
        games = [int(g) for g in games_list_for_player_stats(f)]
        if not games:
            continue
        players_with_games.add(player)
        label = week_label(f)
        for g in games:
            scored.append((g, player, team, label))

        # A per-game absence can leave a single scored game, which is not a
        # night's work and would flatter whoever bowled it.
        if len(games) >= MIN_GAMES_FOR_HIGH_WEEK:
            week_avg = sum(games) / len(games)
            if best_week is None or week_avg > best_week[0]:
                best_week = (week_avg, player, team, label)

        count = len([g for g in games if g >= 200])
        if count:
            prior = over_200.get(player)
            over_200[player] = ((prior[0] if prior else 0) + count, team)

    high_week = None
    if best_week is not None:
        high_week = {
            "score": round(best_week[0], 2),
            "player": best_week[1],
            "team": best_week[2],
            "when": best_week[3],
        }

    most_200s = None
    if over_200:
        leader = max(over_200.items(), key=lambda kv: kv[1][0])
        most_200s = {
            "score": leader[1][0],
            "player": leader[0],
            "team": leader[1][1],
            "when": None,
        }

    high_game = low_game = None
    if scored:
        scored.sort(key=lambda x: x[0])
        for target, src in (("high", scored[-1]), ("low", scored[0])):
            payload = {
                "score": src[0],
                "player": src[1],
                "team": src[2],
                "when": src[3],
            }
            if target == "high":
                high_game = payload
            else:
                low_game = payload

    scores = [s[0] for s in scored]
    league = {
        "league_avg": round(sum(scores) / len(scores), 2) if scores else 0,
        "total_players": len(players_with_games),
        "games_200_plus": len([s for s in scores if s >= 200]),
        "total_games": len(scores),
    }
    return league, {
        "high_game": high_game,
        "low_game": low_game,
        "high_week": high_week,
        "most_200s": most_200s,
    }


def _consistency_highlight(player_rows: List[dict]) -> Optional[dict]:
    """Smallest standard deviation among players with a real sample.

    Takes the finished leaderboard rows rather than the raw facts so the games
    counted here are exactly the ones the player's own row reports.
    """
    scored = [
        r
        for r in player_rows
        if r.get("std_dev") is not None
        and (r.get("games") or 0) >= MIN_GAMES_FOR_CONSISTENCY
    ]
    if not scored:
        return None
    pick = min(scored, key=lambda r: r["std_dev"])
    return {
        "score": pick["std_dev"],
        "player": pick["player"],
        "team": pick["team"],
        "when": None,
        "label": "Most consistent",
    }


def _team_week_highlight(team_rows: List[dict], *, high: bool) -> Optional[dict]:
    """Best or worst team-week, measured by the average of player averages."""
    key = "high_week_avg" if high else "low_week_avg"
    scored = [r for r in team_rows if r.get(key) is not None]
    if not scored:
        return None
    pick = (max if high else min)(scored, key=lambda r: r[key])
    return {
        "score": pick[key],
        "team": pick["team"],
        "when": pick.get(key + "_label"),
        "label": "Team high week" if high else "Team low week",
    }


def get_range_stats(facts: List[dict], scope: Scope) -> dict:
    """Leaderboard payload for a ``(season, week)`` range.

    ``scope.mode`` selects how averages are combined; see
    :meth:`_PlayerAccumulator.average`.
    """
    rows = filter_facts(facts, scope=scope)
    players = _player_rows(rows, scope.mode)
    teams = _team_rows(rows)
    league, highlights = _league_and_highlights(rows)
    # Counted off the finished rows so the tile agrees with the board.
    league["total_teams"] = len(teams)
    highlights["team_high"] = _team_week_highlight(teams, high=True)
    highlights["team_low"] = _team_week_highlight(teams, high=False)
    highlights["consistent"] = _consistency_highlight(players)

    seasons_covered = sorted(
        {safe_int(f.get("season_number"), 0) for f in rows if f.get("season_number")}
    )

    return {
        "scope": {
            "start": list(scope.start) if scope.start else None,
            "end": list(scope.end) if scope.end else None,
            "mode": scope.mode,
            "playoffs": scope.playoffs,
            "single_season": scope.single_season,
            "seasons_covered": seasons_covered,
        },
        "players": players,
        "teams": teams,
        "league": league,
        "highlights": highlights,
    }


def get_player_range_detail(
    facts: List[dict], player_name: str, scope: Scope
) -> Optional[dict]:
    """Per-game detail for one player over the range, for the expanded card."""
    target = player_name.strip().lower()
    rows = [
        f
        for f in filter_facts(facts, scope=scope)
        if str(f.get("player_display_name") or "").strip().lower() == target
    ]
    if not rows:
        return None

    rows.sort(key=fact_position)
    games: List[dict] = []
    absent_weeks: List[dict] = []
    for f in rows:
        season_num, wk = fact_position(f)
        label = f"S{season_num} W{wk}"
        if f.get("absent"):
            credit = absent_week_credit(f)
            absent_weeks.append(
                {
                    "label": label,
                    "season": season_num,
                    "week": wk,
                    "average": round(credit, 2) if credit is not None else None,
                    "games": [int(g) for g in games_list_for_team(f)],
                }
            )
            continue
        is_sub = bool(f.get("substitute"))
        replaced = str(f.get("substituted_for") or "").strip() if is_sub else ""
        for slot in player_profile_game_slots(f):
            games.append(
                {
                    "score": int(slot["score"]),
                    "season": season_num,
                    "week": wk,
                    "game": slot["slot"],
                    "label": label,
                    "is_substitute": is_sub,
                    "substituted_for": replaced or None,
                    "game_absent": slot["absent"],
                    "counts": slot["counts"],
                }
            )

    summary = _player_rows(rows, scope.mode)
    detail = summary[0] if summary else None
    return {
        "player": str(rows[-1].get("player_display_name") or player_name).strip(),
        "summary": detail,
        "games": games,
        "absent_weeks": absent_weeks,
        "teams_by_season": _names_by_season(rows, "team"),
    }


def get_team_range_detail(
    facts: List[dict], team_name: str, scope: Scope
) -> Optional[dict]:
    """Per-week pins for one team over the range, for the expanded card.

    Pins only. Opponents and win/loss live in per-season matchup data, so
    callers layer those on when the range sits inside a single season.
    """
    target = canonical_team_name(team_name.strip()).strip().lower()
    if not target:
        return None

    rows = filter_facts(facts, scope=scope)
    pins = team_pins_by_week(rows)
    match = None
    for team in pins:
        if canonical_team_name(team).strip().lower() == target:
            match = team
            break
    if match is None:
        return None

    by_week = pins[match]
    summary = _team_row(match, by_week)
    if summary is None:
        return None

    weeks: List[dict] = []
    for pos in sorted(by_week):
        player_games = by_week[pos]
        games = [g for gs in player_games for g in gs]
        total = sum(games)
        player_avg = team_week_average(player_games)
        weeks.append(
            {
                "season": pos[0],
                "week": pos[1],
                "label": position_label(pos),
                "pins": int(total),
                "games": len(games),
                "avg": round(total / len(games), 2) if games else None,
                "player_avg": round(player_avg, 2) if player_avg is not None else None,
            }
        )

    # team_pins_by_week drops player identity, so the roster comes off the
    # facts again, keeping only this team's rows.
    team_rows = [
        f
        for f in rows
        if canonical_team_name(str(f.get("team") or "").strip()).strip().lower()
        == target
    ]

    return {
        "team": match,
        "summary": summary,
        "weeks": weeks,
        "rosters": _names_by_season(team_rows, "player_display_name"),
    }
