"""Record lists ("bests") over a cross-season (season, week) range.

Backs the Bests tab on the unified stats page. Built on the same range engine
as the leaderboard rather than on the top-N lists in ``stats/compute.py``: those
are positional tuples, hard-sliced to 50, and their per-season tables are
assembled by looping every season in the service layer.

Counting rules are never re-implemented here. Which games belong to a player and
which rows count at all come from ``stats/facts.py``, so a record can never
disagree with the leaderboard about what was bowled.

Every list is ordered by its value with a name tie-break, so equal values come
out in a stable order instead of depending on fact iteration order.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from stats.facts import (
    fact_counts_for_player_profile,
    fact_counts_for_stats,
    filter_facts,
    games_list_for_player_stats,
    player_profile_games,
)
from stats.range_stats import (
    MIN_GAMES_FOR_CONSISTENCY,
    MIN_GAMES_FOR_HIGH_WEEK,
    build_player_accumulators,
    position_label,
    team_pins_by_week,
    team_week_average,
    week_label,
)
from stats.scope import Scope, fact_position

# A record list rewards outliers, so a small sample is the easiest way onto it.
# Roughly four weeks of a normal three-game night.
MIN_GAMES_FOR_SEASON_BEST = 12

# The career-night margin is measured against the bowler's own average, so that
# average needs enough behind it to be worth comparing to.
MIN_GAMES_FOR_CAREER_NIGHT = MIN_GAMES_FOR_CONSISTENCY

# One 200 is a good game, not a streak.
MIN_STREAK = 2

# Enough to fill the list once the reader expands it, without shipping a season
# of rows nobody scrolls to.
LIST_LIMIT = 25

TWO_HUNDRED = 200


def _mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


class _Collected:
    """The four shapes every player record is derived from.

    Gathered in one pass so the rules are applied once, and so a week's games
    stay associated with the week they were bowled in.
    """

    __slots__ = ("games", "weeks", "seasons", "chronological", "teams")

    def __init__(self) -> None:
        # (score, player, team, label)
        self.games: List[Tuple[float, str, str, str]] = []
        # (week average, player, team, label, game count)
        self.weeks: List[Tuple[float, str, str, str, int]] = []
        # player -> season number -> games
        self.seasons: Dict[str, Dict[int, List[float]]] = {}
        # player -> (game, label) in bowled order, for streaks
        self.chronological: Dict[str, List[Tuple[float, str]]] = {}
        # player -> most recent team seen
        self.teams: Dict[str, str] = {}


def _collect(rows: List[dict]) -> _Collected:
    """One ordered pass over the range's rows.

    Rows are sorted by position first: facts do not arrive in bowled order, and
    a streak read out of order is not a streak.
    """
    out = _Collected()
    for f in sorted(rows, key=fact_position):
        player = str(f.get("player_display_name") or "").strip()
        if not player:
            continue

        # Mirrors the leaderboard: a substitute's games count on their own
        # record, everyone else has to clear the roster-window rules first.
        if f.get("substitute"):
            if not fact_counts_for_player_profile(f):
                continue
            games = [float(g) for g in player_profile_games(f)]
        else:
            if not fact_counts_for_stats(f) or f.get("absent"):
                continue
            games = [float(g) for g in games_list_for_player_stats(f)]
        if not games:
            continue

        team = str(f.get("team") or "Unknown").strip()
        out.teams[player] = team
        season_num, _ = fact_position(f)
        label = week_label(f)

        for g in games:
            out.games.append((g, player, team, label))
        out.weeks.append((sum(games) / len(games), player, team, label, len(games)))
        out.seasons.setdefault(player, {}).setdefault(season_num, []).extend(games)
        out.chronological.setdefault(player, []).extend((g, label) for g in games)
    return out


def _entry(**fields) -> dict:
    """A record row. ``when`` is None for anything spanning the whole range."""
    fields.setdefault("when", None)
    return fields


def _ranked(entries: List[dict], key: str, *, high: bool = True) -> List[dict]:
    """Sort by value then name, and cut to the list limit."""
    entries.sort(
        key=lambda e: (
            -e[key] if high else e[key],
            str(e.get("player") or e.get("team") or ""),
        )
    )
    return entries[:LIST_LIMIT]


def _best_games(data: _Collected) -> List[dict]:
    return _ranked(
        [
            _entry(score=int(score), player=player, team=team, when=label)
            for score, player, team, label in data.games
        ],
        "score",
    )


def _best_weeks(data: _Collected) -> List[dict]:
    return _ranked(
        [
            _entry(
                score=round(avg, 2), player=player, team=team, when=label, games=count
            )
            for avg, player, team, label, count in data.weeks
        ],
        "score",
    )


def _best_seasons(data: _Collected) -> List[dict]:
    """Highest single-season average, gated so a cameo season cannot win."""
    entries: List[dict] = []
    for player, by_season in data.seasons.items():
        for season_num, games in by_season.items():
            if len(games) < MIN_GAMES_FOR_SEASON_BEST:
                continue
            avg = _mean(games)
            if avg is None:
                continue
            entries.append(
                _entry(
                    score=round(avg, 2),
                    player=player,
                    team=data.teams.get(player, ""),
                    when="S" + str(season_num),
                    games=len(games),
                )
            )
    return _ranked(entries, "score")


def _most_200s(data: _Collected) -> List[dict]:
    counts: Dict[str, int] = {}
    for score, player, _team, _label in data.games:
        if score >= TWO_HUNDRED:
            counts[player] = counts.get(player, 0) + 1
    return _ranked(
        [
            _entry(score=count, player=player, team=data.teams.get(player, ""))
            for player, count in counts.items()
        ],
        "score",
    )


def _longest_streak(data: _Collected) -> List[dict]:
    """Most consecutive games at 200 or better, in bowled order.

    ``when`` is the span the run covers, collapsed to one label when it started
    and finished on the same night.
    """
    entries: List[dict] = []
    for player, games in data.chronological.items():
        best = run = 0
        start = end = run_start = None
        for score, label in games:
            if score < TWO_HUNDRED:
                run = 0
                continue
            run += 1
            if run == 1:
                run_start = label
            if run > best:
                best, start, end = run, run_start, label
        if best >= MIN_STREAK:
            entries.append(
                _entry(
                    score=best,
                    player=player,
                    team=data.teams.get(player, ""),
                    when=start if start == end else start + " \u2192 " + end,
                )
            )
    return _ranked(entries, "score")


def _most_consistent(player_rows: List[dict]) -> List[dict]:
    """Smallest standard deviation, reusing the leaderboard's own figures."""
    entries = [
        _entry(
            score=row["std_dev"],
            player=row["player"],
            team=row["team"],
            games=row["games"],
        )
        for row in player_rows
        if row.get("std_dev") is not None
        and (row.get("games") or 0) >= MIN_GAMES_FOR_CONSISTENCY
    ]
    return _ranked(entries, "score", high=False)


def _career_nights(data: _Collected) -> List[dict]:
    """Single week whose average is furthest above the bowler's own average."""
    averages: Dict[str, float] = {}
    for player, games in data.chronological.items():
        if len(games) < MIN_GAMES_FOR_CAREER_NIGHT:
            continue
        avg = _mean([score for score, _label in games])
        if avg is not None:
            averages[player] = avg

    best: Dict[str, Tuple[float, float, str, str, int]] = {}
    for week_avg, player, team, label, count in data.weeks:
        avg = averages.get(player)
        if avg is None or count < MIN_GAMES_FOR_HIGH_WEEK:
            continue
        margin = week_avg - avg
        prior = best.get(player)
        if prior is None or margin > prior[0]:
            best[player] = (margin, week_avg, team, label, count)

    return _ranked(
        [
            _entry(
                score=round(margin, 2),
                average=round(week_avg, 2),
                games=count,
                player=player,
                team=team,
                when=label,
            )
            for player, (margin, week_avg, team, label, count) in best.items()
        ],
        "score",
    )


def _most_improved(data: _Collected) -> List[dict]:
    """Gain from a player's previous bowled season to their most recent one.

    "Previous" is the previous season they actually bowled, not the previous
    season number, so someone returning after sitting one out is still compared
    rather than skipped.
    """
    entries: List[dict] = []
    for player, by_season in data.seasons.items():
        eligible = sorted(
            season
            for season, games in by_season.items()
            if len(games) >= MIN_GAMES_FOR_SEASON_BEST
        )
        if len(eligible) < 2:
            continue
        prev_season, last_season = eligible[-2], eligible[-1]
        prev_avg = _mean(by_season[prev_season])
        last_avg = _mean(by_season[last_season])
        if prev_avg is None or last_avg is None:
            continue
        entries.append(
            _entry(
                score=round(last_avg - prev_avg, 2),
                player=player,
                team=data.teams.get(player, ""),
                when="S" + str(prev_season) + " \u2192 S" + str(last_season),
                from_average=round(prev_avg, 2),
                to_average=round(last_avg, 2),
            )
        )
    return _ranked(entries, "score")


def _team_records(rows: List[dict]) -> Dict[str, List[dict]]:
    """Best team week and team season over the range.

    There is no best single team game: the highest game on a team is one
    bowler's game, which the player lists already cover.
    """
    weeks: List[dict] = []
    by_team_season: Dict[Tuple[str, int], List[float]] = {}

    for team, by_week in team_pins_by_week(rows).items():
        for pos, player_games in by_week.items():
            flat = [g for games_ in player_games for g in games_]
            if not flat:
                continue
            avg = team_week_average(player_games)
            if avg is not None:
                weeks.append(
                    _entry(score=round(avg, 2), team=team, when=position_label(pos))
                )
            by_team_season.setdefault((team, pos[0]), []).extend(flat)

    seasons: List[dict] = []
    for (team, season_num), flat in by_team_season.items():
        avg = _mean(flat)
        if avg is None:
            continue
        seasons.append(
            _entry(
                score=round(avg, 2),
                team=team,
                when="S" + str(season_num),
                games=len(flat),
            )
        )

    return {
        "team_weeks": _ranked(weeks, "score"),
        "team_seasons": _ranked(seasons, "score"),
    }


def get_bests(facts: List[dict], scope: Scope, player_rows: List[dict]) -> dict:
    """Every record list for the range.

    ``player_rows`` is the leaderboard's own player list, passed in so the
    consistency record shows exactly the standard deviations the board shows.
    """
    rows = filter_facts(facts, scope=scope)
    data = _collect(rows)

    seasons_covered = sorted(
        {season for by_season in data.seasons.values() for season in by_season}
    )

    categories = {
        "games": _best_games(data),
        "weeks": _best_weeks(data),
        "seasons": _best_seasons(data),
        "most_200s": _most_200s(data),
        "streaks": _longest_streak(data),
        "consistent": _most_consistent(player_rows),
        "career_nights": _career_nights(data),
    }
    # Needs two seasons to mean anything; the tab hides the list when empty.
    categories["improved"] = (
        _most_improved(data) if len(seasons_covered) > 1 else []
    )
    categories.update(_team_records(rows))

    return {
        "scope": {
            "single_season": scope.single_season,
            "seasons_covered": seasons_covered,
        },
        "categories": categories,
    }
