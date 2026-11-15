"""Playoff seeding, round labelling, and next-round projection.

Default league shape: weeks 1–7 regular, 8–10 playoffs. Seeds freeze after
week 7. Quarterfinals are fixed ``1v8, 2v7, 3v6, 4v5``; later rounds reseed
the remaining pool (best vs worst). Placement games live in a separate
losers bracket.

There is no stored schedule: a matchup only exists once scores are entered.
"Upcoming" is always derived from seeds and prior-round outcomes.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from placement_bracket import winner_loser_from_matchup
from stats import compute

# Fixed calendar for the current league format.
LAST_REGULAR_WEEK = 7
PLAYOFF_WEEKS = (8, 9, 10)
ROUND_LABEL_BY_WEEK = {
    8: "Quarterfinals",
    9: "Semifinals",
    10: "Finals",
}

# Display order for the first playoff week.
_QF_SEED_PAIRS = ((1, 8), (2, 7), (3, 6), (4, 5))

# A pair of teams, second side None when the seed advances on a bye.
Pair = Tuple[str, Optional[str]]


def round_label_for_week(week: Optional[int], *, index: int = 0, total: int = 3) -> str:
    """Name for a playoff week; prefers the fixed 8/9/10 labels."""
    if week in ROUND_LABEL_BY_WEEK:
        return ROUND_LABEL_BY_WEEK[week]
    names = {
        1: ["Finals"],
        2: ["Semifinals", "Finals"],
        3: ["Quarterfinals", "Semifinals", "Finals"],
        4: ["Round of 16", "Quarterfinals", "Semifinals", "Finals"],
    }.get(total)
    if names and 0 <= index < len(names):
        return names[index]
    return f"Playoff Round {index + 1}"


def round_label(index: int, total: int) -> str:
    """Name for the ``index``-th playoff round of a ``total``-round bracket."""
    return round_label_for_week(None, index=index, total=total)


def _record_str(wins: int, losses: int, ties: int) -> str:
    """``4-2``, with a third number only when there is a tie to report."""
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def last_regular_week(facts: List[dict], season_num: int) -> Optional[int]:
    """Final non-playoff week of the season, or ``None`` when it has no weeks.

    Prefers week 7 when the season has reached the fixed playoff calendar;
    otherwise the latest regular week at or before 7, falling back to
    playoff-flag detection for odd historical shapes.
    """
    label = compute.season_label(season_num)
    weeks = compute.list_weeks_for_season(facts, label, season_num=season_num)
    if not weeks:
        return None

    le7 = [w for w in weeks if w <= LAST_REGULAR_WEEK]
    if le7 and (
        LAST_REGULAR_WEEK in weeks
        or any(w > LAST_REGULAR_WEEK for w in weeks)
        or max(weeks) <= LAST_REGULAR_WEEK
    ):
        if max(weeks) >= LAST_REGULAR_WEEK and LAST_REGULAR_WEEK in weeks:
            return LAST_REGULAR_WEEK
        return max(le7)

    playoff_weeks = set(
        compute.list_playoff_weeks_for_season(facts, label, season_num=season_num)
    )
    regular = [w for w in weeks if w not in playoff_weeks]
    return max(regular) if regular else None


def uses_fixed_playoff_calendar(detected_playoff_weeks: Sequence[int]) -> bool:
    """True when the season should use the weeks 8–10 skeleton."""
    detected = list(detected_playoff_weeks or [])
    if not detected:
        return True
    return set(detected) <= set(PLAYOFF_WEEKS)


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


def pair_by_reseed(teams: Sequence[str], ranks: Dict[str, int]) -> List[Pair]:
    """Pair remaining teams best vs worst by original seed."""
    ordered = sorted(
        [t for t in teams if t],
        key=lambda t: (ranks.get(t, 10**6), t),
    )
    pairs: List[Pair] = []
    i, j = 0, len(ordered) - 1
    while i < j:
        pairs.append((ordered[i], ordered[j]))
        i += 1
        j -= 1
    if i == j:
        pairs.append((ordered[i], None))
    return pairs


def projected_quarterfinals(seeds: Sequence[dict]) -> List[Pair]:
    """First-round pairs in display order ``1v8, 2v7, 3v6, 4v5``."""
    by_seed = {int(row["seed"]): row["team"] for row in seeds if row.get("team")}
    if all(a in by_seed and b in by_seed for a, b in _QF_SEED_PAIRS):
        return [(by_seed[a], by_seed[b]) for a, b in _QF_SEED_PAIRS]
    names = [row["team"] for row in seeds if row.get("team")]
    return pair_by_reseed(names, seed_rank(seeds))


def projected_first_round(seed_names: Sequence[str]) -> List[Pair]:
    """First-round pairings from an ordered seed-name list (best first)."""
    names = [n for n in seed_names if n]
    seeds = [{"seed": i + 1, "team": n} for i, n in enumerate(names)]
    return projected_quarterfinals(seeds)


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


def _team_names(m: dict) -> Tuple[Optional[str], Optional[str]]:
    home = (m.get("home") or {}).get("name")
    away = ((m.get("away") or {}) or {}).get("name")
    return home, away


def _find_matchup(matchups: Sequence[dict], home: str, away: Optional[str]) -> Optional[dict]:
    """Locate the played game for a projected pair (order-insensitive)."""
    want = {home} | ({away} if away else set())
    for m in matchups:
        h, a = _team_names(m)
        have = {x for x in (h, a) if x}
        if away is None:
            if have == {home}:
                return m
        elif have == want:
            return m
    return None


def _outcomes_for_pairs(
    matchups: Sequence[dict], pairs: Sequence[Pair]
) -> List[Optional[Tuple[str, Optional[str]]]]:
    """Winner/loser per pair; bye slots resolve to the lone team."""
    out: List[Optional[Tuple[str, Optional[str]]]] = []
    for home, away in pairs:
        if not away:
            out.append((home, None))
            continue
        m = _find_matchup(matchups, home, away)
        if not m:
            # Fall back: any matchup containing both names, even if pair order differed.
            out.append(None)
            continue
        wl = winner_loser_from_matchup(m)
        out.append(wl if wl else None)
    return out


def _winners_losers(
    outcomes: Sequence[Optional[Tuple[str, Optional[str]]]]
) -> Tuple[List[str], List[str]]:
    winners: List[str] = []
    losers: List[str] = []
    for wl in outcomes:
        if not wl:
            continue
        w, l = wl
        if w:
            winners.append(w)
        if l:
            losers.append(l)
    return winners, losers


def _order_matchups_by_pairs(
    matchups: Sequence[dict],
    pairs: Sequence[Pair],
    *,
    include_rest: bool = False,
) -> List[dict]:
    """Matchups in pair order. Optionally append games that matched no pair."""
    used = set()
    ordered: List[dict] = []
    for home, away in pairs:
        m = _find_matchup(matchups, home, away)
        if m is not None:
            ordered.append(m)
            used.add(id(m))
    if include_rest:
        for m in matchups:
            if id(m) not in used:
                ordered.append(m)
    return ordered


def _round_payload(
    week: Optional[int],
    label: str,
    matchups: List[dict],
    *,
    projected: bool = False,
) -> dict:
    payload = {
        "week": week,
        "label": label,
        "matchups": matchups,
    }
    if projected:
        payload["projected"] = True
    return payload


def build_bracket(
    playoff_weeks: Sequence[int],
    snapshots: Sequence[Optional[dict]],
    seeds: Sequence[dict],
    *,
    records: Optional[Dict[int, Dict[str, str]]] = None,
) -> dict:
    """Nested winners/losers rounds + upcoming, plus championship winner.

    ``playoff_weeks`` / ``snapshots`` are parallel. For the fixed calendar they
    are weeks 8, 9, 10 (some snapshots may be ``None``).
    """
    ranks = seed_rank(seeds)
    records = records or {}
    weeks = list(playoff_weeks) or list(PLAYOFF_WEEKS)
    by_week: Dict[int, Optional[List[dict]]] = {}
    for i, week in enumerate(weeks):
        by_week[week] = _entered(snapshots[i] if i < len(snapshots) else None)

    qf_week = weeks[0] if weeks else 8
    sf_week = weeks[1] if len(weeks) > 1 else 9
    final_week = weeks[2] if len(weeks) > 2 else 10

    qf_pairs = projected_quarterfinals(seeds)
    qf_ms = by_week.get(qf_week)
    sf_ms = by_week.get(sf_week)
    final_ms = by_week.get(final_week)

    winners_rounds: List[dict] = []
    losers_rounds: List[dict] = []
    winners_upcoming: Optional[dict] = None
    losers_upcoming: Optional[dict] = None
    champion: Optional[str] = None

    champ_pool: List[str] = []
    place_pool: List[str] = []
    sf_champ_winners: List[str] = []
    sf_champ_losers: List[str] = []
    sf_place_winners: List[str] = []
    sf_place_losers: List[str] = []

    # ---- Quarterfinals (championship path only) ----
    if qf_ms is not None:
        ordered = _order_matchups_by_pairs(qf_ms, qf_pairs, include_rest=True)
        winners_rounds.append(
            _round_payload(
                qf_week,
                round_label_for_week(qf_week, index=0, total=len(weeks)),
                [
                    _matchup_row(m, ranks, None, records.get(qf_week))
                    for m in ordered
                ],
            )
        )
        outcomes = _outcomes_for_pairs(qf_ms, qf_pairs)
        champ_pool, place_pool = _winners_losers(outcomes)
    elif qf_pairs:
        week_records = records.get(qf_week) or {}
        winners_upcoming = _round_payload(
            qf_week,
            round_label_for_week(qf_week, index=0, total=len(weeks)),
            [_projected_row(h, a, ranks, None, week_records) for h, a in qf_pairs],
            projected=True,
        )

    # ---- Semifinals (reseed each pool) ----
    if champ_pool or place_pool:
        wb_pairs = pair_by_reseed(champ_pool, ranks)
        lb_pairs = pair_by_reseed(place_pool, ranks)

        if sf_ms is not None:
            wb_ordered = _order_matchups_by_pairs(sf_ms, wb_pairs)
            lb_ordered = _order_matchups_by_pairs(sf_ms, lb_pairs)
            sf_label = round_label_for_week(sf_week, index=1, total=len(weeks))
            week_rec = records.get(sf_week)

            winners_rounds.append(
                _round_payload(
                    sf_week,
                    sf_label,
                    [
                        _matchup_row(m, ranks, "1st-4th Semifinal", week_rec)
                        for m in wb_ordered
                    ],
                )
            )
            # Only attach losers SF games that actually belong to the place pool.
            lb_rows = [
                _matchup_row(m, ranks, "5th-8th Semifinal", week_rec)
                for m in lb_ordered
            ]
            if lb_rows:
                losers_rounds.append(_round_payload(sf_week, sf_label, lb_rows))

            sf_champ_winners, sf_champ_losers = _winners_losers(
                _outcomes_for_pairs(sf_ms, wb_pairs)
            )
            sf_place_winners, sf_place_losers = _winners_losers(
                _outcomes_for_pairs(sf_ms, lb_pairs)
            )
        else:
            week_rec = records.get(sf_week) or {}
            sf_label = round_label_for_week(sf_week, index=1, total=len(weeks))
            if wb_pairs and winners_upcoming is None:
                winners_upcoming = _round_payload(
                    sf_week,
                    sf_label,
                    [
                        _projected_row(h, a, ranks, "1st-4th Semifinal", week_rec)
                        for h, a in wb_pairs
                    ],
                    projected=True,
                )
            if lb_pairs:
                losers_upcoming = _round_payload(
                    sf_week,
                    sf_label,
                    [
                        _projected_row(h, a, ranks, "5th-8th Semifinal", week_rec)
                        for h, a in lb_pairs
                    ],
                    projected=True,
                )

    # ---- Finals / placement finals ----
    if sf_champ_winners or sf_place_winners or sf_champ_losers or sf_place_losers:
        final_pairs = [
            (pair_by_reseed(sf_champ_winners, ranks), "1st & 2nd place", "winners"),
            (pair_by_reseed(sf_champ_losers, ranks), "3rd & 4th place", "winners"),
            (pair_by_reseed(sf_place_winners, ranks), "5th & 6th place", "losers"),
            (pair_by_reseed(sf_place_losers, ranks), "7th & 8th place", "losers"),
        ]
        # Flatten to one pair each (pools of 2).
        flat: List[Tuple[Pair, str, str]] = []
        for pairs, label, bracket in final_pairs:
            for p in pairs:
                flat.append((p, label, bracket))

        if final_ms is not None:
            week_rec = records.get(final_week)
            fin_label = round_label_for_week(final_week, index=2, total=len(weeks))
            w_rows: List[dict] = []
            l_rows: List[dict] = []
            for (home, away), label, bracket in flat:
                m = _find_matchup(final_ms, home, away) if home else None
                if not m:
                    continue
                row = _matchup_row(m, ranks, label, week_rec)
                if bracket == "winners":
                    w_rows.append(row)
                else:
                    l_rows.append(row)
                if label == "1st & 2nd place":
                    wl = winner_loser_from_matchup(m)
                    if wl:
                        champion = wl[0]
            if w_rows:
                winners_rounds.append(_round_payload(final_week, fin_label, w_rows))
            if l_rows:
                losers_rounds.append(_round_payload(final_week, fin_label, l_rows))
        elif winners_upcoming is None:
            week_rec = records.get(final_week) or {}
            fin_label = round_label_for_week(final_week, index=2, total=len(weeks))
            w_proj = [
                _projected_row(h, a, ranks, label, week_rec)
                for (h, a), label, bracket in flat
                if bracket == "winners" and h
            ]
            l_proj = [
                _projected_row(h, a, ranks, label, week_rec)
                for (h, a), label, bracket in flat
                if bracket == "losers" and h
            ]
            if w_proj:
                winners_upcoming = _round_payload(
                    final_week, fin_label, w_proj, projected=True
                )
            if l_proj:
                losers_upcoming = _round_payload(
                    final_week, fin_label, l_proj, projected=True
                )

    return {
        "winners": {"rounds": winners_rounds, "upcoming": winners_upcoming},
        "losers": {"rounds": losers_rounds, "upcoming": losers_upcoming},
        "champion": champion,
    }


def played_rounds(
    playoff_weeks: Sequence[int],
    snapshots: Sequence[Optional[dict]],
    seeds: Sequence[dict],
    *,
    records: Optional[Dict[int, Dict[str, str]]] = None,
) -> List[dict]:
    """Flat list of played rounds (winners then losers per week) for compat."""
    bracket = build_bracket(playoff_weeks, snapshots, seeds, records=records)
    by_week: Dict[int, dict] = {}
    for side in ("winners", "losers"):
        for r in bracket[side]["rounds"]:
            week = r["week"]
            if week not in by_week:
                by_week[week] = {
                    "week": week,
                    "label": r["label"],
                    "matchups": list(r["matchups"]),
                }
            else:
                by_week[week]["matchups"].extend(r["matchups"])
    return [by_week[w] for w in sorted(by_week)]


def upcoming_round(
    playoff_weeks: Sequence[int],
    snapshots: Sequence[Optional[dict]],
    seeds: Sequence[dict],
    *,
    next_week: Optional[int] = None,
    records: Optional[Dict[int, Dict[str, str]]] = None,
) -> Optional[dict]:
    """Next projected championship-side round (compat helper)."""
    weeks = list(playoff_weeks) if playoff_weeks else (
        [next_week] if next_week else list(PLAYOFF_WEEKS)
    )
    # Pad snapshots to the calendar length when callers pass an empty schedule.
    snaps = list(snapshots)
    while len(snaps) < len(weeks):
        snaps.append(None)
    bracket = build_bracket(weeks, snaps, seeds, records=records)
    return bracket["winners"]["upcoming"]


def champion_from_bracket(
    playoff_weeks: Sequence[int],
    snapshots: Sequence[Optional[dict]],
    seeds: Sequence[dict],
) -> Optional[str]:
    """Championship final winner only (week-10 / last playoff week title game)."""
    return build_bracket(playoff_weeks, snapshots, seeds).get("champion")
