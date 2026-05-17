"""
Pairing logic for common 8-team *full-field* bowling playoffs (every team bowls each week).

From a typical three-week sheet layout (quarterfinals → two side semis → placement finals):

**Week 1 — winners bracket only (four quarterfinals)**  
Matchups follow the standard seeded single-elimination order:

    QF1: 1 vs 8    QF2: 4 vs 5    QF3: 2 vs 7    QF4: 3 vs 6

**Week 2 — parallel brackets**  
*Winners bracket (playing for 1st–4th)* — QF winners meet the same way winners would in
a classic bracket::

    WB-SF1: winner(QF1) vs winner(QF2)
    WB-SF2: winner(QF3) vs winner(QF4)

*Losers bracket (playing for 5th–8th)* — QF losers are paired in the **same structure**::

    LB-SF1: loser(QF1) vs loser(QF2)
    LB-SF2: loser(QF3) vs loser(QF4)

So each “semis” week has four games: two on the undefeated track and two on the
first-loss / placement track.

**Alternate week-2 format (crossover / “relay”)** — seen when each team still plays
once but pairings are *winner vs loser* from *adjacent* quarterfinals within each
half of the draw::

    Game A: winner(QF1) vs loser(QF2)     Game B: loser(QF1) vs winner(QF2)
    Game C: loser(QF3) vs winner(QF4)    Game D: winner(QF3) vs loser(QF4)

Week 3 pairs outcomes of those four games as in ``expected_week3_groups_cross``:
championship is winners of S1 & S2; **winners of S0 & S3 play for 3rd & 4th**;
**losers of S1 & S2 play for 5th & 6th**; losers of S0 & S3 play for 7th & 8th.

The HTML bracket picks **parallel** vs **crossover** by counting which set of
expected team pairs matches the sheet for that week.

**Week 3 — everyone placed**  
*From week-2 winners bracket:*

    Championship: winner(WB-SF1) vs winner(WB-SF2)   → 1st & 2nd
    Consolation:  loser(WB-SF1) vs loser(WB-SF2)    → 3rd & 4th

*From week-2 losers bracket:*

    5th–6th: winner(LB-SF1) vs winner(LB-SF2)
    7th–8th: loser(LB-SF1) vs loser(LB-SF2)

Ties on the sheet are ignored until a winner/loser is recorded. Total pins (or
league rules) are assumed to already be reflected in who is marked W/L on the sheet.
"""

from __future__ import annotations

from typing import FrozenSet, List, Optional, Tuple, cast

# (winner_name, loser_name) for a decided game — exported for bracket HTML helpers
SlotWL = Tuple[str, str]

# Loser placeholder when a team advances on a quarterfinal bye (no opponent game).
BYE_LOSER = "__BYE__"


def _norm_team(name: str) -> str:
    """Lowercase, strip, flatten curly quotes — match sheets_handler / Google Sheets quirks."""
    n = str(name).strip().lower()
    return (
        n.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def _loose_name_eq(a: str, b: str) -> bool:
    x, y = _norm_team(a), _norm_team(b)
    if x == y:
        return True
    if len(x) < 2 or len(y) < 2:
        return x == y
    return x in y or y in x


def sheet_matchup_matches_expected_pair(
    m: dict, expected: FrozenSet[str], *, strict: bool = True
) -> bool:
    """Whether this sheet matchup is the two teams in ``expected`` (home/away order free)."""
    away = m.get("away")
    if not away or len(expected) != 2:
        return False
    hn = str(m["home"]["name"])
    an = str(away["name"])
    en = frozenset({_norm_team(t) for t in expected})
    sn = frozenset({_norm_team(hn), _norm_team(an)})
    if sn == en:
        return True
    if strict:
        return False
    e1, e2 = tuple(expected)
    return (_loose_name_eq(e1, hn) and _loose_name_eq(e2, an)) or (
        _loose_name_eq(e1, an) and _loose_name_eq(e2, hn)
    )


def _matchup_total_pins(side: dict) -> int:
    """Team pin total for the week (sum of game_pins, else pins field)."""
    gp = side.get("game_pins") or []
    if gp:
        return int(sum(gp))
    return int(side.get("pins", 0) or 0)


def winner_loser_from_matchup(m: dict) -> Optional[SlotWL]:
    away = m.get("away")
    if not away:
        return None
    home, a = m["home"], cast(dict, away)
    hr, ar = home.get("result", ""), a.get("result", "")
    hn, an = cast(str, home["name"]), cast(str, a["name"])
    if hr == "W" and ar == "L":
        return (hn, an)
    if ar == "W" and hr == "L":
        return (an, hn)
    # Matchup tie (sheet T/T or 2–2 override) — higher total pins wins the week.
    hp = _matchup_total_pins(home)
    ap = _matchup_total_pins(a)
    if hp > ap:
        return (hn, an)
    if ap > hp:
        return (an, hn)
    return None


def qf_slot_results_in_order(ordered_qf_matchups: List[dict]) -> List[Optional[SlotWL]]:
    """Quarterfinal slots in bracket order (4 games). None = not finished or tied."""
    return [winner_loser_from_matchup(m) for m in ordered_qf_matchups]


def expected_week2_groups(
    qf: List[Optional[SlotWL]],
) -> Tuple[List[FrozenSet[str]], List[FrozenSet[str]]]:
    """(winners_bracket team pairs, losers_bracket team pairs), each up to length 2."""
    if len(qf) != 4:
        return [], []

    def w(slot: int) -> Optional[str]:
        wl = qf[slot]
        return wl[0] if wl else None

    def ell(slot: int) -> Optional[str]:
        wl = qf[slot]
        if not wl or wl[1] == BYE_LOSER:
            return None
        return wl[1]

    wb_groups: List[FrozenSet[str]] = []
    lb_groups: List[FrozenSet[str]] = []
    a, b, c, d = w(0), w(1), w(2), w(3)
    if a and b:
        wb_groups.append(frozenset({a, b}))
    if c and d:
        wb_groups.append(frozenset({c, d}))
    la, lb_, lc, ld = ell(0), ell(1), ell(2), ell(3)
    if la and lb_:
        lb_groups.append(frozenset({la, lb_}))
    if lc and ld:
        lb_groups.append(frozenset({lc, ld}))
    return wb_groups, lb_groups


def expected_week2_cross_sets(
    qf: List[Optional[SlotWL]],
) -> List[Optional[FrozenSet[str]]]:
    """Four semifinal pairings in fixed order S0..S3 (crossover / relay format).

    S0: W(QF1) vs L(QF2)   S1: L(QF1) vs W(QF2)
    S2: L(QF3) vs W(QF4)   S3: W(QF3) vs L(QF4)

    Indices 0..3 are quarterfinal slots in seeded bracket order. Slots with
    incomplete QF yield None for that pairing.
    """
    if len(qf) != 4:
        return [None, None, None, None]

    def w(i: int) -> Optional[str]:
        wl = qf[i]
        return wl[0] if wl else None

    def ell(i: int) -> Optional[str]:
        wl = qf[i]
        if not wl or wl[1] == BYE_LOSER:
            return None
        return wl[1]

    pairs: List[Optional[FrozenSet[str]]] = []
    if w(0) and ell(1):
        pairs.append(frozenset({w(0), ell(1)}))
    else:
        pairs.append(None)
    if ell(0) and w(1):
        pairs.append(frozenset({ell(0), w(1)}))
    else:
        pairs.append(None)
    if ell(2) and w(3):
        pairs.append(frozenset({ell(2), w(3)}))
    else:
        pairs.append(None)
    if w(2) and ell(3):
        pairs.append(frozenset({w(2), ell(3)}))
    else:
        pairs.append(None)
    return pairs


def count_sheet_matches_for_groups(matchups: List[dict], group_sets: List[FrozenSet[str]]) -> int:
    """How many distinct sheet games match one of the expected team pairs."""
    used: set[int] = set()
    n = 0
    for teams in group_sets:
        for i, m in enumerate(matchups):
            if i in used:
                continue
            away = m.get("away")
            if not away:
                continue
            if sheet_matchup_matches_expected_pair(m, teams, strict=True):
                used.add(i)
                n += 1
                break
        else:
            for i, m in enumerate(matchups):
                if i in used:
                    continue
                away = m.get("away")
                if not away:
                    continue
                if sheet_matchup_matches_expected_pair(m, teams, strict=False):
                    used.add(i)
                    n += 1
                    break
    return n


def prefer_crossover_week2(matchups: List[dict], qf: List[Optional[SlotWL]]) -> bool:
    """True if sheet semis match the crossover model better than parallel WB/LB."""
    par_wb, par_lb = expected_week2_groups(qf)
    parallel = par_wb + par_lb
    cross_defined = [s for s in expected_week2_cross_sets(qf) if s is not None]
    if not parallel and not cross_defined:
        return False
    cp = count_sheet_matches_for_groups(matchups, parallel)
    cc = count_sheet_matches_for_groups(matchups, cross_defined)
    if cc > cp:
        return True
    if cp > cc:
        return False
    return False


def matchups_by_cross_ordered_groups(
    matchups: List[dict],
    cross_sets: List[Optional[FrozenSet[str]]],
) -> Tuple[List[Optional[dict]], List[dict]]:
    """Map sheet games to S0..S3 in order; leftovers unmatched to the crossover model."""
    n = len(cross_sets)
    ordered: List[Optional[dict]] = [None] * n
    used: set[int] = set()

    def fill(strict: bool) -> None:
        for slot_i, teams in enumerate(cross_sets):
            if teams is None or ordered[slot_i] is not None:
                continue
            for mi, m in enumerate(matchups):
                if mi in used:
                    continue
                away = m.get("away")
                if not away:
                    continue
                if sheet_matchup_matches_expected_pair(m, teams, strict=strict):
                    used.add(mi)
                    ordered[slot_i] = m
                    break

    fill(strict=True)
    fill(strict=False)
    rest = [m for i, m in enumerate(matchups) if i not in used]
    return ordered, rest


def expected_week3_groups_cross(
    semis: List[Optional[SlotWL]],
) -> List[Tuple[FrozenSet[str], str]]:
    """Finals from crossover semis S0..S3 (each SlotWL is winner/loser of that game)."""
    if len(semis) < 4 or not all(semis):
        return []
    s0, s1, s2, s3 = semis[0], semis[1], semis[2], semis[3]
    assert s0 and s1 and s2 and s3
    return [
        (frozenset({s1[0], s2[0]}), "1st & 2nd place"),
        (frozenset({s0[0], s3[0]}), "3rd & 4th place"),
        (frozenset({s1[1], s2[1]}), "5th & 6th place"),
        (frozenset({s0[1], s3[1]}), "7th & 8th place"),
    ]


def expected_week3_groups(
    wb_semis: List[Optional[SlotWL]],
    lb_semis: List[Optional[SlotWL]],
) -> List[Tuple[FrozenSet[str], str]]:
    """Four finals-week pairings and short labels (sheet-style)."""
    out: List[Tuple[FrozenSet[str], str]] = []

    if len(wb_semis) >= 2 and wb_semis[0] and wb_semis[1]:
        w0, w1 = wb_semis[0], wb_semis[1]
        out.append(
            (
                frozenset({w0[0], w1[0]}),
                "1st & 2nd place",
            )
        )
        out.append(
            (
                frozenset({w0[1], w1[1]}),
                "3rd & 4th place",
            )
        )

    if len(lb_semis) >= 2 and lb_semis[0] and lb_semis[1]:
        l0, l1 = lb_semis[0], lb_semis[1]
        out.append(
            (
                frozenset({l0[0], l1[0]}),
                "5th & 6th place",
            )
        )
        out.append(
            (
                frozenset({l0[1], l1[1]}),
                "7th & 8th place",
            )
        )

    return out


def order_matchups_by_labeled_groups(
    matchups: List[dict],
    groups: List[Tuple[FrozenSet[str], str]],
) -> Tuple[List[Tuple[str, Optional[dict]]], List[dict]]:
    """One (label, matchup | None) per expected group; leftover sheet rows last."""
    used: set[int] = set()
    out: List[Tuple[str, Optional[dict]]] = []
    for teams, label in groups:
        hit: Optional[dict] = None
        for strict in (True, False):
            for i, m in enumerate(matchups):
                if i in used:
                    continue
                away = m.get("away")
                if not away:
                    continue
                if sheet_matchup_matches_expected_pair(m, teams, strict=strict):
                    used.add(i)
                    hit = m
                    break
            if hit:
                break
        out.append((label, hit))
    rest = [m for i, m in enumerate(matchups) if i not in used]
    return out, rest


def matchups_by_ordered_groups(
    matchups: List[dict],
    group_sets: List[FrozenSet[str]],
) -> Tuple[List[Optional[dict]], List[dict]]:
    """First tuple element aligns 1:1 with group_sets; second is unmatched matchups."""
    used: set[int] = set()
    ordered: List[Optional[dict]] = []
    for teams in group_sets:
        hit: Optional[dict] = None
        for strict in (True, False):
            for i, m in enumerate(matchups):
                if i in used:
                    continue
                away = m.get("away")
                if not away:
                    continue
                if sheet_matchup_matches_expected_pair(m, teams, strict=strict):
                    used.add(i)
                    hit = m
                    break
            if hit:
                break
        ordered.append(hit)
    rest = [m for i, m in enumerate(matchups) if i not in used]
    return ordered, rest
