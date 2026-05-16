"""
League stats + HTML views (same visual templates as the old PNG exports).
"""
from __future__ import annotations

from typing import List, Optional, Tuple, Union

from image_generator import (
    build_all_weeks_matchups_html,
    build_all_weeks_summary_html,
    build_bracket_index_html,
    build_html,
    build_leaders_html,
    build_matchups_html,
    build_player_detail_html,
    build_players_html,
    build_playoff_bracket_html,
    build_team_weekly_html,
    build_teams_html,
    build_top_games_html,
    compute_bracket_rounds,
    inject_web_chrome,
)
from sheets_handler import SheetHandler
from utils import safe_float, safe_int


class LeagueService:
    def __init__(self, sheet_handler: SheetHandler):
        self.h = sheet_handler

    def _normalize(self, text: str) -> str:
        return text.lower().replace("\u2018", "'").replace("\u2019", "'")

    def resolve_season(self, raw: Optional[str]) -> str:
        if raw is None or str(raw).strip() == "":
            return self.h._get_current_season()
        s = str(raw).strip()
        low = s.lower()
        if low in ("all", "all-time", "alltime"):
            return "all"
        if low == "last":
            seasons = sorted(
                [x for x in self.h.get_seasons() if x.startswith("Season")],
                key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 0,
            )
            if len(seasons) >= 2:
                return seasons[-2]
            if seasons:
                return seasons[-1]
            return self.h._get_current_season()
        if low.startswith("season"):
            return s
        if s.isdigit():
            return f"Season {int(s)}"
        return s

    def seasons_sorted(self) -> List[str]:
        def num(name: str) -> int:
            try:
                return int(name.split()[-1])
            except (ValueError, IndexError):
                return 0

        return sorted(
            [s for s in self.h.get_seasons() if s.startswith("Season")],
            key=num,
            reverse=True,
        )

    def reload_data(self) -> Tuple[bool, str]:
        try:
            self.h._load_workbook()
            return True, f"Reloaded ({len(self.h.get_seasons())} sheets)."
        except Exception as e:
            return False, str(e)

    def weekly_summary_page(
        self,
        season: str,
        week: Optional[Union[int, str]] = None,
        *,
        embed: bool = False,
    ) -> Tuple[Optional[str], str]:
        if season == "all":
            season = self.h._get_current_season()
        if week == "all":
            weeks_list = self.h.list_weeks_for_season(season)
            if not weeks_list:
                return None, "No weeks in this season."
            datas = []
            for wk in weeks_list:
                data = self.h.get_week_summary(wk, season)
                if "error" not in data and data.get("players"):
                    datas.append(data)
            if not datas:
                return None, "No weekly data for this season."
            return inject_web_chrome(build_all_weeks_summary_html(season, datas), embed=embed), ""

        wk = week if week is not None else self.h.get_latest_week(season if season != "all" else None)
        data = self.h.get_week_summary(wk, season)
        if "error" in data:
            return None, data["error"]
        if not data.get("players"):
            return None, f"No data for week {wk}."
        return inject_web_chrome(build_html(data), embed=embed), ""

    def weekly_results_page(
        self,
        season: str,
        week: Optional[Union[int, str]] = None,
        *,
        embed: bool = False,
    ) -> Tuple[Optional[str], str]:
        if season == "all":
            season = self.h._get_current_season()
        if week == "all":
            weeks_list = self.h.list_weeks_for_season(season)
            if not weeks_list:
                return None, "No weeks in this season."
            datas = []
            for wk in weeks_list:
                data = self.h.get_week_matchups(wk, season)
                if "error" not in data and data.get("matchups"):
                    datas.append(data)
            if not datas:
                return None, "No matchups for this season."
            return inject_web_chrome(build_all_weeks_matchups_html(season, datas), embed=embed), ""

        wk = week if week is not None else self.h.get_latest_week(season)
        data = self.h.get_week_matchups(wk, season)
        if "error" in data:
            return None, data["error"]
        if not data.get("matchups"):
            return None, f"No matchups for week {wk}."
        return inject_web_chrome(build_matchups_html(data), embed=embed), ""

    def playoff_results_page(self, season: str, *, embed: bool = False) -> Tuple[Optional[str], str]:
        """Same page as the bracket view: seeds, bracket, and stacked playoff week cards."""
        return self.playoff_bracket_page(season, embed=embed)

    def playoff_bracket_page(self, season: str, *, embed: bool = False) -> Tuple[Optional[str], str]:
        """Playoff seeds, bracket, and (when available) full playoff week scorecards on one page."""
        if season == "all":
            return None, "Pick a specific season for playoffs."
        weeks = self.h.list_weeks_for_season(season)
        if not weeks:
            return None, "No weeks in this season."
        pweeks = self.h.list_playoff_weeks_for_season(season)
        if pweeks:
            first = min(pweeks)
            sw = max(1, first - 1)
            if sw not in weeks:
                before = [w for w in weeks if w < first]
                sw = max(before) if before else min(weeks)
            note = (
                f"Seeds use cumulative regular-season stats through week {sw} "
                f"(last week before playoffs start on week {first}). "
                "Order: team average (same idea as team standings), then wins, then total pins. "
                "Each playoff week column shows real matchups when that week has scores in the sheet. "
                "When a series is split 2–2 with no Game 5 pin totals, the **Game 5 winner** column decides "
                "who advanced. "
                "When every team plays each week, matchups are grouped by what finishing spots they decide "
                "(1st, 2nd–4th, 5th–8th, etc.). For eight teams over three playoff weeks, semifinals may be "
                "winners-vs-winners and losers-vs-losers, or winner-vs-loser from adjacent quarterfinals; "
                "the bracket page picks whichever fits your sheet. See placement_bracket.py for the exact rules."
            )
        else:
            if 7 in weeks:
                sw = 7
                note = (
                    "No playoff weeks were flagged on the sheet; using week 7 as the seeding week. "
                    "Order: team average, then wins, then total pins. "
                    "Playoff columns with results appear when playoff weeks can be detected from the sheet."
                )
            else:
                sw = max(weeks)
                note = (
                    f"No playoff weeks flagged; using week {sw} (latest week in this season) for seeding. "
                    "Order: team average, then wins, then total pins. "
                    "Playoff columns with results appear when playoff weeks can be detected from the sheet."
                )
        data = self.h.get_team_scores(None, season, through_week=sw)
        if isinstance(data, dict) and "error" in data:
            return None, data["error"]
        if not data:
            return None, "No team data for seeding."
        sorted_teams = sorted(
            data.items(),
            key=lambda x: (
                x[1].get("avg_per_game", 0),
                x[1].get("wins", 0),
                x[1].get("pins_for", 0),
            ),
            reverse=True,
        )
        if len(sorted_teams) < 2:
            return None, "Need at least two teams for a bracket."
        seeded_names = [name for name, _ in sorted_teams]
        rounds = compute_bracket_rounds(seeded_names)
        pweeks_sorted = sorted(pweeks)
        playoff_snapshots: List[Optional[dict]] = []
        cards_data: List[dict] = []
        for pw in pweeks_sorted:
            md = self.h.get_week_matchups(pw, season)
            if isinstance(md, dict) and "error" not in md and md.get("matchups"):
                playoff_snapshots.append(md)
                cards_data.append(md)
            else:
                playoff_snapshots.append(None)
        html = build_playoff_bracket_html(
            season,
            sw,
            note,
            sorted_teams,
            rounds,
            playoff_week_numbers=pweeks_sorted if pweeks_sorted else None,
            playoff_matchups_by_round=playoff_snapshots if pweeks_sorted else None,
            playoff_week_cards_data=cards_data if cards_data else None,
        )
        return inject_web_chrome(html, embed=embed), ""

    def playoff_bracket_index_page(self, *, embed: bool = False) -> Tuple[Optional[str], str]:
        seasons = self.seasons_sorted()
        if not seasons:
            return None, "No seasons in spreadsheet."
        return inject_web_chrome(build_bracket_index_html(seasons), embed=embed), ""

    def players_page(self, season: str, *, embed: bool = False) -> Tuple[Optional[str], str]:
        if season == "all":
            stats = self.h.get_all_time_stats()
            pdata = {
                p["player"]: {
                    "team": p.get("team", ""),
                    "average": p.get("average", 0),
                    "highest_game": p.get("highest_game", 0),
                    "lowest_game": p.get("lowest_game", 0),
                    "weeks_played": p.get("games", 0),
                }
                for p in stats.get("player_averages", [])
            }
            subtitle = "All Time"
        else:
            pdata = self.h.get_player_scores(None, season)
            if isinstance(pdata, dict) and "error" in pdata:
                return None, pdata["error"]
            subtitle = season
        if not pdata:
            return None, "No players found."
        return inject_web_chrome(build_players_html(pdata, subtitle), embed=embed), ""

    def teams_page(self, season: str, *, embed: bool = False) -> Tuple[Optional[str], str]:
        if season == "all":
            return None, "Pick a specific season for team standings."
        data = self.h.get_team_scores(None, season)
        if isinstance(data, dict) and "error" in data:
            return None, data["error"]
        if not data:
            return None, "No team data."
        return inject_web_chrome(build_teams_html(data, season), embed=embed), ""

    def leaders_page(self, season: str, *, embed: bool = False) -> Tuple[Optional[str], str]:
        if season == "all":
            blob = self.h.get_all_time_stats()
        else:
            blob = self.h.get_league_stats(season)
        if "error" in blob:
            return None, blob["error"]
        return inject_web_chrome(build_leaders_html(blob), embed=embed), ""

    def team_weekly_page(self, team_name: str, season: str, *, embed: bool = False) -> Tuple[Optional[str], str]:
        if season == "all":
            season = self.h._get_current_season()
        data = self.h.get_team_weekly_summary(team_name, season)
        if "error" in data:
            return None, data["error"]
        team = data.get("team", team_name)
        ws = data.get("weekly_summary", {})
        if not ws:
            return None, "No weekly rows for that team."
        season_str = data.get("season", season)
        return inject_web_chrome(build_team_weekly_html(team, season_str, ws), embed=embed), ""

    def top_players_page(
        self, season: str, n: int, worst: bool, week: Optional[int] = None, *, embed: bool = False
    ) -> Tuple[Optional[str], str]:
        n = max(1, min(n, 50))
        if week is not None:
            if season == "all":
                season = self.h._get_current_season()
            wdat = self.h.get_week_summary(week, season)
            if "error" in wdat:
                return None, wdat["error"]
            active = [p for p in wdat.get("players", []) if not p.get("absent")]
            active = (active[-n:] if worst else active[:n])
            player_data = {
                p["name"]: {
                    "team": p.get("team", ""),
                    "average": p.get("avg", 0),
                    "highest_game": p.get("high", 0),
                    "lowest_game": min(p.get("games", [0]) or [0]),
                    "weeks_played": 1,
                }
                for p in active
            }
            label = f"{'Bottom' if worst else 'Top'} {n} — Week {week} ({season})"
        elif season == "all":
            stats = self.h.get_all_time_stats()
            avgs = stats.get("player_averages", [])
            avgs = avgs[-n:] if worst else avgs[:n]
            player_data = {
                p["player"]: {
                    "team": p.get("team", ""),
                    "average": p.get("average", 0),
                    "highest_game": p.get("highest_game", 0),
                    "lowest_game": p.get("lowest_game", 0),
                    "weeks_played": p.get("games", 0),
                }
                for p in avgs
            }
            label = f"{'Bottom' if worst else 'Top'} {n} — All Time"
        else:
            raw = self.h.get_player_scores(None, season)
            if isinstance(raw, dict) and "error" in raw:
                return None, raw["error"]
            sorted_players = sorted(raw.items(), key=lambda x: x[1].get("average", 0), reverse=True)
            sliced = sorted_players[-n:] if worst else sorted_players[:n]
            player_data = dict(sliced)
            label = f"{'Bottom' if worst else 'Top'} {n} — {season}"
        if not player_data:
            return None, "No player data."
        return inject_web_chrome(build_players_html(player_data, label, ascending=worst), embed=embed), ""

    def top_games_page(self, season: str, n: int, worst: bool, *, embed: bool = False) -> Tuple[Optional[str], str]:
        n = max(1, min(n, 50))
        if season == "all":
            stats = self.h.get_all_time_stats()
        else:
            stats = self.h.get_league_stats(season)
        if "error" in stats:
            return None, stats["error"]
        games = list(stats.get("top_games", []))
        if worst:
            games = list(reversed(games))
        subtitle = stats.get("season", season)
        return inject_web_chrome(build_top_games_html(games, subtitle, n), embed=embed), ""

    def find_player_names(self, search: str, season: str) -> List[str]:
        return self.h.find_player_names(search, season if season != "all" else None)

    def player_detail_page(
        self, player_name: str, season: str, *, embed: bool = False
    ) -> Tuple[Optional[str], str]:
        """Full HTML using the same list-page template as players / teams / leaders."""
        view, err = self._player_detail_view(player_name, season)
        if err:
            return None, err
        page = build_player_detail_html(**view)
        return inject_web_chrome(page, embed=embed), ""

    def _player_detail_view(self, player_name: str, season: str) -> Tuple[Optional[dict], str]:
        if season == "all" and player_name:
            stats = self.h.get_all_time_stats()
            normalized = self._normalize(player_name)
            match = next(
                (
                    p
                    for p in stats.get("player_averages", [])
                    if normalized in self._normalize(p["player"])
                    or self._normalize(p["player"]) in normalized
                ),
                None,
            )
            if not match:
                return None, f"Player {player_name!r} not found (all-time)."
            name = match["player"]
            team = match.get("team", "Unknown")
            stat_rows = [
                ("Average", f"{match.get('average', 0):.1f}", "gold"),
                ("Std dev", f"{safe_float(match.get('std_dev', 0)):.1f}", "gold"),
                ("Highest game", str(safe_int(match.get("highest_game", 0))), "green"),
                ("Lowest game", str(safe_int(match.get("lowest_game", 0))), "muted"),
                ("Games", str(safe_int(match.get("games", 0))), "muted"),
            ]
            return {
                "page_title": name,
                "subtitle": f"{name} · All Time",
                "team": team,
                "stats_title": "Career stats",
                "stat_rows": stat_rows,
                "empty_message": None,
            }, ""

        if season != "all":
            matches = self.h.find_player_names(player_name, season)
            if len(matches) > 1:
                return None, "AMBIGUOUS"
            if len(matches) == 1:
                player_name = matches[0]

        data = self.h.get_player_scores(player_name, season)
        if isinstance(data, dict) and "error" in data:
            return None, data["error"]
        if not isinstance(data, dict) or "player" not in data:
            return None, "Not found."

        player = data.get("player", player_name)
        team = data.get("team", "Unknown")
        scores = [safe_float(s) for s in data.get("scores", []) if s is not None]
        avg = safe_float(data.get("average", 0))
        if scores:
            stat_rows = [
                ("Average", f"{avg:.1f}", "gold"),
                ("Std dev", f"{safe_float(data.get('std_dev', 0)):.1f}", "gold"),
                ("Highest game", str(safe_int(data.get("highest_game", 0))), "green"),
                ("Lowest game", str(safe_int(data.get("lowest_game", 0))), "muted"),
                ("Games played", str(len(scores)), "muted"),
            ]
            empty_message = None
        else:
            stat_rows = None
            empty_message = "No scores for this scope."
        scope = season if season != "all" else ""
        subtitle = f"{player} · {scope}" if scope else player
        return {
            "page_title": player,
            "subtitle": subtitle,
            "team": team,
            "stats_title": "Season stats",
            "stat_rows": stat_rows,
            "empty_message": empty_message,
        }, ""
