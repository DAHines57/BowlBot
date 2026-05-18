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
    champion_from_playoff_snapshots,
    build_top_games_html,
    compute_bracket_rounds,
    inject_web_chrome,
)
from league_data import LeagueDataSource
from stats.compute import sort_teams_for_playoff_seeding
from utils import safe_float, safe_int


class LeagueService:
    def __init__(self, data: LeagueDataSource):
        self.data = data

    def _normalize(self, text: str) -> str:
        return text.lower().replace("\u2018", "'").replace("\u2019", "'")

    def resolve_season(self, raw: Optional[str]) -> str:
        if raw is None or str(raw).strip() == "":
            return self.data.get_current_season()
        s = str(raw).strip()
        low = s.lower()
        if low in ("all", "all-time", "alltime"):
            return "all"
        if low == "last":
            seasons = sorted(
                [x for x in self.data.get_seasons() if x.startswith("Season")],
                key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 0,
            )
            if len(seasons) >= 2:
                return seasons[-2]
            if seasons:
                return seasons[-1]
            return self.data.get_current_season()
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
            [s for s in self.data.get_seasons() if s.startswith("Season")],
            key=num,
            reverse=True,
        )

    def lookup_catalog(self) -> dict:
        """Player/team names per season for home-page lookup dropdowns."""
        players_by_season: dict = {}
        teams_by_season: dict = {}
        for season in self.seasons_sorted():
            pdata = self.data.get_player_scores(None, season)
            if isinstance(pdata, dict) and "error" not in pdata:
                players_by_season[season] = sorted(pdata.keys(), key=str.lower)
            tdata = self.data.get_team_scores(None, season)
            if isinstance(tdata, dict) and "error" not in tdata:
                teams_by_season[season] = sorted(tdata.keys(), key=str.lower)
        stats = self.data.get_all_time_stats()
        all_players = sorted(
            (
                p["player"]
                for p in stats.get("player_averages", [])
                if p.get("player")
            ),
            key=str.lower,
        )
        return {
            "players_by_season": players_by_season,
            "teams_by_season": teams_by_season,
            "all_players": all_players,
        }

    def refresh_data(self) -> Tuple[bool, str]:
        """Reload in-memory facts and team colors from PostgreSQL (no Excel)."""
        try:
            self.data.reload_workbook()
            from db.team_colors import refresh_team_colors_cache

            refresh_team_colors_cache()
            return True, "Refreshed league data from database."
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
            season = self.data.get_current_season()
        if week == "all":
            weeks_list = self.data.list_weeks_for_season(season)
            if not weeks_list:
                return None, "No weeks in this season."
            datas = []
            for wk in weeks_list:
                data = self.data.get_week_summary(wk, season)
                if "error" not in data and data.get("players"):
                    datas.append(data)
            if not datas:
                return None, "No weekly data for this season."
            return inject_web_chrome(build_all_weeks_summary_html(season, datas), embed=embed), ""

        wk = week if week is not None else self.data.get_latest_week(season if season != "all" else None)
        data = self.data.get_week_summary(wk, season)
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
            season = self.data.get_current_season()
        if week == "all":
            weeks_list = self.data.list_weeks_for_season(season)
            if not weeks_list:
                return None, "No weeks in this season."
            datas = []
            for wk in weeks_list:
                data = self.data.get_week_matchups(wk, season)
                if "error" not in data and data.get("matchups"):
                    datas.append(data)
            if not datas:
                return None, "No matchups for this season."
            return inject_web_chrome(build_all_weeks_matchups_html(season, datas), embed=embed), ""

        wk = week if week is not None else self.data.get_latest_week(season)
        data = self.data.get_week_matchups(wk, season)
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
        weeks = self.data.list_weeks_for_season(season)
        if not weeks:
            return None, "No weeks in this season."
        pweeks = self.data.list_playoff_weeks_for_season(season)
        if pweeks:
            first = min(pweeks)
            sw = max(1, first - 1)
            if sw not in weeks:
                before = [w for w in weeks if w < first]
                sw = max(before) if before else min(weeks)

        else:
            if 7 in weeks:
                sw = 7
            else:
                sw = max(weeks)
        data = self.data.get_team_scores(None, season, through_week=sw)
        if isinstance(data, dict) and "error" in data:
            return None, data["error"]
        if not data:
            return None, "No team data for seeding."
        sorted_teams = sort_teams_for_playoff_seeding(data)
        if len(sorted_teams) < 2:
            return None, "Need at least two teams for a bracket."
        seeded_names = [name for name, _ in sorted_teams]
        rounds = compute_bracket_rounds(seeded_names)
        pweeks_sorted, playoff_snapshots = self._playoff_snapshots_for_season(season)
        playoff_h2h = sum(
            sum(1 for m in (snap or {}).get("matchups", []) if m.get("away"))
            for snap in playoff_snapshots
            if snap
        )
        if pweeks_sorted and playoff_h2h == 0:
            return None, "No playoff matchups for this season."
        html = build_playoff_bracket_html(
            season,
            sw,
            sorted_teams,
            rounds,
            playoff_week_numbers=pweeks_sorted if pweeks_sorted else None,
            playoff_matchups_by_round=playoff_snapshots if pweeks_sorted else None,
        )
        return inject_web_chrome(html, embed=embed), ""

    def playoff_bracket_index_page(self, *, embed: bool = False) -> Tuple[Optional[str], str]:
        seasons = self.seasons_sorted()
        if not seasons:
            return None, "No seasons in spreadsheet."
        return inject_web_chrome(build_bracket_index_html(seasons, embed=embed), embed=embed), ""

    def players_page(self, season: str, *, embed: bool = False) -> Tuple[Optional[str], str]:
        if season == "all":
            stats = self.data.get_all_time_stats()
            pdata = {
                p["player"]: {
                    "team": p.get("team", ""),
                    "average": p.get("average", 0),
                    "highest_game": p.get("highest_game", 0),
                    "lowest_game": p.get("lowest_game", 0),
                    "weeks_played": p.get("games", 0),
                    "weeks_absent": p.get("absences", 0),
                    "std_dev": p.get("std_dev", 0),
                }
                for p in stats.get("player_averages", [])
            }
            subtitle = "All Time"
        else:
            pdata = self.data.get_player_scores(None, season)
            if isinstance(pdata, dict) and "error" in pdata:
                return None, pdata["error"]
            subtitle = season
        if not pdata:
            return None, "No players found."
        par_map = self.data.get_player_par(
            "all" if season == "all" else subtitle
        )
        for name, stats in pdata.items():
            stats["par"] = par_map.get(name, 0)
        if season == "all":
            summary = self.data.get_league_game_stats(all_time=True)
        else:
            summary = self.data.get_league_game_stats(season)
        return (
            inject_web_chrome(
                build_players_html(pdata, subtitle, summary=summary), embed=embed
            ),
            "",
        )

    def _playoff_snapshots_for_season(
        self, season: str
    ) -> Tuple[List[int], List[Optional[dict]]]:
        pweeks = self.data.list_playoff_weeks_for_season(season)
        pweeks_sorted = sorted(pweeks)
        snapshots: List[Optional[dict]] = []
        for pw in pweeks_sorted:
            md = self.data.get_week_matchups(pw, season)
            if isinstance(md, dict) and "error" not in md and md.get("matchups"):
                snapshots.append(md)
            else:
                snapshots.append(None)
        return pweeks_sorted, snapshots

    def teams_page(self, season: str, *, embed: bool = False) -> Tuple[Optional[str], str]:
        if season == "all":
            return None, "Pick a specific season for team standings."
        data = self.data.get_team_scores(None, season)
        if isinstance(data, dict) and "error" in data:
            return None, data["error"]
        if not data:
            return None, "No team data."
        _, snapshots = self._playoff_snapshots_for_season(season)
        champion = champion_from_playoff_snapshots(snapshots)
        return inject_web_chrome(
            build_teams_html(data, season, champion_team=champion), embed=embed
        ), ""

    def leaders_page(self, season: str, *, embed: bool = False) -> Tuple[Optional[str], str]:
        if season == "all":
            blob = self.data.get_all_time_stats()
        else:
            blob = self.data.get_league_stats(season)
        if "error" in blob:
            return None, blob["error"]
        return inject_web_chrome(build_leaders_html(blob), embed=embed), ""

    def team_weekly_page(self, team_name: str, season: str, *, embed: bool = False) -> Tuple[Optional[str], str]:
        if season == "all":
            season = self.data.get_current_season()
        data = self.data.get_team_weekly_summary(team_name, season)
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
                season = self.data.get_current_season()
            wdat = self.data.get_week_summary(week, season)
            if "error" in wdat:
                return None, wdat["error"]
            active = [p for p in wdat.get("players", []) if not p.get("absent")]
            active = (active[-n:] if worst else active[:n])
            player_data = {
                p["name"]: {
                    "team": p.get("team", ""),
                    "average": p.get("avg", 0),
                    "highest_game": p.get("high", 0),
                    "lowest_game": p.get("low", min(p.get("games", [0]) or [0])),
                    "weeks_played": 1,
                }
                for p in active
            }
            label = f"{'Bottom' if worst else 'Top'} {n} — Week {week} ({season})"
        elif season == "all":
            stats = self.data.get_all_time_stats()
            avgs = stats.get("player_averages", [])
            avgs = avgs[-n:] if worst else avgs[:n]
            player_data = {
                p["player"]: {
                    "team": p.get("team", ""),
                    "average": p.get("average", 0),
                    "highest_game": p.get("highest_game", 0),
                    "lowest_game": p.get("lowest_game", 0),
                    "weeks_played": p.get("games", 0),
                    "weeks_absent": p.get("absences", 0),
                    "std_dev": p.get("std_dev", 0),
                }
                for p in avgs
            }
            label = f"{'Bottom' if worst else 'Top'} {n} — All Time"
        else:
            raw = self.data.get_player_scores(None, season)
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
            stats = self.data.get_all_time_stats()
        else:
            stats = self.data.get_league_stats(season)
        if "error" in stats:
            return None, stats["error"]
        games = list(stats.get("top_games", []))
        if worst:
            games = list(reversed(games))
        subtitle = stats.get("season", season)
        return inject_web_chrome(build_top_games_html(games, subtitle, n), embed=embed), ""

    def find_player_names(self, search: str, season: str) -> List[str]:
        return self.data.find_player_names(search, season if season != "all" else None)

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
            stats = self.data.get_all_time_stats()
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
            game_history = self.data.get_player_game_history(name, season=None, limit=30)
            league_summary = self.data.get_league_game_stats(all_time=True)
            return {
                "page_title": name,
                "subtitle": f"{name} · All Time",
                "team": team,
                "stats_title": "Career stats",
                "stat_rows": stat_rows,
                "empty_message": None,
                "game_history": game_history,
                "chart_scope": "all time",
                "league_avg": league_summary.get("league_avg"),
            }, ""

        if season != "all":
            matches = self.data.find_player_names(player_name, season)
            if len(matches) > 1:
                return None, "AMBIGUOUS"
            if len(matches) == 1:
                player_name = matches[0]

        data = self.data.get_player_scores(player_name, season)
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
        game_history = self.data.get_player_game_history(player, season, limit=30)
        league_summary = self.data.get_league_game_stats(season)
        return {
            "page_title": player,
            "subtitle": subtitle,
            "team": team,
            "stats_title": "Season stats",
            "stat_rows": stat_rows,
            "empty_message": empty_message,
            "game_history": game_history,
            "chart_scope": scope or season,
            "league_avg": league_summary.get("league_avg"),
        }, ""
