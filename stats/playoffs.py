"""Playoff seeding, round labelling, and next-round projection.

There is no stored schedule: a matchup only exists once scores are entered. So
"upcoming" here is always derived, either by seeding the regular-season
standings into the bracket or by advancing the winners and losers of the last
playoff week that was entered.

Pure logic over fact rows and week-matchup snapshots, so it can be tested
without a database. The bracket shape itself lives in ``placement_bracket``.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

from placement_bracket import (
    BYE_LOSER,
    SlotWL,
    expected_week2_cross_sets,
    expected_week2_groups,
    expected_week3_groups,
    expected_week3_groups_cross,
    matchups_by_cross_ordered_groups,
    matchups_by_ordered_groups,
    prefer_crossover_week2,
    winner_loser_from_matchup,
)
from playoff_champion import compute_bracket_rounds
from stats import compute

# Round names by how many playoff weeks the season has. Anything longer falls
# back to a generic label rather than inventing round names.
_ROUND_NAMES = {
    1: ["Finals"],
    2: ["Semifinals", "Finals"],
    3: ["Quarterfinals", "Semifinals", "Finals"],
    4: ["Round of 16", "Quarterfinals", "Semifinals", "Finals"],
}

# A pair of teams, second side None when the seed advances on a bye.
Pair = Tuple[str, Optional[str]]


def round_label(index: int, total: int) -> str:
    """Name for the ``index``-th playoff round of a ``total``-round bracket."""
    names = _ROUND_NAMES.get(total)
    if names and 0 <= index < len(names):
        return names[index]
    return f"Playoff Round {index + 1}"


def _record_str(wins: int, losses: int, ties: int) -> str:
    """``4-2``, with a third number only when there is a tie to report."""
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def last_regular_week(facts: List[dict], season_num: int) -> Optional[int]:
    """Final non-playoff week of the season, or ``None`` when it has no weeks."""
    label = compute.season_label(season_num)
    weeks = compute.list_weeks_for_season(facts, label, season_num=season_num)
    if not weeks:
        return None
    playoff_weeks = set(
        compute.list_playoff_weeks_for_season(facts, label, season_num=season_num)
    )
    regular = [w for w in weeks if w not in playoff_weeks]
    return max(regular) if regular else None


def season_seeding(
    facts: List[dict],
    season_num: int,
    *,
    matchup_overrides: Optional[List[dict]] = None,
    through_week: Optional[int] = None,
) -> List[dict]:
    """Teams best seed first, from regular-season record only.

    ``through_week`` makes ``get_team_scores`` exclude playoff rows, so passing
    the last regular week gives standings as they stood entering the playoffs.
    """
    if through_week is None:
        through_week = last_regular_week(facts, season_num)
    if through_week is None:
        return []

    scores = compute.get_team_scores(
        facts,
        None,
        compute.season_label(season_num),
        through_week=through_week,
        season_num=season_num,
        matchup_overrides=matchup_overrides,
    )
    if not isinstance(scores, dict) or "error" in scores or not scores:
        return []

    out = []
    for seed, (team, stats) in enumerate(
        compute.sort_teams_for_playoff_seeding(scores), start=1
    ):
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        ties = stats.get("ties", 0)
        out.append(
            {
                "seed": seed,
                "team": team,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "record": _record_str(wins, losses, ties),
                "pins_for": stats.get("pins_for", 0),
                "avg_per_game": stats.get("avg_per_game", 0),
            }
        )
    return out


def standings_through_week(
    facts: List[dict],
    season_num: int,
    *,
    through_week: Optional[int] = None,
    matchup_overrides: Optional[List[dict]] = None,
) -> List[dict]:
    """The table as it stood after ``through_week``, playoff weeks included.

    This is a display-only view, ordered and numbered from the record as of that
    week. The bracket's own seeding stays frozen at the last regular week, so it
    is computed separately by ``season_seeding``.
    """
    scores = compute.get_team_scores(
        facts,
        None,
        compute.season_label(season_num),
        through_week=through_week,
        season_num=season_num,
        matchup_overrides=matchup_overrides,
        # A cutoff would otherwise drop playoff rows, since get_team_scores
        # leaves them out by default.
        include_playoffs=True,
    )
    if not isinstance(scores, dict) or "error" in scores or not scores:
        return []

    out = []
    for place, (team, stats) in enumerate(
        compute.sort_teams_for_playoff_seeding(scores), start=1
    ):
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        ties = stats.get("ties", 0)
        out.append(
            {
                "seed": place,
                "team": team,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "record": _record_str(wins, losses, ties),
                "pins_for": stats.get("pins_for", 0),
                "avg_per_game": stats.get("avg_per_game", 0),
            }
        )
    return out


def records_before_weeks(
    facts: List[dict],
    season_num: int,
    weeks: Sequence[int],
    *,
    matchup_overrides: Optional[List[dict]] = None,
) -> Dict[int, Dict[str, str]]:
    """Team records as they stood going into each of ``weeks``.

    Playoff weeks count, so a later round shows the wins picked up in earlier
    rounds. Week 1 (and anything with no week before it) maps to an empty dict.
    """
    label = compute.season_label(season_num)
    out: Dict[int, Dict[str, str]] = {}
    for week in weeks:
        if week is None or week < 2:
            out[week] = {}
            continue
        scores = compute.get_team_scores(
            facts,
            None,
            label,
            through_week=week - 1,
            season_num=season_num,
            matchup_overrides=matchup_overrides,
            include_playoffs=True,
        )
        if not isinstance(scores, dict) or "error" in scores:
            out[week] = {}
            continue
        out[week] = {
            team: _record_str(
                stats.get("wins", 0), stats.get("losses", 0), stats.get("ties", 0)
            )
            for team, stats in scores.items()
            if isinstance(stats, dict)
        }
    return out


def seed_rank(seeds: Sequence[dict]) -> Dict[str, int]:
    """Team name to seed number."""
    return {row["team"]: row["seed"] for row in seeds}


def projected_first_round(seed_names: Sequence[str]) -> List[Pair]:
    """First-round pairings in seeded bracket order (1v8, 4v5, 2v7, 3v6 at eight)."""
    names = [n for n in seed_names if n]
    if len(names) < 2:
        return []
    rounds = compute_bracket_rounds(list(names))
    if not rounds:
        return []
    pairs: List[Pair] = []
    for left, right in rounds[0]:
        # Round 0 slots are plain names or None (a bye), never nested tuples.
        home = left if isinstance(left, str) else None
        away = right if isinstance(right, str) else None
        if home is None and away is None:
            continue
        if home is None:
            home, away = away, None
        pairs.append((home, away))
    return pairs


def _slot_results(matchups: List[dict], pairs: Sequence[Pair]) -> List[Optional[SlotWL]]:
    """Winner/loser per bracket slot, aligned 1:1 with ``pairs``.

    Bye slots have no game to look up, so they resolve straight to the seed with
    ``BYE_LOSER`` as the opponent, which the week-2 helpers already understand.
    """
    groups: List[Optional[FrozenSet[str]]] = []
    for home, away in pairs:
        groups.append(frozenset({home, away}) if away else None)

    defined = [g for g in groups if g is not None]
    ordered, _rest = matchups_by_ordered_groups(matchups, defined)
    queue = list(ordered)

    out: List[Optional[SlotWL]] = []
    for (home, _away), group in zip(pairs, groups):
        if group is None:
            out.append((home, BYE_LOSER))
            continue
        m = queue.pop(0) if queue else None
        out.append(winner_loser_from_matchup(m) if m else None)
    return out


def _semi_results(
    matchups: List[dict], qf: List[Optional[SlotWL]]
) -> Tuple[List[Optional[SlotWL]], List[Optional[SlotWL]], bool]:
    """Week-2 outcomes as ``(winners_bracket, losers_bracket, crossover)``.

    Under the crossover format the four games are one flat S0..S3 list, so it
    comes back in the first slot with the second empty.
    """
    if prefer_crossover_week2(matchups, qf):
        cross_sets = expected_week2_cross_sets(qf)
        ordered, _rest = matchups_by_cross_ordered_groups(matchups, cross_sets)
        semis = [winner_loser_from_matchup(m) if m else None for m in ordered]
        return semis, [], True

    wb_groups, lb_groups = expected_week2_groups(qf)
    ordered, _rest = matchups_by_ordered_groups(matchups, wb_groups + lb_groups)
    wb = [winner_loser_from_matchup(m) if m else None for m in ordered[: len(wb_groups)]]
    lb = [winner_loser_from_matchup(m) if m else None for m in ordered[len(wb_groups) :]]
    return wb, lb, False


def _matchup_row(
    m: dict,
    ranks: Dict[str, int],
    label: Optional[str] = None,
    records: Optional[Dict[str, str]] = None,
) -> dict:
    """One played matchup flattened for JSON."""
    home = m.get("home") or {}
    away = m.get("away")
    home_name = home.get("name")
    away_name = (away or {}).get("name")
    records = records or {}
    return {
        "home": home_name,
        "away": away_name,
        "home_seed": ranks.get(home_name or ""),
        "away_seed": ranks.get(away_name or ""),
        "home_record": records.get(home_name or ""),
        "away_record": records.get(away_name or ""),
        "home_game_wins": home.get("wins"),
        "away_game_wins": (away or {}).get("wins"),
        "home_pins": home.get("pins"),
        "away_pins": (away or {}).get("pins"),
        "home_games": list(home.get("game_pins") or []),
        "away_games": list((away or {}).get("game_pins") or []),
        "home_result": home.get("result"),
        "away_result": (away or {}).get("result"),
        "record_overridden": bool(m.get("record_overridden")),
        "label": label,
        "projected": False,
    }


def _projected_row(
    home: str,
    away: Optional[str],
    ranks: Dict[str, int],
    label: Optional[str] = None,
    records: Optional[Dict[str, str]] = None,
) -> dict:
    records = records or {}
    return {
        "home": home,
        "away": away,
        "home_seed": ranks.get(home),
        "away_seed": ranks.get(away or ""),
        "home_record": records.get(home or ""),
        "away_record": records.get(away or ""),
        "label": label,
        "projected": True,
    }


def _entered(snapshot: Optional[dict]) -> Optional[List[dict]]:
    """Matchups from a week snapshot, or ``None`` when the week has no games."""
    if not snapshot or snapshot.get("error"):
        return None
    matchups = snapshot.get("matchups") or []
    return matchups or None


def played_rounds(
    playoff_weeks: Sequence[int],
    snapshots: Sequence[Optional[dict]],
    seeds: Sequence[dict],
    *,
    records: Optional[Dict[int, Dict[str, str]]] = None,
) -> List[dict]:
    """One entry per playoff week that has games, with per-matchup placement labels.

    ``records`` maps a week to the team records going into it, as built by
    ``records_before_weeks``.
    """
    ranks = seed_rank(seeds)
    total = len(playoff_weeks)
    pairs = projected_first_round([row["team"] for row in seeds])

    qf: List[Optional[SlotWL]] = []
    wb: List[Optional[SlotWL]] = []
    lb: List[Optional[SlotWL]] = []
    crossover = False

    rounds: List[dict] = []
    for index, week in enumerate(playoff_weeks):
        matchups = _entered(snapshots[index] if index < len(snapshots) else None)
        if matchups is None:
            continue

        labels: Dict[int, str] = {}
        if index == 0 and pairs:
            qf = _slot_results(matchups, pairs)
        elif index == 1 and qf:
            wb, lb, crossover = _semi_results(matchups, qf)
            if not crossover:
                wb_groups, lb_groups = expected_week2_groups(qf)
                for pos in range(len(wb_groups) + len(lb_groups)):
                    labels[pos] = (
                        "1st-4th Semifinal"
                        if pos < len(wb_groups)
                        else "5th-8th Semifinal"
                    )
        elif index == 2:
            groups = (
                expected_week3_groups_cross(wb)
                if crossover
                else expected_week3_groups(wb, lb)
            )
            for pos, (_teams, label) in enumerate(groups):
                labels[pos] = label

        ordered = _order_for_labels(matchups, index, qf, wb, lb, crossover)
        rounds.append(
            {
                "week": week,
                "label": round_label(index, total),
                "matchups": [
                    _matchup_row(m, ranks, labels.get(pos), (records or {}).get(week))
                    for pos, m in enumerate(ordered)
                ],
            }
        )
    return rounds


def _order_for_labels(
    matchups: List[dict],
    index: int,
    qf: List[Optional[SlotWL]],
    wb: List[Optional[SlotWL]],
    lb: List[Optional[SlotWL]],
    crossover: bool,
) -> List[dict]:
    """Matchups in bracket-slot order so the labels line up; extras kept at the end."""
    groups: List[FrozenSet[str]] = []
    if index == 1 and qf and not crossover:
        wb_groups, lb_groups = expected_week2_groups(qf)
        groups = wb_groups + lb_groups
    elif index == 2:
        labeled = (
            expected_week3_groups_cross(wb)
            if crossover
            else expected_week3_groups(wb, lb)
        )
        groups = [teams for teams, _label in labeled]
    if not groups:
        return list(matchups)

    ordered, rest = matchups_by_ordered_groups(matchups, groups)
    return [m for m in ordered if m] + rest


def upcoming_round(
    playoff_weeks: Sequence[int],
    snapshots: Sequence[Optional[dict]],
    seeds: Sequence[dict],
    *,
    next_week: Optional[int] = None,
    records: Optional[Dict[int, Dict[str, str]]] = None,
) -> Optional[dict]:
    """The next round that has not been bowled, projected from what is known.

    ``None`` once every playoff week has games, or when there are too few teams
    to seed a bracket.
    """
    ranks = seed_rank(seeds)
    pairs = projected_first_round([row["team"] for row in seeds])
    if not pairs:
        return None

    total = len(playoff_weeks) or 3
    index = 0
    for i, _week in enumerate(playoff_weeks):
        if _entered(snapshots[i] if i < len(snapshots) else None) is None:
            break
        index = i + 1
    else:
        if playoff_weeks:
            return None

    week = playoff_weeks[index] if index < len(playoff_weeks) else next_week
    week_records = (records or {}).get(week) or {}

    rows: List[dict] = []
    if index == 0:
        rows = [_projected_row(h, a, ranks, None, week_records) for h, a in pairs]
    elif index == 1:
        qf = _slot_results(_entered(snapshots[0]) or [], pairs)
        wb_groups, lb_groups = expected_week2_groups(qf)
        for pos, group in enumerate(wb_groups + lb_groups):
            label = "1st-4th Semifinal" if pos < len(wb_groups) else "5th-8th Semifinal"
            home, away = _pair_of(group, ranks)
            rows.append(_projected_row(home, away, ranks, label, week_records))
    elif index == 2:
        qf = _slot_results(_entered(snapshots[0]) or [], pairs)
        wb, lb, crossover = _semi_results(_entered(snapshots[1]) or [], qf)
        groups = (
            expected_week3_groups_cross(wb)
            if crossover
            else expected_week3_groups(wb, lb)
        )
        for teams, label in groups:
            home, away = _pair_of(teams, ranks)
            rows.append(_projected_row(home, away, ranks, label, week_records))

    if not rows:
        return None
    return {
        "week": week,
        "label": round_label(index, total),
        "projected": True,
        "matchups": rows,
    }


def _pair_of(group: FrozenSet[str], ranks: Dict[str, int]) -> Pair:
    """A team pair as (home, away), better seed first."""
    members = sorted(group, key=lambda t: (ranks.get(t, 10**6), t))
    if not members:
        return "", None
    if len(members) == 1:
        return members[0], None
    return members[0], members[1]
