"""Aggregate league stats from player-week fact rows."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from stats.facts import (
    filter_facts,
    games_list,
    games_slots,
    name_matches_team,
    resolve_opponent_on_roster,
    normalize,
)
from placement_bracket import winner_loser_from_matchup
from stats.matchup_overrides import find_matchup_override, sides_from_overrides
from utils import safe_float, safe_int


def playoff_seeding_sort_key(stats: dict) -> Tuple[int, int, int, float]:
    """Best-first sort key: wins, then total pins when record is tied, then avg."""
    return (
        stats.get("wins", 0),
        stats.get("pins_for", 0),
        -stats.get("losses", 0),
        stats.get("avg_per_game", 0),
    )


def sort_teams_for_playoff_seeding(
    team_scores: Dict[str, dict],
) -> List[Tuple[str, dict]]:
    """Return (team_name, stats) pairs best seed first."""
    return sorted(
        team_scores.items(),
        key=lambda item: playoff_seeding_sort_key(item[1]),
        reverse=True,
    )


def parse_season_number(season: Optional[str]) -> Optional[int]:
    if season is None:
        return None
    s = str(season).strip()
    if not s:
        return None
    if s.lower().startswith("season"):
        try:
            return int(s.split()[-1])
        except (ValueError, IndexError):
            return None
    if s.isdigit():
        return int(s)
    try:
        return int(s.split()[-1])
    except (ValueError, IndexError):
        return None


def season_label(season_num: int) -> str:
    return f"Season {season_num}"


def seasons_from_facts(facts: List[dict]) -> List[str]:
    from db.excluded_seasons import is_season_excluded

    by_num: Dict[int, str] = {}
    for f in facts:
        n = f.get("season_number")
        if n is None or is_season_excluded(int(n)):
            continue
        by_num[int(n)] = f.get("season_label") or season_label(int(n))
    return [by_num[k] for k in sorted(by_num)]


def current_season_label(facts: List[dict]) -> Optional[str]:
    seasons = seasons_from_facts(facts)
    return seasons[-1] if seasons else None


def _find_opponent_team(
    opponent_name: str,
    team_names: List[str],
    *,
    season_num: Optional[int] = None,
) -> Optional[str]:
    return resolve_opponent_on_roster(
        opponent_name, team_names, season_num=season_num
    )


def _team_game_totals_by_week(
    rows: List[dict],
) -> Dict[str, Dict[int, Dict[int, float]]]:
    """team -> week -> game_num (1-5) -> pins."""
    out: Dict[str, Dict[int, Dict[int, float]]] = {}
    for f in rows:
        if f.get("substitute"):
            continue
        team = str(f.get("team") or "").strip()
        if not team:
            continue
        week = safe_int(f.get("week"), 0)
        if week <= 0:
            continue
        if team not in out:
            out[team] = {}
        if week not in out[team]:
            out[team][week] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for i, g in enumerate(games_list(f), start=1):
            if i <= 5:
                out[team][week][i] = out[team][week].get(i, 0) + g
    return out


def _resolve_matchup_opponent_team(
    opponent_name: Optional[str],
    team_names: List[str],
    *,
    season_num: int,
    override_row: Optional[dict],
) -> Optional[str]:
    if opponent_name:
        found = _find_opponent_team(
            str(opponent_name).strip(), team_names, season_num=season_num
        )
        if found:
            return found
    if override_row:
        hint = str(override_row.get("opponent") or "").strip()
        if hint:
            return _find_opponent_team(hint, team_names, season_num=season_num)
    return None


def _week_wlt_and_pins_against(
    team: str,
    week_num: int,
    opponent_name: Optional[str],
    team_names: List[str],
    season_num: int,
    game_index: Dict[str, Dict[int, Dict[int, float]]],
    team_weekly_game_totals: Dict[int, Dict[int, float]],
    matchup_overrides: Optional[List[dict]],
) -> Tuple[int, int, int, bool, int, Optional[str]]:
    """Wins, losses, ties, record_overridden, pins_against, resolved opponent team."""
    o_row = find_matchup_override(
        matchup_overrides, season_num=season_num, week=week_num, team=team
    )
    opp_team = _resolve_matchup_opponent_team(
        opponent_name, team_names, season_num=season_num, override_row=o_row
    )
    o_opp = None
    if opp_team:
        o_opp = find_matchup_override(
            matchup_overrides, season_num=season_num, week=week_num, team=opp_team
        )

    pins_against = 0
    team_games = team_weekly_game_totals.get(
        week_num, {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    )
    if opp_team:
        opp_games = game_index.get(opp_team, {}).get(
            week_num, {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        )
        for game_num in range(1, 6):
            team_total = team_games.get(game_num, 0)
            opp_total = opp_games.get(game_num, 0)
            if team_total > 0 or opp_total > 0:
                pins_against += opp_total

    if o_row is not None or o_opp is not None:
        wk_w, wk_l, wk_t, _, _, _, _, _ = sides_from_overrides(
            team, opp_team or opponent_name or "", o_row, o_opp
        )
        return wk_w, wk_l, wk_t, True, pins_against, opp_team

    if not opp_team:
        return 0, 0, 0, False, 0, None

    opp_games = game_index.get(opp_team, {}).get(
        week_num, {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    )
    wk_w = wk_l = wk_t = 0
    for game_num in range(1, 6):
        team_total = team_games.get(game_num, 0)
        opp_total = opp_games.get(game_num, 0)
        if team_total > 0 or opp_total > 0:
            if team_total > opp_total:
                wk_w += 1
            elif team_total < opp_total:
                wk_l += 1
            else:
                wk_t += 1
    return wk_w, wk_l, wk_t, False, pins_against, opp_team


def get_team_scores(
    facts: List[dict],
    team_name: Optional[str] = None,
    season: Optional[str] = None,
    week: Optional[int] = None,
    through_week: Optional[int] = None,
    *,
    season_num: Optional[int] = None,
    matchup_overrides: Optional[List[dict]] = None,
) -> Dict:
    week_param = week
    through_param = through_week
    if week_param is not None and through_param is not None:
        return {"error": "Use either week or through_week, not both."}

    if season_num is None:
        season_num = parse_season_number(season)
    if season_num is None:
        return {"error": f"Season '{season}' not found"}

    season_rows = filter_facts(facts, season_num=season_num)
    if not season_rows:
        return {"error": f"Season '{season}' not found"}

    if week_param is not None:
        rows = filter_facts(season_rows, week=week_param)
    elif through_param is not None:
        rows = filter_facts(
            season_rows, through_week=through_param, exclude_playoffs=True
        )
    else:
        rows = season_rows

    team_data: Dict[str, dict] = {}
    for f in rows:
        team = str(f.get("team") or "").strip()
        if not team:
            continue
        is_sub = bool(f.get("substitute"))
        is_absent = bool(f.get("absent"))
        games = games_list(f)
        week_total = sum(games)
        player = str(f.get("player_display_name") or "").strip()

        if team not in team_data:
            team_data[team] = {"players": {}, "weekly_totals": {}}

        if not is_sub and not is_absent and player:
            if player not in team_data[team]["players"]:
                team_data[team]["players"][player] = {"games": []}
            team_data[team]["players"][player]["games"].extend(games)

        if not is_sub:
            wk = safe_int(f.get("week"), 0)
            if wk > 0:
                wt = team_data[team]["weekly_totals"]
                if wk not in wt:
                    opp = f.get("opponent")
                    wt[wk] = {
                        "pins": 0,
                        "opponent": str(opp).strip() if opp else None,
                    }
                wt[wk]["pins"] += week_total

    game_index = _team_game_totals_by_week(rows)
    team_names = list(team_data.keys())
    playoff_weeks: set[int] = set()
    for f in season_rows:
        if f.get("playoffs"):
            w = safe_int(f.get("week"), 0)
            if w > 0:
                playoff_weeks.add(w)
    if matchup_overrides:
        for row in matchup_overrides:
            if int(row.get("season_number", 0)) != season_num:
                continue
            if row.get("playoffs"):
                w = safe_int(row.get("week"), 0)
                if w > 0:
                    playoff_weeks.add(w)
    results: Dict = {}

    for team, data in team_data.items():
        player_averages = []
        for _player, player_data in data["players"].items():
            g = player_data["games"]
            if g:
                player_averages.append(sum(g) / len(g))
        avg_per_game = (
            sum(player_averages) / len(player_averages) if player_averages else 0
        )

        total_pins = sum(wd["pins"] for wd in data["weekly_totals"].values())

        wins = losses = ties = pins_against = 0
        record_overridden = False
        record_override_mark = False
        team_weekly_game_totals = game_index.get(team, {})

        for week_num, week_data in data["weekly_totals"].items():
            wk_w, wk_l, wk_t, wk_ov, pa, _opp = _week_wlt_and_pins_against(
                team,
                week_num,
                week_data.get("opponent"),
                team_names,
                season_num,
                game_index,
                team_weekly_game_totals,
                matchup_overrides,
            )
            if not (wk_w or wk_l or wk_t or wk_ov):
                continue
            wins += wk_w
            losses += wk_l
            ties += wk_t
            pins_against += pa
            if wk_ov:
                record_overridden = True
                if week_num not in playoff_weeks:
                    pin_w, pin_l, pin_t, _, _, _ = _week_wlt_and_pins_against(
                        team,
                        week_num,
                        week_data.get("opponent"),
                        team_names,
                        season_num,
                        game_index,
                        team_weekly_game_totals,
                        None,
                    )
                    if (wk_w, wk_l, wk_t) != (pin_w, pin_l, pin_t):
                        record_override_mark = True

        player_averages_dict = {}
        for player, player_data in data["players"].items():
            g = player_data["games"]
            if g:
                player_averages_dict[player] = round(sum(g) / len(g), 2)

        team_result = {
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "pins_for": int(total_pins),
            "pins_against": int(pins_against),
            "avg_per_game": round(avg_per_game, 2),
            "players": player_averages_dict,
            "record_overridden": record_overridden,
            "record_override_mark": record_override_mark,
        }

        if week_param is not None and team_name:
            if name_matches_team(team_name, team):
                week_info = data["weekly_totals"].get(week_param)
                if week_info:
                    players_games: Dict[str, List[float]] = {}
                    week_total = 0
                    twgt = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                    for f in filter_facts(
                        rows, team=team, week=week_param
                    ):
                        if f.get("substitute"):
                            continue
                        player = str(f.get("player_display_name") or "Unknown")
                        games = games_list(f)
                        if games:
                            players_games[player] = games
                            week_total += sum(games)
                            for game_num in range(1, min(len(games) + 1, 6)):
                                twgt[game_num] += games[game_num - 1]

                    opponent_name = week_info.get("opponent", "Unknown")
                    week_wins = week_losses = week_ties = 0
                    week_record_overridden = False
                    if opponent_name and opponent_name != "Unknown":
                        opp_team_found = _find_opponent_team(
                            opponent_name, team_names, season_num=season_num
                        )
                        if opp_team_found:
                            o_row = find_matchup_override(
                                matchup_overrides,
                                season_num=season_num,
                                week=week_param,
                                team=team,
                            )
                            o_opp = find_matchup_override(
                                matchup_overrides,
                                season_num=season_num,
                                week=week_param,
                                team=opp_team_found,
                            )
                            if o_row is not None or o_opp is not None:
                                week_record_overridden = True
                                week_wins, week_losses, week_ties, _, _, _, _, _ = (
                                    sides_from_overrides(
                                        team, opp_team_found, o_row, o_opp
                                    )
                                )
                            else:
                                opp_games = game_index.get(opp_team_found, {}).get(
                                    week_param, {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                                )
                                for game_num in range(1, 6):
                                    team_total = twgt.get(game_num, 0)
                                    opp_total = opp_games.get(game_num, 0)
                                    if team_total > 0 or opp_total > 0:
                                        if team_total > opp_total:
                                            week_wins += 1
                                        elif team_total < opp_total:
                                            week_losses += 1
                                        else:
                                            week_ties += 1

                    return {
                        "team": team,
                        "week_data": {
                            "opponent": opponent_name,
                            "players": players_games,
                            "total": week_total,
                            "wins": week_wins,
                            "losses": week_losses,
                            "ties": week_ties,
                            "record_overridden": week_record_overridden,
                        },
                    }
                return {
                    "error": f"No data found for {team} in Week {week_param}"
                }

        if team_name is None:
            results[team] = team_result
        elif name_matches_team(team_name, team):
            return {"team": team, **team_result}

    if team_name:
        if week_param is not None:
            return {
                "error": f"Team '{team_name}' not found in Week {week_param} of {season}"
            }
        return {"error": f"Team '{team_name}' not found in {season}"}

    return results


def get_team_weekly_summary(
    facts: List[dict],
    team_name: str,
    season: Optional[str] = None,
    *,
    season_num: Optional[int] = None,
    matchup_overrides: Optional[List[dict]] = None,
) -> Dict:
    if season_num is None:
        season_num = parse_season_number(season)
    if season_num is None:
        return {"error": f"Season '{season}' not found"}

    season_rows = filter_facts(facts, season_num=season_num)
    if not season_rows:
        return {"error": f"Season '{season}' not found"}

    team_found = None
    for f in season_rows:
        t = str(f.get("team") or "").strip()
        if t and name_matches_team(team_name, t):
            team_found = t
            break
    if not team_found:
        return {"error": f"Team '{team_name}' not found in {season}"}

    all_teams: Dict[str, Dict[int, Dict[int, float]]] = {}
    for f in season_rows:
        if f.get("substitute"):
            continue
        team = str(f.get("team") or "").strip()
        week = safe_int(f.get("week"), 0)
        if week <= 0:
            continue
        if team not in all_teams:
            all_teams[team] = {}
        if week not in all_teams[team]:
            all_teams[team][week] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for i, g in enumerate(games_list(f), start=1):
            if i <= 5:
                all_teams[team][week][i] += g

    weekly_data: Dict[int, dict] = {}
    for f in filter_facts(season_rows, team=team_found):
        if f.get("substitute"):
            continue
        week = safe_int(f.get("week"), 0)
        if week <= 0:
            continue
        if week not in weekly_data:
            opp = f.get("opponent")
            weekly_data[week] = {
                "opponent": str(opp).strip() if opp else "Unknown",
                "game_totals": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                "opp_game_totals": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                "wins": 0,
                "losses": 0,
                "ties": 0,
            }
        for i, g in enumerate(games_list(f), start=1):
            if i <= 5:
                weekly_data[week]["game_totals"][i] += g

    team_names = list(all_teams.keys())
    team_weekly_games = all_teams.get(team_found, {})
    for week, week_info in weekly_data.items():
        wk_w, wk_l, wk_t, wk_ov, pa, opp_team = _week_wlt_and_pins_against(
            team_found,
            week,
            week_info.get("opponent"),
            team_names,
            season_num,
            all_teams,
            team_weekly_games,
            matchup_overrides,
        )
        week_info["wins"] = wk_w
        week_info["losses"] = wk_l
        week_info["ties"] = wk_t
        week_info["record_overridden"] = wk_ov
        if opp_team and week in all_teams.get(opp_team, {}):
            week_info["opp_game_totals"] = dict(all_teams[opp_team][week])

    for week, week_info in weekly_data.items():
        team_games = week_info["game_totals"]
        team_total = sum(team_games.values())
        opp_total = sum(week_info["opp_game_totals"].values())
        total_games = 0
        for f in filter_facts(season_rows, team=team_found, week=week):
            if f.get("substitute"):
                continue
            total_games += len(games_list(f))
        week_info["avg"] = team_total / total_games if total_games > 0 else 0
        week_info["pins_for"] = int(team_total)
        week_info["pins_against"] = int(opp_total)

    return {
        "team": team_found,
        "season": season or season_label(season_num),
        "weekly_summary": weekly_data,
    }


def get_league_stats(
    facts: List[dict],
    season: Optional[str] = None,
    *,
    season_num: Optional[int] = None,
) -> Dict:
    if season_num is None:
        season_num = parse_season_number(season)
    if season_num is None:
        return {"error": f"Season '{season}' not found"}

    rows = filter_facts(facts, season_num=season_num)
    if not rows:
        return {"error": f"Season '{season}' not found"}

    player_averages: Dict[str, dict] = {}
    player_weekly_totals: List[tuple] = []
    team_weekly_totals: List[tuple] = []
    individual_games: List[tuple] = []

    for f in rows:
        if f.get("substitute"):
            continue
        team = str(f.get("team") or "").strip()
        if not team:
            continue
        is_absent = bool(f.get("absent"))
        week_games = games_list(f)
        week_total = sum(week_games)
        player = str(f.get("player_display_name") or "").strip()
        week = safe_int(f.get("week"), 0)

        for g in week_games:
            individual_games.append((player, team, week, g))

        if not is_absent and player:
            if player not in player_averages:
                player_averages[player] = {
                    "team": team,
                    "games": [],
                    "total_pins": 0,
                }
            player_averages[player]["games"].extend(week_games)
            player_averages[player]["total_pins"] += week_total
            if week_total > 0:
                player_weekly_totals.append(
                    (player, team, week, week_total, len(week_games))
                )

        if week > 0 and week_total > 0:
            team_weekly_totals.append((team, week, week_total, len(week_games)))

    player_avg_list = []
    for player, data in player_averages.items():
        games = data["games"]
        if games:
            player_avg_list.append(
                {
                    "player": player,
                    "team": data["team"],
                    "average": round(sum(games) / len(games), 2),
                    "games": len(games),
                }
            )
    player_avg_list.sort(key=lambda x: x["average"], reverse=True)
    player_weekly_totals.sort(
        key=lambda x: x[3] / x[4] if x[4] else 0, reverse=True
    )
    top_player_weeks = player_weekly_totals[:10]

    team_week_dict: Dict[tuple, List[float]] = {}
    for team, week, total, games in team_weekly_totals:
        key = (team, week)
        if key not in team_week_dict:
            team_week_dict[key] = [0, 0]
        team_week_dict[key][0] += total
        team_week_dict[key][1] += games

    team_totals_list = [
        (team, week, vals[0], vals[1])
        for (team, week), vals in team_week_dict.items()
    ]
    team_totals_list.sort(
        key=lambda x: x[2] / x[3] if x[3] else 0, reverse=True
    )
    top_team_totals = team_totals_list[:5]

    individual_games.sort(key=lambda x: x[3], reverse=True)
    top_games = individual_games[:50]

    return {
        "season": season or season_label(season_num),
        "player_averages": player_avg_list,
        "top_player_weeks": top_player_weeks,
        "top_team_totals": top_team_totals,
        "top_games": top_games,
    }


def get_all_time_stats(facts: List[dict]) -> Dict:
    all_individual_games: List[tuple] = []
    all_player_weeks: List[tuple] = []
    all_team_weeks: Dict[tuple, List[float]] = {}
    player_totals: Dict[str, dict] = {}

    by_season: Dict[int, List[dict]] = {}
    for f in facts:
        sn = f.get("season_number")
        if sn is None:
            continue
        by_season.setdefault(int(sn), []).append(f)

    for season_num in sorted(by_season.keys(), reverse=True):
        team_week_pins: Dict[tuple, List[float]] = {}
        for f in by_season[season_num]:
            if f.get("substitute"):
                continue
            team = str(f.get("team") or "").strip()
            if not team:
                continue
            week = safe_int(f.get("week"), 0)
            label = f"S{season_num} W{week}"
            is_absent = bool(f.get("absent"))
            week_games = games_list(f)
            week_total = sum(week_games)
            player = str(f.get("player_display_name") or "").strip()

            for g in week_games:
                all_individual_games.append((player, team, label, g))

            if not is_absent and player:
                if player not in player_totals:
                    player_totals[player] = {"team": team, "games": []}
                player_totals[player]["games"].extend(week_games)
                if week_total > 0:
                    all_player_weeks.append(
                        (player, team, label, week_total, len(week_games))
                    )

            if week > 0 and week_total > 0:
                key = (team, label)
                if key not in team_week_pins:
                    team_week_pins[key] = [0, 0]
                team_week_pins[key][0] += week_total
                team_week_pins[key][1] += len(week_games)

        for (team, label), vals in team_week_pins.items():
            if (team, label) not in all_team_weeks:
                all_team_weeks[(team, label)] = [0, 0]
            all_team_weeks[(team, label)][0] += vals[0]
            all_team_weeks[(team, label)][1] += vals[1]

    all_individual_games.sort(key=lambda x: x[3], reverse=True)
    all_player_weeks.sort(
        key=lambda x: x[3] / x[4] if x[4] else 0, reverse=True
    )
    team_totals = sorted(
        [(t, lbl, vals[0], vals[1]) for (t, lbl), vals in all_team_weeks.items()],
        key=lambda x: x[2] / x[3] if x[3] else 0,
        reverse=True,
    )

    def _std_dev(games: List[float]) -> float:
        if len(games) < 2:
            return 0.0
        avg = sum(games) / len(games)
        return (sum((g - avg) ** 2 for g in games) / len(games)) ** 0.5

    player_avg_list = sorted(
        [
            {
                "player": p,
                "team": d["team"],
                "average": round(sum(d["games"]) / len(d["games"]), 2),
                "std_dev": round(_std_dev(d["games"]), 2),
                "highest_game": max(d["games"]),
                "lowest_game": min(d["games"]),
                "games": len(d["games"]),
            }
            for p, d in player_totals.items()
            if d["games"]
        ],
        key=lambda x: x["average"],
        reverse=True,
    )

    return {
        "season": "All Time",
        "player_averages": player_avg_list,
        "top_player_weeks": all_player_weeks[:10],
        "top_team_totals": team_totals[:5],
        "top_games": all_individual_games[:50],
    }


def get_player_scores(
    facts: List[dict],
    player_name: Optional[str] = None,
    season: Optional[str] = None,
    week: Optional[int] = None,
    *,
    season_num: Optional[int] = None,
) -> Dict:
    if season_num is None:
        season_num = parse_season_number(season)
    if season_num is None:
        return {"error": f"Season '{season}' not found"}

    if week is not None:
        rows = filter_facts(facts, season_num=season_num, week=week)
    else:
        rows = filter_facts(facts, season_num=season_num)

    if not rows and season_num is not None:
        return {"error": f"Season '{season}' not found"}

    player_data: Dict[str, dict] = {}
    for f in rows:
        player = str(f.get("player_display_name") or "").strip()
        if not player:
            continue
        team = str(f.get("team") or "Unknown").strip()
        is_absent = bool(f.get("absent"))
        week_games = games_list(f)
        wk = safe_int(f.get("week"), 0)

        if player not in player_data:
            player_data[player] = {
                "team": team,
                "scores": [],
                "absent_count": 0,
                "weeks": [],
                "highest_game": 0,
                "lowest_game": 300,
            }

        week_avg = f.get("week_average")
        if week_avg is not None and week_avg != "":
            week_avg = safe_float(week_avg)
        elif week_games:
            week_avg = sum(week_games) / len(week_games)
        else:
            week_avg = 0

        if not is_absent:
            player_data[player]["scores"].extend(week_games)
            for game_score in week_games:
                if game_score > player_data[player]["highest_game"]:
                    player_data[player]["highest_game"] = game_score
                if game_score < player_data[player]["lowest_game"]:
                    player_data[player]["lowest_game"] = game_score
        else:
            player_data[player]["absent_count"] += 1

        player_data[player]["weeks"].append(
            {
                "week": wk,
                "games": week_games,
                "average": week_avg,
                "absent": is_absent,
            }
        )

    results: Dict = {}
    for player, data in player_data.items():
        scores = data["scores"]
        avg = sum(scores) / len(scores) if scores else 0
        std_dev = 0.0
        if scores and len(scores) > 1:
            variance = sum((x - avg) ** 2 for x in scores) / len(scores)
            std_dev = variance**0.5

        highest = data.get("highest_game", 0)
        lowest = data.get("lowest_game", 300)
        if scores:
            if highest == 0:
                highest = max(scores)
            if lowest == 300:
                lowest = min(scores)
        else:
            highest = 0
            lowest = 0

        result_data = {
            "team": data["team"],
            "scores": scores,
            "average": round(avg, 2),
            "std_dev": round(std_dev, 2),
            "weeks_played": len(data["weeks"]) - data["absent_count"],
            "weeks_absent": data["absent_count"],
            "highest_game": int(highest),
            "lowest_game": int(lowest),
        }

        if week is not None and player_name:
            if name_matches_team(player_name, player):
                week_info = next(
                    (w for w in data["weeks"] if w["week"] == week), None
                )
                if week_info:
                    return {
                        "player": player,
                        "team": data["team"],
                        "week_data": {
                            "games": week_info["games"],
                            "average": week_info["average"],
                            "absent": week_info["absent"],
                        },
                    }
                return {"error": f"No data found for {player} in Week {week}"}

        if player_name is None:
            results[player] = result_data
        elif name_matches_team(player_name, player):
            return {"player": player, **result_data}

    if player_name:
        if week is not None:
            return {
                "error": f"Player '{player_name}' not found in Week {week} of {season}"
            }
        return {"error": f"Player '{player_name}' not found in {season}"}

    return results


def get_latest_week(
    facts: List[dict],
    season: Optional[str] = None,
    *,
    season_num: Optional[int] = None,
) -> int:
    if season_num is None:
        season_num = parse_season_number(season)
    if season_num is None:
        return 1
    rows = filter_facts(facts, season_num=season_num)
    max_week = 1
    for f in rows:
        w = safe_int(f.get("week"), 0)
        if w > max_week:
            max_week = w
    return max_week


def list_weeks_for_season(
    facts: List[dict],
    season: Optional[str] = None,
    *,
    season_num: Optional[int] = None,
) -> List[int]:
    if season_num is None:
        season_num = parse_season_number(season)
    if season_num is None:
        return []
    found = set()
    for f in filter_facts(facts, season_num=season_num):
        w = safe_int(f.get("week"), 0)
        if w > 0:
            found.add(w)
    return sorted(found)


def list_playoff_weeks_for_season(
    facts: List[dict],
    season: Optional[str] = None,
    *,
    seasons: Optional[List[str]] = None,
    season_num: Optional[int] = None,
) -> List[int]:
    if season is not None:
        low = str(season).strip().lower()
        if low == "last" and seasons:
            sorted_seasons = sorted(
                [x for x in seasons if x.startswith("Season")],
                key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 0,
            )
            if len(sorted_seasons) >= 2:
                season = sorted_seasons[-2]
            elif sorted_seasons:
                season = sorted_seasons[-1]

    weeks = list_weeks_for_season(facts, season, season_num=season_num)
    if not weeks:
        return []

    if season_num is None:
        season_num = parse_season_number(season)
    if season_num is None:
        return []

    from_flag: set = set()
    for f in filter_facts(facts, season_num=season_num):
        w = safe_int(f.get("week"), 0)
        if w > 0 and f.get("playoffs"):
            from_flag.add(w)
    if from_flag:
        return sorted(from_flag)

    if len(weeks) < 2:
        return []

    counts: Dict[int, int] = {}
    for f in filter_facts(facts, season_num=season_num):
        w = safe_int(f.get("week"), 0)
        if w > 0:
            counts[w] = counts.get(w, 0) + 1

    sorted_weeks = sorted(weeks)
    peak = max(counts.get(w, 0) for w in sorted_weeks)
    if peak < 2:
        return []
    cutoff = max(4, int(peak * 0.80))
    playoff_rev: List[int] = []
    for w in reversed(sorted_weeks):
        if counts.get(w, 0) < cutoff:
            playoff_rev.append(w)
        else:
            break
    return sorted(playoff_rev)


def get_week_summary(
    facts: List[dict],
    week: int,
    season: Optional[str] = None,
    *,
    season_num: Optional[int] = None,
) -> dict:
    if season_num is None:
        season_num = parse_season_number(season)
    if season_num is None:
        return {"error": f"Season '{season}' not found"}

    rows = filter_facts(facts, season_num=season_num, week=week)
    if not rows:
        return {"error": f"Season '{season}' not found"}

    players = []
    all_scored_games: List[tuple] = []

    for f in rows:
        player = str(f.get("player_display_name") or "").strip()
        if not player:
            continue
        team = str(f.get("team") or "Unknown").strip()
        is_absent = bool(f.get("absent"))
        games = [int(g) for g in games_list(f)]

        entry = {
            "name": player,
            "team": team,
            "games": games,
            "avg": round(sum(games) / len(games), 1) if games else 0,
            "high": max(games) if games else 0,
            "absent": is_absent,
        }
        players.append(entry)
        if not is_absent:
            for g in games:
                all_scored_games.append((g, player, team))

    players.sort(key=lambda x: x["avg"], reverse=True)

    high_game = low_game = None
    if all_scored_games:
        all_scored_games.sort(key=lambda x: x[0])
        lg = all_scored_games[0]
        hg = all_scored_games[-1]
        high_game = {"score": hg[0], "player": hg[1], "team": hg[2]}
        low_game = {"score": lg[0], "player": lg[1], "team": lg[2]}

    scores_only = [g for g, _, _ in all_scored_games]
    return {
        "season": season,
        "week": week,
        "players": players,
        "high_game": high_game,
        "low_game": low_game,
        "league_avg": round(sum(scores_only) / len(scores_only), 1)
        if scores_only
        else 0,
        "total_players": len([p for p in players if not p["absent"]]),
        "games_200_plus": len([g for g in scores_only if g >= 200]),
        "total_games": len(scores_only),
    }


def get_week_matchups(
    facts: List[dict],
    week: int,
    season: Optional[str] = None,
    *,
    season_num: Optional[int] = None,
    matchup_overrides: Optional[List[dict]] = None,
) -> dict:
    if season_num is None:
        season_num = parse_season_number(season)
    if season_num is None:
        return {"error": f"Season '{season}' not found"}

    rows = filter_facts(facts, season_num=season_num, week=week)
    if not rows:
        return {"error": f"Season '{season}' not found"}

    teams: Dict[str, dict] = {}
    for f in rows:
        team = str(f.get("team") or "").strip()
        player = str(f.get("player_display_name") or "").strip()
        if not team or not player:
            continue

        is_absent = bool(f.get("absent"))
        is_sub = bool(f.get("substitute"))
        opponent = str(f.get("opponent") or "").strip()

        if team not in teams:
            teams[team] = {
                "game_pins": [],
                "player_count": 0,
                "opponent": opponent,
                "players": [],
            }

        if not is_sub:
            teams[team]["players"].append(
                {
                    "name": player,
                    "games": games_slots(f),
                    "absent": is_absent,
                }
            )
            teams[team]["player_count"] += 1
            for i, g in enumerate(games_list(f)):
                gi = int(g)
                if i >= len(teams[team]["game_pins"]):
                    teams[team]["game_pins"].append(gi)
                else:
                    teams[team]["game_pins"][i] += gi

    matched: set = set()
    matchups: List[dict] = []
    for team_name, td in teams.items():
        if team_name in matched:
            continue
        opp_name = (td.get("opponent") or "").strip()
        resolved = (
            resolve_opponent_on_roster(
                opp_name, list(teams.keys()), season_num=season_num
            )
            if opp_name
            else None
        )
        if resolved:
            opp_name = resolved
        opp = teams.get(opp_name)

        total_h = sum(td["game_pins"])
        num_games = len(td["game_pins"])
        avg_h = (
            round(total_h / (td["player_count"] * num_games), 1)
            if td["player_count"] and num_games
            else 0
        )

        if not opp_name or not opp:
            matchups.append(
                {
                    "home": {
                        "name": team_name,
                        "pins": total_h,
                        "avg": avg_h,
                        "game_pins": td["game_pins"],
                        "wins": 0,
                        "result": "—",
                    },
                    "away": None,
                }
            )
            matched.add(team_name)
            continue

        matched.add(team_name)
        matched.add(opp_name)

        total_a = sum(opp["game_pins"])
        avg_a = (
            round(total_a / (opp["player_count"] * len(opp["game_pins"])), 1)
            if opp["player_count"] and opp["game_pins"]
            else 0
        )

        h_wins = a_wins = 0
        num_games_cmp = max(len(td["game_pins"]), len(opp["game_pins"]))
        game_results = []
        for i in range(num_games_cmp):
            hp = td["game_pins"][i] if i < len(td["game_pins"]) else 0
            ap = opp["game_pins"][i] if i < len(opp["game_pins"]) else 0
            if hp > ap:
                h_wins += 1
                game_results.append(("W", "L", hp, ap))
            elif ap > hp:
                a_wins += 1
                game_results.append(("L", "W", hp, ap))
            else:
                game_results.append(("T", "T", hp, ap))

        if h_wins > a_wins:
            h_result, a_result = "W", "L"
        elif a_wins > h_wins:
            h_result, a_result = "L", "W"
        elif total_h > total_a:
            h_result, a_result = "W", "L"
        elif total_a > total_h:
            h_result, a_result = "L", "W"
        else:
            h_result = a_result = "T"

        record_overridden = False
        o_home = find_matchup_override(
            matchup_overrides,
            season_num=season_num,
            week=week,
            team=team_name,
        )
        o_away = find_matchup_override(
            matchup_overrides,
            season_num=season_num,
            week=week,
            team=opp_name,
        )
        if o_home is not None or o_away is not None:
            record_overridden = True
            (
                h_wins,
                _,
                _,
                a_wins,
                _,
                _,
                h_result,
                a_result,
            ) = sides_from_overrides(team_name, opp_name, o_home, o_away)

        if h_result == "T" and a_result == "T":
            wl = winner_loser_from_matchup(
                {
                    "home": {
                        "name": team_name,
                        "result": h_result,
                        "pins": total_h,
                        "game_pins": td["game_pins"],
                    },
                    "away": {
                        "name": opp_name,
                        "result": a_result,
                        "pins": total_a,
                        "game_pins": opp["game_pins"],
                    },
                }
            )
            if wl:
                if name_matches_team(team_name, wl[0]):
                    h_result, a_result = "W", "L"
                else:
                    h_result, a_result = "L", "W"

        matchups.append(
            {
                "home": {
                    "name": team_name,
                    "pins": total_h,
                    "avg": avg_h,
                    "game_pins": td["game_pins"],
                    "wins": h_wins,
                    "result": h_result,
                    "players": list(td.get("players", [])),
                },
                "away": {
                    "name": opp_name,
                    "pins": total_a,
                    "avg": avg_a,
                    "game_pins": opp["game_pins"],
                    "wins": a_wins,
                    "result": a_result,
                    "players": list(opp.get("players", [])),
                },
                "game_results": game_results,
                "record_overridden": record_overridden,
            }
        )

    paired_teams: set = set()
    for m in matchups:
        away = m.get("away")
        if not away:
            continue
        paired_teams.add(m["home"]["name"])
        paired_teams.add(away["name"])
    matchups = [
        m
        for m in matchups
        if m.get("away") or m["home"]["name"] not in paired_teams
    ]

    matchups.sort(key=lambda m: m["home"]["name"])
    return {"season": season, "week": week, "matchups": matchups}


def find_player_names(
    facts: List[dict],
    search: str,
    season: Optional[str] = None,
    *,
    season_num: Optional[int] = None,
) -> List[str]:
    if season_num is None:
        season_num = parse_season_number(season)
    if season_num is None:
        return []

    seen: set = set()
    matches: List[str] = []
    normalized_search = normalize(search)
    for f in filter_facts(facts, season_num=season_num):
        player = str(f.get("player_display_name") or "").strip()
        if not player or player in seen:
            continue
        seen.add(player)
        np = normalize(player)
        if normalized_search in np or np in normalized_search:
            matches.append(player)
    return matches
