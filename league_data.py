"""League read API — PostgreSQL only for the web app."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from db.availability import db_has_data
from db.config import get_database_url
from db.facts_loader import load_all_facts, load_all_matchup_overrides
from stats import compute


class LeagueDataSource(ABC):
    """Read-only league stats API used by LeagueService and routes."""

    @property
    @abstractmethod
    def read_source(self) -> str:
        """'database'."""

    @abstractmethod
    def reload_workbook(self) -> None:
        """Clear cached DB facts (reload after sync)."""

    @abstractmethod
    def get_seasons(self) -> List[str]:
        pass

    @abstractmethod
    def get_current_season(self) -> Optional[str]:
        pass

    @abstractmethod
    def get_team_scores(
        self,
        team_name: Optional[str] = None,
        season: Optional[str] = None,
        week: Optional[int] = None,
        through_week: Optional[int] = None,
    ) -> Dict:
        pass

    @abstractmethod
    def get_player_scores(
        self,
        player_name: Optional[str] = None,
        season: Optional[str] = None,
        week: Optional[int] = None,
    ) -> Dict:
        pass

    @abstractmethod
    def get_league_stats(self, season: Optional[str] = None) -> Dict:
        pass

    @abstractmethod
    def get_all_time_stats(self) -> Dict:
        pass

    @abstractmethod
    def get_week_summary(self, week: int, season: Optional[str] = None) -> dict:
        pass

    @abstractmethod
    def get_league_game_stats(
        self, season: Optional[str] = None, *, all_time: bool = False
    ) -> dict:
        pass

    @abstractmethod
    def get_week_matchups(self, week: int, season: Optional[str] = None) -> dict:
        pass

    @abstractmethod
    def get_team_weekly_summary(
        self, team_name: str, season: Optional[str] = None
    ) -> Dict:
        pass

    @abstractmethod
    def list_weeks_for_season(self, season: Optional[str] = None) -> List[int]:
        pass

    @abstractmethod
    def list_playoff_weeks_for_season(
        self, season: Optional[str] = None
    ) -> List[int]:
        pass

    @abstractmethod
    def get_latest_week(self, season: Optional[str] = None) -> int:
        pass

    @abstractmethod
    def find_player_names(
        self, search: str, season: Optional[str] = None
    ) -> List[str]:
        pass


class DbLeagueData(LeagueDataSource):
    """Facts from PostgreSQL; stats via stats.compute."""

    def __init__(self):
        self._facts: Optional[List[dict]] = None
        self._matchup_overrides: Optional[List[dict]] = None

    @property
    def read_source(self) -> str:
        return "database"

    def reload_workbook(self) -> None:
        self._facts = None
        self._matchup_overrides = None

    def _facts_list(self) -> List[dict]:
        if self._facts is None:
            self._facts = load_all_facts()
        return self._facts

    def _overrides_list(self) -> List[dict]:
        if self._matchup_overrides is None:
            self._matchup_overrides = load_all_matchup_overrides()
        return self._matchup_overrides

    def get_seasons(self) -> List[str]:
        return compute.seasons_from_facts(self._facts_list())

    def get_current_season(self) -> Optional[str]:
        return compute.current_season_label(self._facts_list())

    def get_team_scores(
        self,
        team_name: Optional[str] = None,
        season: Optional[str] = None,
        week: Optional[int] = None,
        through_week: Optional[int] = None,
    ) -> Dict:
        if season is None:
            season = self.get_current_season()
        season_num = compute.parse_season_number(season)
        return compute.get_team_scores(
            self._facts_list(),
            team_name,
            season,
            week,
            through_week,
            season_num=season_num,
            matchup_overrides=self._overrides_list(),
        )

    def get_player_scores(
        self,
        player_name: Optional[str] = None,
        season: Optional[str] = None,
        week: Optional[int] = None,
    ) -> Dict:
        if season is None:
            season = self.get_current_season()
        season_num = compute.parse_season_number(season)
        return compute.get_player_scores(
            self._facts_list(),
            player_name,
            season,
            week,
            season_num=season_num,
        )

    def get_player_game_history(
        self,
        player_name: str,
        season: Optional[str] = None,
        *,
        limit: int = 30,
    ) -> List[dict]:
        season_num = None
        if season not in (None, "", "all"):
            season_num = compute.parse_season_number(season)
        return compute.get_player_game_history(
            self._facts_list(),
            player_name,
            season,
            season_num=season_num,
            limit=limit,
        )

    def get_league_stats(self, season: Optional[str] = None) -> Dict:
        season_num = compute.parse_season_number(season)
        return compute.get_league_stats(
            self._facts_list(), season, season_num=season_num
        )

    def get_all_time_stats(self) -> Dict:
        return compute.get_all_time_stats(self._facts_list())

    def get_week_summary(self, week: int, season: Optional[str] = None) -> dict:
        if season is None:
            season = self.get_current_season()
        season_num = compute.parse_season_number(season)
        return compute.get_week_summary(
            self._facts_list(), week, season, season_num=season_num
        )

    def get_league_game_stats(
        self, season: Optional[str] = None, *, all_time: bool = False
    ) -> dict:
        facts = self._facts_list()
        if all_time:
            return compute.get_league_game_stats(facts, exclude_substitutes=True)
        if season is None:
            season = self.get_current_season()
        season_num = compute.parse_season_number(season)
        return compute.get_league_game_stats(facts, season_num=season_num)

    def get_player_par(self, season: Optional[str] = None) -> Dict[str, int]:
        facts = self._facts_list()
        if season in (None, "", "all"):
            return compute.compute_player_par(facts, season=None)
        season_num = compute.parse_season_number(season)
        return compute.compute_player_par(facts, season=season, season_num=season_num)

    def get_week_matchups(self, week: int, season: Optional[str] = None) -> dict:
        if season is None:
            season = self.get_current_season()
        season_num = compute.parse_season_number(season)
        return compute.get_week_matchups(
            self._facts_list(),
            week,
            season,
            season_num=season_num,
            matchup_overrides=self._overrides_list(),
        )

    def get_team_weekly_summary(
        self, team_name: str, season: Optional[str] = None
    ) -> Dict:
        season_num = compute.parse_season_number(season)
        return compute.get_team_weekly_summary(
            self._facts_list(),
            team_name,
            season,
            season_num=season_num,
            matchup_overrides=self._overrides_list(),
        )

    def list_weeks_for_season(self, season: Optional[str] = None) -> List[int]:
        if season is None:
            season = self.get_current_season()
        season_num = compute.parse_season_number(season)
        return compute.list_weeks_for_season(
            self._facts_list(), season, season_num=season_num
        )

    def list_playoff_weeks_for_season(
        self, season: Optional[str] = None
    ) -> List[int]:
        return compute.list_playoff_weeks_for_season(
            self._facts_list(),
            season,
            seasons=self.get_seasons(),
        )

    def get_latest_week(self, season: Optional[str] = None) -> int:
        if season is None:
            season = self.get_current_season()
        season_num = compute.parse_season_number(season)
        return compute.get_latest_week(
            self._facts_list(), season, season_num=season_num
        )

    def find_player_names(
        self, search: str, season: Optional[str] = None
    ) -> List[str]:
        if season is None:
            season = self.get_current_season()
        season_num = compute.parse_season_number(season)
        return compute.find_player_names(
            self._facts_list(), search, season, season_num=season_num
        )


def create_league_data() -> Optional[DbLeagueData]:
    """Web app data source. Requires DATABASE_URL and a prior sync_db run."""
    try:
        get_database_url()
    except RuntimeError:
        return None
    if not db_has_data():
        return None
    return DbLeagueData()
