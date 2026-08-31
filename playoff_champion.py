"""Playoff champion detection and bracket round/placement math.

Pure logic, no HTML. The champion badges and the bracket on the stats page come
from here, via ``/api/playoffs``.
"""
import itertools
from typing import Dict, FrozenSet, List, Optional, Set, Tuple, Union, cast

from placement_bracket import (
    BYE_LOSER,
    SlotWL,
    expected_week2_cross_sets,
    expected_week2_groups,
    expected_week3_groups,
    expected_week3_groups_cross,
    matchups_by_cross_ordered_groups,
    matchups_by_ordered_groups,
    order_matchups_by_labeled_groups,
    prefer_crossover_week2,
    qf_slot_results_in_order,
    sheet_matchup_matches_expected_pair,
    winner_loser_from_matchup,
)


def _playoff_snapshots_with_matchups(
    snapshots: List[Optional[dict]],
) -> List[dict]:
    return [s for s in (snapshots or []) if s and s.get("matchups")]

def _champion_from_labeled_finals(valid: List[dict], ms: List[dict]) -> Optional[str]:
    """Winner of the 1st-place game when the finals week has placement matchups."""
    w3_groups: List[Tuple[FrozenSet[str], str]] = []
    if len(valid) >= 3:
        qf_ms = list(valid[0]["matchups"])
        ms1 = list(valid[1]["matchups"])
        teams: Set[str] = set()
        for s in valid:
            for m in s["matchups"]:
                teams.add(cast(str, m["home"]["name"]))
                away = m.get("away")
                if away:
                    teams.add(cast(str, away["name"]))
        round_pairs = compute_bracket_rounds(sorted(teams))[0] if len(teams) >= 2 else []
        w3_groups = _best_w3_groups(qf_ms, ms1, ms, round_pairs, snapshots=valid)
    elif len(valid) == 2:
        parallel = _resolve_two_week_parallel_playoffs(valid, seed_rank=None)
        if parallel:
            w3_groups = list(parallel.get("w3_groups") or [])
    if not w3_groups:
        return None
    ordered, _ = order_matchups_by_labeled_groups(ms, w3_groups)
    for label, mm in ordered:
        if label.startswith("1st") and mm:
            wl = winner_loser_from_matchup(mm)
            if wl:
                return wl[0]
    return None

def _champion_from_unbeaten_final(valid: List[dict], ms: List[dict]) -> Optional[str]:
    """Fallback: finals game between two teams still undefeated in prior playoff weeks."""
    losses: Dict[str, int] = {}
    for s in valid[:-1]:
        for m in _playoff_matchups_with_opponent(list(s["matchups"])):
            wl = winner_loser_from_matchup(m)
            if not wl:
                continue
            winner, loser = wl
            losses[loser] = losses.get(loser, 0) + 1
            losses.setdefault(winner, losses.get(winner, 0))
    for m in ms:
        away = m.get("away")
        if not away:
            continue
        h, a = cast(str, m["home"]["name"]), cast(str, away["name"])
        if losses.get(h, 0) != 0 or losses.get(a, 0) != 0:
            continue
        wl = winner_loser_from_matchup(m)
        if wl:
            return wl[0]
    return None

def champion_from_playoff_snapshots(snapshots: List[Optional[dict]]) -> Optional[str]:
    """Playoff champion: winner of the 1st-place game (or sole finals matchup)."""
    valid = _playoff_snapshots_with_matchups(snapshots)
    if not valid:
        return None
    ms = _playoff_matchups_with_opponent(list(valid[-1]["matchups"]))
    if not ms:
        return None
    if len(ms) == 1:
        wl = winner_loser_from_matchup(ms[0])
        return wl[0] if wl else None
    champ = _champion_from_labeled_finals(valid, ms)
    if champ:
        return champ
    return _champion_from_unbeaten_final(valid, ms)

def _bracket_next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p <<= 1
    return max(p, 2)

def _bracket_seed_order(size: int) -> List[int]:
    if size < 2:
        return [1]
    if size == 2:
        return [1, 2]
    prev = _bracket_seed_order(size // 2)
    out: List[int] = []
    for s in prev:
        out.append(s)
        out.append(size + 1 - s)
    return out

BracketSlot = Union[None, str, Tuple["BracketSlot", "BracketSlot"]]

def _advance_bracket_slot(left: Optional[str], right: Optional[str]) -> BracketSlot:
    """Promote winners from one first-round-style matchup (optional team names)."""
    if left is None and right is None:
        return None
    if left is None:
        return right  # type: ignore[return-value]
    if right is None:
        return left
    return (left, right)

def _combine_slots(left: BracketSlot, right: BracketSlot) -> BracketSlot:
    """Pair two advancing slots into the next round's matchup side (nested pending)."""
    if left is None and right is None:
        return None
    if left is None:
        return right
    if right is None:
        return left
    return (left, right)

def compute_bracket_rounds(seeded_teams: List[str]) -> List[List[Tuple[BracketSlot, BracketSlot]]]:
    """seeded_teams[0] is 1-seed. Standard adjacent pairing; byes for non-power-of-2.
    After round 0, undecided games become nested (A, B) tuples so later rounds show
    'Winner advances' trees instead of BYE placeholders."""
    n = len(seeded_teams)
    if n < 1:
        return []
    size = _bracket_next_pow2(n)
    order = _bracket_seed_order(size)
    leaf: List[Optional[str]] = []
    for sn in order:
        if sn <= n:
            leaf.append(seeded_teams[sn - 1])
        else:
            leaf.append(None)
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]] = []
    cur_q: List[Tuple[Optional[str], Optional[str]]] = [
        (leaf[i], leaf[i + 1]) for i in range(0, len(leaf), 2)
    ]
    rounds.append([(a, b) for a, b in cur_q])  # type: ignore[list-item]
    cur_slots: List[BracketSlot] = [_advance_bracket_slot(L, R) for L, R in cur_q]
    while len(cur_slots) > 1:
        next_matchups = [
            (cur_slots[i], cur_slots[i + 1])
            for i in range(0, len(cur_slots), 2)
        ]
        rounds.append(next_matchups)
        cur_slots = [_combine_slots(L, R) for L, R in next_matchups]
    return rounds

def _slot_team_names(slot: BracketSlot) -> FrozenSet[str]:
    if slot is None:
        return frozenset()
    if isinstance(slot, str):
        return frozenset({slot})
    L, R = slot
    return _slot_team_names(L) | _slot_team_names(R)

def _theoretical_pair_team_pool(left: BracketSlot, right: BracketSlot) -> FrozenSet[str]:
    return _slot_team_names(left) | _slot_team_names(right)

def _matchup_fits_theoretical_pool(m: dict, pool: FrozenSet[str]) -> bool:
    away = m.get("away")
    if not away:
        return m["home"]["name"] in pool
    return frozenset({m["home"]["name"], away["name"]}).issubset(pool)

def _match_matchups_to_theoretical_round(
    matchups: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
) -> Tuple[List[dict], List[bool]]:
    """Order sheet matchups like the seeded bracket (not alphabetically by home).

    The first len(round_pairs) entries that get assigned from the main loop are
    *theoretically aligned* to bracket slots (one try per slot). Remaining sheet
    games are full-field extras (e.g. cross-bracket); flags mark aligned ones.
    """
    used: Set[int] = set()
    out: List[dict] = []
    aligned: List[bool] = []
    for left, right in round_pairs:
        pool = _theoretical_pair_team_pool(left, right)
        for i, m in enumerate(matchups):
            if i in used:
                continue
            if _matchup_fits_theoretical_pool(m, pool):
                used.add(i)
                out.append(m)
                aligned.append(True)
                break
    for i, m in enumerate(matchups):
        if i not in used:
            out.append(m)
            aligned.append(False)
    return out, aligned

def _solo_teams_in_week(matchups: List[dict]) -> List[str]:
    return [m["home"]["name"] for m in matchups if not m.get("away")]

def _slot_wl_from_matchup(m: Optional[dict]) -> Optional[SlotWL]:
    if not m:
        return None
    if m.get("_bye_pair"):
        return (cast(str, m["home"]["name"]), BYE_LOSER)
    if not m.get("away"):
        return (cast(str, m["home"]["name"]), BYE_LOSER)
    return winner_loser_from_matchup(m)

def qf_matchups_in_bracket_slot_order(
    matchups: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
) -> List[Optional[dict]]:
    """One entry per bracket QF slot; None if no sheet game uses that seed pairing."""
    slots: List[Optional[dict]] = [None] * len(round_pairs)
    used: Set[int] = set()
    for i, (left, right) in enumerate(round_pairs):
        pool = _theoretical_pair_team_pool(left, right)
        for j, m in enumerate(matchups):
            if j in used:
                continue
            if _matchup_fits_theoretical_pool(m, pool):
                used.add(j)
                slots[i] = m
                break
    leftover_idxs = [
        j
        for j in range(len(matchups))
        if j not in used and matchups[j].get("away")
    ]
    while leftover_idxs:
        best_j: Optional[int] = None
        best_i: Optional[int] = None
        best_ov = 0
        empty = [i for i in range(len(slots)) if slots[i] is None]
        for j in leftover_idxs:
            m = matchups[j]
            away = m.get("away")
            if not away:
                continue
            teams = frozenset({m["home"]["name"], away["name"]})
            for i in empty:
                pool = _theoretical_pair_team_pool(round_pairs[i][0], round_pairs[i][1])
                ov = len(teams & pool)
                if ov > best_ov:
                    best_ov = ov
                    best_j = j
                    best_i = i
        if best_j is None or best_i is None:
            j = leftover_idxs.pop(0)
            for i in range(len(slots)):
                if slots[i] is None:
                    slots[i] = matchups[j]
                    used.add(j)
                    break
            continue
        slots[best_i] = matchups[best_j]
        used.add(best_j)
        leftover_idxs.remove(best_j)

    teams_in_slots: Set[str] = set()
    for s in slots:
        if not s:
            continue
        teams_in_slots.add(s["home"]["name"])
        away = s.get("away")
        if away:
            teams_in_slots.add(away["name"])
    solo = [t for t in _solo_teams_in_week(matchups) if t not in teams_in_slots]
    solo_used: Set[str] = set()
    for i, (left, right) in enumerate(round_pairs):
        if slots[i] is not None:
            continue
        pool = _theoretical_pair_team_pool(left, right)
        in_pool = [t for t in solo if t in pool and t not in solo_used]
        if len(in_pool) == 1:
            nm = in_pool[0]
            solo_used.add(nm)
            slots[i] = {
                "home": {"name": nm, "result": "W", "pins": 0, "avg": 0, "game_pins": [], "wins": 0},
                "away": None,
            }
        elif len(in_pool) >= 2:
            for nm in in_pool[:2]:
                solo_used.add(nm)
            slots[i] = {
                "home": {
                    "name": in_pool[0],
                    "result": "W",
                    "pins": 0,
                    "avg": 0,
                    "game_pins": [],
                    "wins": 0,
                },
                "away": {
                    "name": in_pool[1],
                    "result": "W",
                    "pins": 0,
                    "avg": 0,
                    "game_pins": [],
                    "wins": 0,
                },
                "_bye_pair": True,
            }

    return slots

def _qf_results_for_bracket_placement(
    qf_matchups: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
) -> List[Optional[SlotWL]]:
    """Use true bracket-slot QF order when all four games match theory; else theory-then-sheet order."""
    slots = qf_matchups_in_bracket_slot_order(qf_matchups, round_pairs)
    if len(slots) >= 4 and all(slots):
        wl = [_slot_wl_from_matchup(s) for s in slots[:4]]
        if all(wl):
            return wl
    qf_ord, _ = _match_matchups_to_theoretical_round(qf_matchups, round_pairs)
    return qf_slot_results_in_order(qf_ord)

def _qf_res_candidates(
    qf_matchups: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
) -> List[List[Optional[SlotWL]]]:
    """Distinct 4-slot QF outcomes (W/L per bracket slot) to try for crossover vs parallel fit."""
    acc: List[List[Optional[SlotWL]]] = []
    seen: Set[Tuple[Optional[SlotWL], ...]] = set()

    def push(seq: List[Optional[SlotWL]]) -> None:
        if len(seq) < 4:
            return
        s4 = seq[:4]
        if not all(s4):
            return
        key = tuple(s4)
        if key in seen:
            return
        seen.add(key)
        acc.append(list(s4))

    push(_qf_results_for_bracket_placement(qf_matchups, round_pairs))
    slot_wl = [
        _slot_wl_from_matchup(s)
        for s in qf_matchups_in_bracket_slot_order(qf_matchups, round_pairs)
    ]
    if len(slot_wl) >= 4 and all(slot_wl):
        push(slot_wl[:4])
    sheet_full = qf_slot_results_in_order(qf_matchups)
    if len(sheet_full) >= 4:
        s4 = sheet_full[:4]
        for k in range(4):
            push(s4[k:] + s4[:k])
    row_wl: List[Optional[SlotWL]] = []
    for m in qf_matchups[:4]:
        row_wl.append(winner_loser_from_matchup(m))
    if len(row_wl) == 4 and all(row_wl):
        for perm in itertools.permutations((0, 1, 2, 3)):
            push([row_wl[perm[i]] for i in range(4)])
    return acc

def _qf_winner_loser_sets(qf_ms: List[dict]) -> Tuple[Set[str], Set[str]]:
    """QF winners and losers from the first four decided games."""
    w: Set[str] = set()
    l: Set[str] = set()
    for m in qf_ms[:4]:
        wl = winner_loser_from_matchup(m)
        if wl:
            w.add(wl[0])
            l.add(wl[1])
    return w, l

def _split_semis_by_playoff_loss_band(
    snapshots: List[Optional[dict]],
    ms1: List[dict],
    *,
    losses_before_col: int = 1,
) -> Tuple[List[dict], List[dict], List[dict]]:
    """Winners-bracket semis = both teams with 0 playoff losses; losers-bracket = both with 1+."""
    losses = _playoff_losses_through_prior_rounds(snapshots, losses_before_col)
    wb: List[dict] = []
    lb: List[dict] = []
    other: List[dict] = []
    for m in _playoff_matchups_with_opponent(ms1):
        away = m.get("away")
        if not away:
            continue
        h, a = m["home"]["name"], away["name"]
        lh, la = losses.get(h, 0), losses.get(a, 0)
        if lh == 0 and la == 0:
            wb.append(m)
        elif lh >= 1 and la >= 1:
            lb.append(m)
        else:
            other.append(m)
    return wb, lb, other

def _parallel_model_from_loss_band(
    snapshots: List[Optional[dict]],
    ms1: List[dict],
    ms2: List[dict],
    qf_ms: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
) -> Optional[dict]:
    """Sheet-style parallel semis: QF winners play winners, QF losers play losers."""
    wb_ms, lb_ms, other = _split_semis_by_playoff_loss_band(snapshots, ms1)
    if len(wb_ms) != 2 or len(lb_ms) != 2:
        return None
    wb_semis = [winner_loser_from_matchup(m) for m in wb_ms]
    lb_semis = [winner_loser_from_matchup(m) for m in lb_ms]
    if not all(wb_semis) or not all(lb_semis):
        return None
    w3_groups = expected_week3_groups(wb_semis[:2], lb_semis[:2])
    ms2_played = _playoff_matchups_with_opponent(ms2)
    sheet_qf = qf_slot_results_in_order(_playoff_matchups_with_opponent(qf_ms))
    if len(sheet_qf) >= 4 and all(sheet_qf):
        qf_res = sheet_qf[:4]
    else:
        qf_res = _qf_results_for_bracket_placement(qf_ms, round_pairs)
    return {
        "kind": "parallel",
        "qf_res": list(qf_res[:4]) if qf_res else [],
        "wb_ord": wb_ms,
        "lb_ord": lb_ms,
        "rest": other,
        "w3_groups": w3_groups,
        "w3_hits": _week3_match_count(ms2_played, w3_groups),
    }

def _semis_week_parallel_shape(
    qf_ms: List[dict],
    ms1: List[dict],
    *,
    snapshots: Optional[List[Optional[dict]]] = None,
) -> bool:
    """True if semis has two unbeaten-vs-unbeaten games and two one-loss-vs-one-loss games."""
    if snapshots is not None:
        wb, lb, other = _split_semis_by_playoff_loss_band(snapshots, ms1)
        if len(wb) == 2 and len(lb) == 2 and not other:
            return True
    W, L = _qf_winner_loser_sets(qf_ms)
    if len(W) != 4 or len(L) != 4:
        return False
    ww = ll = 0
    for m in ms1:
        away = m.get("away")
        if not away:
            continue
        a, b = m["home"]["name"], away["name"]
        if a in W and b in W:
            ww += 1
        elif a in L and b in L:
            ll += 1
    return ww == 2 and ll == 2

def _backfill_cross_ord(
    cross_ord: List[Optional[dict]],
    cross_sets: List[Optional[FrozenSet[str]]],
    rest: List[dict],
) -> Tuple[List[Optional[dict]], List[dict]]:
    filled: List[Optional[dict]] = list(cross_ord)
    pool = list(rest)
    for i in range(min(4, len(filled))):
        if filled[i] is not None:
            continue
        teams = cross_sets[i] if i < len(cross_sets) else None
        pick_idx: Optional[int] = None
        if teams:
            for strict in (True, False):
                for j, m in enumerate(pool):
                    away = m.get("away")
                    if not away:
                        continue
                    if sheet_matchup_matches_expected_pair(m, teams, strict=strict):
                        pick_idx = j
                        break
                if pick_idx is not None:
                    break
        if pick_idx is None and pool:
            pick_idx = 0
        if pick_idx is not None:
            filled[i] = pool.pop(pick_idx)
    return filled, pool

def _backfill_parallel_sl(
    slots: List[Optional[dict]],
    groups: List[FrozenSet[str]],
    pool: List[dict],
) -> Tuple[List[Optional[dict]], List[dict]]:
    out: List[Optional[dict]] = []
    p = list(pool)
    for i, m in enumerate(slots):
        if m is not None:
            out.append(m)
            continue
        g = groups[i] if i < len(groups) else frozenset()
        pick_idx: Optional[int] = None
        if g:
            for strict in (True, False):
                for j, cand in enumerate(p):
                    away = cand.get("away")
                    if not away:
                        continue
                    if sheet_matchup_matches_expected_pair(cand, g, strict=strict):
                        pick_idx = j
                        break
                if pick_idx is not None:
                    break
        if pick_idx is None and p:
            pick_idx = 0
        if pick_idx is not None:
            out.append(p.pop(pick_idx))
        else:
            out.append(None)
    return out, p

def _week3_match_count(ms2: List[dict], w3_groups: List[Tuple[FrozenSet[str], str]]) -> int:
    if not ms2 or not w3_groups:
        return 0
    ord3, _ = order_matchups_by_labeled_groups(ms2, w3_groups)
    return sum(1 for _lab, mm in ord3 if mm is not None)

def _playoff_matchups_with_opponent(ms: List[dict]) -> List[dict]:
    """Sheet rows that are head-to-head (exclude lone 'advances' placeholders)."""
    return [m for m in ms if m.get("away")]

def _w3_groups_from_snapshots_parallel(
    snapshots: List[Optional[dict]],
    ms1: List[dict],
) -> List[Tuple[FrozenSet[str], str]]:
    """Finals pairings from parallel semis (0-loss vs 0-loss, 1+ vs 1+)."""
    wb_ms, lb_ms, _other = _split_semis_by_playoff_loss_band(
        snapshots, ms1, losses_before_col=1
    )
    if len(wb_ms) != 2 or len(lb_ms) != 2:
        return []
    wb_semis = [winner_loser_from_matchup(m) for m in wb_ms]
    lb_semis = [winner_loser_from_matchup(m) for m in lb_ms]
    if not all(wb_semis) or not all(lb_semis):
        return []
    return expected_week3_groups(wb_semis[:2], lb_semis[:2])

def _w3_groups_from_ms1_parallel(
    qf_ms: List[dict], ms1: List[dict]
) -> List[Tuple[FrozenSet[str], str]]:
    """Finals pairings from parallel semis (WW / LL games in week 2)."""
    w_set, l_set = _qf_winner_loser_sets(qf_ms)
    if len(w_set) != 4 or len(l_set) != 4:
        return []
    wb_semis: List[Optional[SlotWL]] = []
    lb_semis: List[Optional[SlotWL]] = []
    for m in ms1:
        wl = winner_loser_from_matchup(m)
        if not wl:
            continue
        win, lose = wl
        if win in w_set and lose in w_set:
            wb_semis.append(wl)
        elif win in l_set and lose in l_set:
            lb_semis.append(wl)
    while len(wb_semis) < 2:
        wb_semis.append(None)
    while len(lb_semis) < 2:
        lb_semis.append(None)
    if not all(wb_semis[:2]) or not all(lb_semis[:2]):
        return []
    return expected_week3_groups(wb_semis[:2], lb_semis[:2])

def _collect_w3_group_candidates(
    qf_ms: List[dict],
    ms1: List[dict],
    ms2: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
    *,
    snapshots: Optional[List[Optional[dict]]] = None,
) -> List[List[Tuple[FrozenSet[str], str]]]:
    """Every plausible finals-week pairing model to score against the sheet."""
    candidates: List[List[Tuple[FrozenSet[str], str]]] = []
    seen: Set[Tuple[Tuple[str, ...], ...]] = set()

    def add(groups: List[Tuple[FrozenSet[str], str]]) -> None:
        if not groups:
            return
        key = tuple(
            tuple(sorted(t for t in teams)) + (label,)
            for teams, label in groups
        )
        if key in seen:
            return
        seen.add(key)
        candidates.append(groups)

    if snapshots is not None:
        loss_par = _parallel_model_from_loss_band(
            snapshots, ms1, ms2, qf_ms, round_pairs
        )
        if loss_par and loss_par.get("w3_groups"):
            add(list(loss_par["w3_groups"]))

    model = _pick_best_eight_team_placement_model(
        qf_ms, ms1, ms2, round_pairs, snapshots=snapshots
    )
    if model and model.get("w3_groups"):
        add(list(model["w3_groups"]))

    for qf_res in _qf_res_candidates(qf_ms, round_pairs):
        if not all(qf_res):
            continue
        cross_sets = expected_week2_cross_sets(qf_res)
        cross_ord, _ = matchups_by_cross_ordered_groups(ms1, cross_sets)
        semis_x = [winner_loser_from_matchup(m) if m else None for m in cross_ord]
        if len(semis_x) >= 4 and all(semis_x):
            add(expected_week3_groups_cross(semis_x))
        wb_g, lb_g = expected_week2_groups(qf_res)
        wb_ord, r1 = matchups_by_ordered_groups(ms1, wb_g)
        lb_ord, _ = matchups_by_ordered_groups(r1, lb_g)
        wb_semis = [winner_loser_from_matchup(m) if m else None for m in wb_ord]
        lb_semis = [winner_loser_from_matchup(m) if m else None for m in lb_ord]
        if (
            len(wb_semis) >= 2
            and len(lb_semis) >= 2
            and all(wb_semis[:2])
            and all(lb_semis[:2])
        ):
            add(expected_week3_groups(wb_semis[:2], lb_semis[:2]))

    add(_w3_groups_from_ms1_parallel(qf_ms, ms1))
    return candidates

def _best_w3_groups(
    qf_ms: List[dict],
    ms1: List[dict],
    ms2: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
    *,
    snapshots: Optional[List[Optional[dict]]] = None,
) -> List[Tuple[FrozenSet[str], str]]:
    ms2_played = _playoff_matchups_with_opponent(ms2)
    parallel_shape = _semis_week_parallel_shape(qf_ms, ms1, snapshots=snapshots)
    best_groups: List[Tuple[FrozenSet[str], str]] = []
    best_n = -1

    if parallel_shape:
        if snapshots is not None:
            snap_par = _w3_groups_from_snapshots_parallel(snapshots, ms1)
            if snap_par and _week3_match_count(ms2_played, snap_par) >= 3:
                return snap_par
        ms1_par = _w3_groups_from_ms1_parallel(qf_ms, ms1)
        if ms1_par and _week3_match_count(ms2_played, ms1_par) >= 3:
            return ms1_par
        if snapshots is not None:
            loss_par = _parallel_model_from_loss_band(
                snapshots, ms1, ms2, qf_ms, round_pairs
            )
            if loss_par and loss_par.get("w3_groups"):
                w3g = list(loss_par["w3_groups"])
                if _week3_match_count(ms2_played, w3g) >= 2:
                    return w3g

    for groups in _collect_w3_group_candidates(
        qf_ms, ms1, ms2_played, round_pairs, snapshots=snapshots
    ):
        n = _week3_match_count(ms2_played, groups)
        if n > best_n:
            best_n = n
            best_groups = groups

    if best_groups and best_n >= 2:
        return best_groups

    if parallel_shape:
        if snapshots is not None:
            snap_par = _w3_groups_from_snapshots_parallel(snapshots, ms1)
            if snap_par:
                return snap_par
        ms1_par = _w3_groups_from_ms1_parallel(qf_ms, ms1)
        if ms1_par:
            return ms1_par

    return best_groups

def _pick_best_eight_team_placement_model(
    qf_ms: List[dict],
    ms1: List[dict],
    ms2: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
    *,
    snapshots: Optional[List[Optional[dict]]] = None,
) -> Optional[dict]:
    """Choose QF slot labeling + cross vs parallel so week-2 fits 2+2 and week-3 placement groups match the sheet."""
    if snapshots is not None:
        loss_par = _parallel_model_from_loss_band(snapshots, ms1, ms2, qf_ms, round_pairs)
        if loss_par is not None and loss_par.get("w3_hits", 0) >= 3:
            out = dict(loss_par)
            out.pop("w3_hits", None)
            return out

    candidates = _qf_res_candidates(qf_ms, round_pairs)
    if not candidates:
        return None
    ms2_played = _playoff_matchups_with_opponent(ms2)
    best: Optional[dict] = None
    best_key: Tuple[int, int, int] = (-1, -1, -1)  # (week3 matches, week2 matches, shape bonus)
    shape_parallel = _semis_week_parallel_shape(qf_ms, ms1, snapshots=snapshots)

    def maybe_take(key: Tuple[int, int, int], row: dict) -> None:
        nonlocal best, best_key
        if key > best_key:
            best_key = key
            best = row
        elif key == best_key and best is not None:
            if row["kind"] == "parallel" and best["kind"] == "cross":
                best = row
            elif row["kind"] == "cross" and best["kind"] == "parallel":
                pass
            else:
                pr = prefer_crossover_week2(ms1, row["qf_res"])
                if (pr and row["kind"] == "cross") or (not pr and row["kind"] == "parallel"):
                    best = row

    for qf_res in candidates:
        cross_sets = expected_week2_cross_sets(qf_res)
        cross_ord, rest_c = matchups_by_cross_ordered_groups(ms1, cross_sets)
        cross_f, rest_xf = _backfill_cross_ord(cross_ord, cross_sets, rest_c)
        w2x = sum(1 for x in cross_f if x is not None)
        semis_x = [winner_loser_from_matchup(m) if m else None for m in cross_f]
        w3g_x: List[Tuple[FrozenSet[str], str]] = []
        if all(semis_x):
            w3g_x = expected_week3_groups_cross(semis_x)
        w3x = _week3_match_count(ms2_played, w3g_x)
        fit_bonus = 0 if shape_parallel else 1
        maybe_take(
            (w3x, w2x, fit_bonus),
            {"kind": "cross", "qf_res": qf_res, "cross_ord": cross_f, "cross_sets": cross_sets, "rest": rest_xf, "w3_groups": w3g_x},
        )

        wb_g, lb_g = expected_week2_groups(qf_res)
        if len(wb_g) >= 2 and len(lb_g) >= 2:
            wb_ord, r1 = matchups_by_ordered_groups(ms1, wb_g)
            lb_ord, r2 = matchups_by_ordered_groups(r1, lb_g)
            wb_f, pool2 = _backfill_parallel_sl(list(wb_ord), list(wb_g), list(r2))
            lb_f, rest_pf = _backfill_parallel_sl(list(lb_ord), list(lb_g), pool2)
            w2p = sum(1 for x in wb_f + lb_f if x is not None)
            wb_semis = [winner_loser_from_matchup(m) if m else None for m in wb_f]
            lb_semis = [winner_loser_from_matchup(m) if m else None for m in lb_f]
            w3g_p: List[Tuple[FrozenSet[str], str]] = []
            if len(wb_semis) >= 2 and len(lb_semis) >= 2 and all(wb_semis) and all(lb_semis):
                w3g_p = expected_week3_groups(wb_semis[:2], lb_semis[:2])
            w3p = _week3_match_count(ms2_played, w3g_p)
            par_bonus = 1 if shape_parallel else 0
            maybe_take(
                (w3p, w2p, par_bonus),
                {
                    "kind": "parallel",
                    "qf_res": qf_res,
                    "wb_ord": wb_f,
                    "lb_ord": lb_f,
                    "rest": rest_pf,
                    "w3_groups": w3g_p,
                },
            )

    return best

def _matchup_identity(m: dict) -> Tuple[str, ...]:
    away = m.get("away")
    if not away:
        return (m["home"]["name"],)
    return tuple(sorted((m["home"]["name"], away["name"])))

def _playoff_losses_through_prior_rounds(
    snapshots: List[Optional[dict]], before_col: int
) -> Dict[str, int]:
    """Playoff losses before column `before_col` begins (sheet weeks prior only)."""
    losses: Dict[str, int] = {}
    for ri in range(before_col):
        snap = snapshots[ri] if ri < len(snapshots) else None
        if not snap or not snap.get("matchups"):
            continue
        for m in snap["matchups"]:
            away = m.get("away")
            if not away:
                continue
            home, a = m["home"], away
            hr, ar = home.get("result", ""), away.get("result", "")
            if hr == "W" and ar == "L":
                losses[a["name"]] = losses.get(a["name"], 0) + 1
            elif ar == "W" and hr == "L":
                losses[home["name"]] = losses.get(home["name"], 0) + 1
    return losses

def _matchup_seed_rank_sum(m: dict, seed_rank: Dict[str, int]) -> int:
    away = m.get("away")
    if not away:
        return 9999
    h, a = m["home"]["name"], away["name"]
    return seed_rank.get(h, 99) + seed_rank.get(a, 99)

def _resolve_two_week_parallel_playoffs(
    snapshots: List[Optional[dict]],
    seed_rank: Optional[Dict[str, int]] = None,
) -> Optional[dict]:
    """Semifinals week (parallel WB/LB) + labeled placement finals — no quarterfinals."""
    if len(snapshots) < 2:
        return None
    snap0, snap1 = snapshots[0], snapshots[1]
    if not snap0 or not snap1 or not snap0.get("matchups") or not snap1.get("matchups"):
        return None
    ms1 = _playoff_matchups_with_opponent(list(snap0["matchups"]))
    ms2 = _playoff_matchups_with_opponent(list(snap1["matchups"]))
    if len(ms1) != 4 or len(ms2) < 2:
        return None

    sr = seed_rank or {}
    best: Optional[dict] = None
    best_key: Tuple[int, int] = (-1, -9999)  # (finals hits, -wb seed sum)
    for wb_idx in itertools.combinations(range(4), 2):
        lb_idx = [i for i in range(4) if i not in wb_idx]
        wb_ms = [ms1[i] for i in wb_idx]
        lb_ms = [ms1[i] for i in lb_idx]
        wb_semis = [winner_loser_from_matchup(m) for m in wb_ms]
        lb_semis = [winner_loser_from_matchup(m) for m in lb_ms]
        if not all(wb_semis) or not all(lb_semis):
            continue
        w3g = expected_week3_groups(wb_semis[:2], lb_semis[:2])
        hits = _week3_match_count(ms2, w3g)
        wb_seed_sum = sum(_matchup_seed_rank_sum(m, sr) for m in wb_ms)
        key = (hits, -wb_seed_sum)
        if key > best_key:
            best_key = key
            used = {_matchup_identity(m) for m in wb_ms + lb_ms}
            rest = [m for m in ms1 if _matchup_identity(m) not in used]
            best = {
                "wb_ord": wb_ms,
                "lb_ord": lb_ms,
                "w3_groups": w3g,
                "rest": rest,
                "hits": hits,
            }
    if best is None or best["hits"] < 2:
        return None
    return best
