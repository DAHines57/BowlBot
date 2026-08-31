"""Season/week resolution and playoff snapshots shared by the API and admin."""
from __future__ import annotations

from typing import List, Optional, Tuple

from league_data import LeagueDataSource


class LeagueService:
    def __init__(self, data: LeagueDataSource):
        self.data = data

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

    def refresh_data(self) -> Tuple[bool, str]:
        """Reload in-memory facts and team colors from PostgreSQL (no Excel)."""
        try:
            self.data.reload_workbook()
            from db.team_colors import refresh_team_colors_cache

            refresh_team_colors_cache()
            return True, "Refreshed league data from database."
        except Exception as e:
            return False, str(e)

    def playoff_snapshots_for_season(
        self, season: str
    ) -> Tuple[List[int], List[Optional[dict]]]:
        """Playoff weeks and their matchup snapshots, ``None`` for unbowled weeks."""
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
