"""
Sheet handler module for reading/writing bowling league data.
Supports local Excel files with one row per week per player structure.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from openpyxl import load_workbook
from utils import safe_float, safe_int


class SheetHandler(ABC):
    """Abstract base class for sheet handlers."""
    
    @abstractmethod
    def get_team_scores(self, team_name: Optional[str] = None, season: Optional[str] = None, week: Optional[int] = None) -> Dict:
        """Get team scores. If team_name is None, return all teams."""
        pass
    
    @abstractmethod
    def get_player_scores(self, player_name: Optional[str] = None, season: Optional[str] = None, week: Optional[int] = None) -> Dict:
        """Get player scores. If player_name is None, return all players. If week is specified, return individual games for that week."""
        pass
    
    @abstractmethod
    def add_score(self, player_name: str, score: int, week: Optional[int] = None, season: Optional[str] = None) -> bool:
        """Add a score for a player. Returns True if successful."""
        pass
    
    @abstractmethod
    def get_seasons(self) -> List[str]:
        """Get list of available seasons."""
        pass


class ExcelHandler(SheetHandler):
    """Handler for local Excel files with one row per week per player structure."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.workbook = None
        self._load_workbook()
    
    def _load_workbook(self):
        """Load the Excel workbook."""
        self.workbook = load_workbook(self.file_path, data_only=True)
    
    def get_seasons(self) -> List[str]:
        """Get list of available season sheet names."""
        return [sheet for sheet in self.workbook.sheetnames if sheet.startswith('Season')]
    
    def _get_current_season(self) -> str:
        """Get the most recent season (highest number)."""
        seasons = self.get_seasons()
        if not seasons:
            return None
        # Sort by season number
        seasons.sort(key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 0, reverse=True)
        return seasons[0]
    
    def _get_season_number(self, season: Optional[str] = None) -> Optional[int]:
        """Get season number from season name."""
        if season is None:
            season = self._get_current_season()
        if season is None:
            return None
        try:
            return int(season.split()[-1])
        except (ValueError, IndexError):
            return None
    
    def _safe_float(self, value, default=0.0):
        return safe_float(value, default)

    def _safe_int(self, value, default=0):
        return safe_int(value, default)
    
    def _normalize(self, text: str) -> str:
        """Normalize text for comparison — lowercase and flatten curly quotes."""
        return text.lower().replace('\u2018', "'").replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')

    def _is_absent(self, value) -> bool:
        """Check if absent flag is set."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.upper() in ['Y', 'YES', 'TRUE', '1']
        return bool(value)
    
    def _is_substitute(self, value) -> bool:
        """Check if substitute flag is set."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.upper() in ['Y', 'YES', 'TRUE', '1']
        return bool(value)
    
    def get_team_scores(self, team_name: Optional[str] = None, season: Optional[str] = None, week: Optional[int] = None) -> Dict:
        """Get team scores from Excel. Team average is average of individual player averages.
        Total pins includes absences but excludes substitutes.
        Calculates wins/losses/ties from weekly matchups.
        If week is specified, returns individual games for that week.
        If season is None, uses the latest/current season."""
        # Save week parameter immediately to avoid it being overwritten by loop variables
        week_param = week
        
        # If no season specified, use current season
        if season is None:
            season = self._get_current_season()
        
        season_num = self._get_season_number(season)
        if season_num is None:
            return {"error": f"Season '{season}' not found"}
        
        season_sheet = f"Season {season_num}"
        if season_sheet not in self.workbook.sheetnames:
            return {"error": f"Season '{season}' not found"}
        
        sheet = self.workbook[season_sheet]
        results = {}
        
        # Structure: team_name -> {
        #   players: {player_name -> {games: []}},  # For average calculation (excludes absent/sub)
        #   weekly_totals: {week -> {pins: int, opponent: str}}  # For wins/losses (excludes sub, includes absent)
        # }
        team_data = {}
        
        # Column mapping: Index=1 (ignored), Team=2, Player=3, Season=4, Week=5, Game1=6, Game2=7, Game3=8, Game4=9, Game5=10, Average=11
        # Absent?=13, Substitute?=14, Opponent=15
        for row in range(2, sheet.max_row + 1):
            row_team = sheet.cell(row=row, column=2).value
            row_player = sheet.cell(row=row, column=3).value
            row_season = sheet.cell(row=row, column=4).value
            row_week = sheet.cell(row=row, column=5).value
            absent = sheet.cell(row=row, column=13).value
            substitute = sheet.cell(row=row, column=14).value
            opponent = sheet.cell(row=row, column=15).value  # Opponent column
            
            if row_season != season_num:
                continue
            
            # If week is specified, skip other weeks
            if week_param is not None:
                if self._safe_int(row_week, 0) != week_param:
                    continue
            
            if not row_team or not isinstance(row_team, str):
                continue
            
            team = row_team.strip()
            is_sub = self._is_substitute(substitute)
            is_absent = self._is_absent(absent)
            
            # Initialize team structure
            if team not in team_data:
                team_data[team] = {
                    "players": {},
                    "weekly_totals": {}
                }
            
            # Get games (Game 1-5)
            games = []
            for col in range(6, 11):  # Columns 6-10 (Game 1-5)
                game_score = sheet.cell(row=row, column=col).value
                if game_score is not None:
                    game_float = self._safe_float(game_score)
                    if game_float > 0:
                        games.append(game_float)
            
            week_total = sum(games)
            
            # For team average: exclude both absent and substitutes
            if not is_sub and not is_absent and row_player and isinstance(row_player, str):
                player = row_player.strip()
                if player not in team_data[team]["players"]:
                    team_data[team]["players"][player] = {"games": []}
                team_data[team]["players"][player]["games"].extend(games)
            
            # For weekly totals (wins/losses): exclude substitutes but include absent
            if not is_sub and row_week is not None:
                row_week_num = self._safe_int(row_week, 0)
                if row_week_num > 0:
                    if row_week_num not in team_data[team]["weekly_totals"]:
                        team_data[team]["weekly_totals"][row_week_num] = {
                            "pins": 0,
                            "opponent": str(opponent).strip() if opponent else None
                        }
                    team_data[team]["weekly_totals"][row_week_num]["pins"] += week_total
        
        # Calculate team stats
        for team, data in team_data.items():
            # Calculate team average (average of player averages, excluding absent/sub)
            player_averages = []
            for player, player_data in data["players"].items():
                games = player_data["games"]
                if games:
                    player_avg = sum(games) / len(games)
                    player_averages.append(player_avg)
            
            avg_per_game = sum(player_averages) / len(player_averages) if player_averages else 0
            
            # Calculate total pins (includes absent, excludes substitutes)
            total_pins = 0
            for week_data in data["weekly_totals"].values():
                total_pins += week_data["pins"]
            
            # Calculate wins/losses/ties from individual game matchups (per game number, not per week)
            # Compare Game 1 vs Game 1, Game 2 vs Game 2, etc. (up to 4 games per week)
            wins = 0
            losses = 0
            ties = 0
            pins_against = 0
            
            # Collect games by game number (1-4) per week for this team
            team_weekly_game_totals = {}  # week -> {game_num: total_pins}
            for row in range(2, sheet.max_row + 1):
                row_team = sheet.cell(row=row, column=2).value
                row_season = sheet.cell(row=row, column=4).value
                row_week = sheet.cell(row=row, column=5).value
                substitute = sheet.cell(row=row, column=14).value
                
                if (row_season != season_num or 
                    not row_team or 
                    row_team.strip() != team or
                    self._is_substitute(substitute)):
                    continue
                
                row_week_num = self._safe_int(row_week, 0)
                if row_week_num > 0:
                    if row_week_num not in team_weekly_game_totals:
                        team_weekly_game_totals[row_week_num] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                    
                    # Sum games by game number (Game 1 = col 5, Game 2 = col 6, etc.)
                    for game_num in range(1, 6):  # Game 1-5
                        col = 5 + game_num  # Column 6-10
                        game_score = sheet.cell(row=row, column=col).value
                        if game_score is not None:
                            game_float = self._safe_float(game_score)
                            if game_float > 0:
                                team_weekly_game_totals[row_week_num][game_num] += game_float
            
            # Compare games week by week, game number by game number
            for week_num, week_data in data["weekly_totals"].items():
                opponent_name = week_data["opponent"]
                team_games = team_weekly_game_totals.get(week_num, {})
                
                if opponent_name and team_games:
                    # Find opponent team's game totals for this week
                    opp_games = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                    opp_team_found = None
                    
                    for opp_team, opp_data in team_data.items():
                        if (opponent_name.lower() in opp_team.lower() or 
                            opp_team.lower() in opponent_name.lower()):
                            opp_team_found = opp_team
                            break
                    
                    if opp_team_found:
                        # Get opponent's games for this week
                        for row in range(2, sheet.max_row + 1):
                            row_team = sheet.cell(row=row, column=2).value
                            row_season = sheet.cell(row=row, column=4).value
                            row_week = sheet.cell(row=row, column=5).value
                            substitute = sheet.cell(row=row, column=14).value
                            
                            if (row_season != season_num or
                                not row_team or
                                row_team.strip() != opp_team_found or
                                self._safe_int(row_week, 0) != week_num or
                                self._is_substitute(substitute)):
                                continue
                            
                            # Sum games by game number
                            for game_num in range(1, 6):
                                col = 5 + game_num
                                game_score = sheet.cell(row=row, column=col).value
                                if game_score is not None:
                                    game_float = self._safe_float(game_score)
                                    if game_float > 0:
                                        opp_games[game_num] += game_float
                    
                    # Compare Game 1 vs Game 1, Game 2 vs Game 2, etc. (up to 5 games if Game 5 is played)
                    for game_num in range(1, 6):  # Compare Game 1-5 (includes Game 5 if played)
                        team_total = team_games.get(game_num, 0)
                        opp_total = opp_games.get(game_num, 0)
                        
                        if team_total > 0 or opp_total > 0:
                            pins_against += opp_total
                            
                            if team_total > opp_total:
                                wins += 1
                            elif team_total < opp_total:
                                losses += 1
                            else:
                                ties += 1
            
            # Calculate player averages for individual players
            player_averages_dict = {}
            for player, player_data in data["players"].items():
                games = player_data["games"]
                if games:
                    player_avg = sum(games) / len(games)
                    player_averages_dict[player] = round(player_avg, 2)
            
            team_result = {
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "pins_for": int(total_pins),
                "pins_against": int(pins_against),
                "avg_per_game": round(avg_per_game, 2),
                "players": player_averages_dict
            }
            
            # If week parameter is specified and team matches, return week data
            if week_param is not None and team_name:
                if self._normalize(team_name) in self._normalize(team) or self._normalize(team) in self._normalize(team_name):
                    # Get week data
                    week_info = data["weekly_totals"].get(week_param)
                    if week_info:
                        # Get individual player games for this week
                        players_games = {}
                        week_total = 0
                        team_weekly_game_totals = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                        
                        for row in range(2, sheet.max_row + 1):
                            r_team = sheet.cell(row=row, column=2).value
                            r_player = sheet.cell(row=row, column=3).value
                            r_season = sheet.cell(row=row, column=4).value
                            r_week = sheet.cell(row=row, column=5).value
                            r_substitute = sheet.cell(row=row, column=14).value
                            
                            if (r_season == season_num and
                                r_team and r_team.strip() == team and
                                self._safe_int(r_week, 0) == week_param and
                                not self._is_substitute(r_substitute)):
                                
                                player = r_player.strip() if r_player else "Unknown"
                                games = []
                                for col in range(6, 11):
                                    game_score = sheet.cell(row=row, column=col).value
                                    if game_score is not None:
                                        game_float = self._safe_float(game_score)
                                        if game_float > 0:
                                            games.append(game_float)
                                
                                if games:
                                    players_games[player] = games
                                    week_total += sum(games)
                                    # Sum by game number for record calculation
                                    for game_num in range(1, min(len(games) + 1, 6)):
                                        team_weekly_game_totals[game_num] += games[game_num - 1]
                        
                        # Calculate weekly record by comparing games
                        opponent_name = week_info.get("opponent", "Unknown")
                        week_wins = 0
                        week_losses = 0
                        week_ties = 0
                        
                        if opponent_name and opponent_name != "Unknown":
                            # Find opponent team
                            opp_team_found = None
                            for opp_team, opp_data in team_data.items():
                                if (opponent_name.lower() in opp_team.lower() or 
                                    opp_team.lower() in opponent_name.lower()):
                                    opp_team_found = opp_team
                                    break
                            
                            if opp_team_found:
                                # Get opponent's games for this week
                                opp_games = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                                for row in range(2, sheet.max_row + 1):
                                    row_team = sheet.cell(row=row, column=2).value
                                    row_season = sheet.cell(row=row, column=4).value
                                    row_week = sheet.cell(row=row, column=5).value
                                    substitute = sheet.cell(row=row, column=14).value
                                    
                                    if (row_season != season_num or
                                        not row_team or
                                        str(row_team).strip() != opp_team_found or
                                        self._safe_int(row_week, 0) != week_param or
                                        self._is_substitute(substitute)):
                                        continue
                                    
                                    # Sum games by game number
                                    for game_num in range(1, 6):
                                        col = 5 + game_num
                                        game_score = sheet.cell(row=row, column=col).value
                                        if game_score is not None:
                                            game_float = self._safe_float(game_score)
                                            if game_float > 0:
                                                opp_games[game_num] += game_float
                                
                                # Compare Game 1 vs Game 1, Game 2 vs Game 2, etc. (up to 5 games if Game 5 is played)
                                for game_num in range(1, 6):  # Compare Game 1-5 (includes Game 5 if played)
                                    team_total = team_weekly_game_totals.get(game_num, 0)
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
                                "ties": week_ties
                            }
                        }
                    else:
                        return {"error": f"No data found for {team} in Week {week_param}"}
            
            if team_name is None:
                results[team] = team_result
            elif self._normalize(team_name) in self._normalize(team) or self._normalize(team) in self._normalize(team_name):
                return {"team": team, **team_result}
        
        if team_name:
            if week_param is not None:
                return {"error": f"Team '{team_name}' not found in Week {week_param} of {season}"}
            return {"error": f"Team '{team_name}' not found in {season}"}
        
        return results
    
    def get_team_weekly_summary(self, team_name: str, season: Optional[str] = None) -> Dict:
        """Get weekly breakdown for a team showing opponent, record, and totals per week."""
        season_num = self._get_season_number(season)
        if season_num is None:
            return {"error": f"Season '{season}' not found"}
        
        season_sheet = f"Season {season_num}"
        if season_sheet not in self.workbook.sheetnames:
            return {"error": f"Season '{season}' not found"}
        
        sheet = self.workbook[season_sheet]
        
        # Find the team
        team_found = None
        for row in range(2, sheet.max_row + 1):
            row_team = sheet.cell(row=row, column=2).value
            if row_team and isinstance(row_team, str):
                if self._normalize(team_name) in self._normalize(row_team.strip()) or self._normalize(row_team.strip()) in self._normalize(team_name):
                    team_found = row_team.strip()
                    break
        
        if not team_found:
            return {"error": f"Team '{team_name}' not found in {season}"}
        
        # Collect weekly data
        weekly_data = {}  # week -> {opponent, team_pins, opp_pins, team_games, opp_games, wins, losses, ties}
        
        # Get all teams' data for comparison
        all_teams = {}
        for row in range(2, sheet.max_row + 1):
            row_team = sheet.cell(row=row, column=2).value
            row_season = sheet.cell(row=row, column=4).value
            row_week = sheet.cell(row=row, column=5).value
            substitute = sheet.cell(row=row, column=14).value
            
            if (row_season != season_num or 
                not row_team or
                self._is_substitute(substitute)):
                continue
            
            team = row_team.strip()
            week = self._safe_int(row_week, 0)
            
            if week > 0:
                if team not in all_teams:
                    all_teams[team] = {}
                if week not in all_teams[team]:
                    all_teams[team][week] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                
                for game_num in range(1, 6):
                    col = 5 + game_num
                    game_score = sheet.cell(row=row, column=col).value
                    if game_score is not None:
                        game_float = self._safe_float(game_score)
                        if game_float > 0:
                            all_teams[team][week][game_num] += game_float
        
        # Get team's weekly data
        for row in range(2, sheet.max_row + 1):
            row_team = sheet.cell(row=row, column=2).value
            row_season = sheet.cell(row=row, column=4).value
            row_week = sheet.cell(row=row, column=5).value
            substitute = sheet.cell(row=row, column=14).value
            opponent = sheet.cell(row=row, column=15).value
            
            if (row_season != season_num or 
                not row_team or 
                row_team.strip() != team_found or
                self._is_substitute(substitute)):
                continue
            
            week = self._safe_int(row_week, 0)
            if week > 0:
                if week not in weekly_data:
                    weekly_data[week] = {
                        "opponent": str(opponent).strip() if opponent else "Unknown",
                        "game_totals": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                        "opp_game_totals": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                        "wins": 0,
                        "losses": 0,
                        "ties": 0
                    }
                
                # Sum games by game number
                for game_num in range(1, 6):
                    col = 5 + game_num
                    game_score = sheet.cell(row=row, column=col).value
                    if game_score is not None:
                        game_float = self._safe_float(game_score)
                        if game_float > 0:
                            weekly_data[week]["game_totals"][game_num] += game_float
        
        # Calculate wins/losses and get opponent totals
        for week, week_info in weekly_data.items():
            opponent_name = week_info["opponent"]
            team_games = week_info["game_totals"]
            
            # Find opponent team
            opp_team_found = None
            for team_name_key in all_teams.keys():
                if (opponent_name.lower() in team_name_key.lower() or 
                    team_name_key.lower() in opponent_name.lower()):
                    opp_team_found = team_name_key
                    break
            
            if opp_team_found and week in all_teams[opp_team_found]:
                opp_games = all_teams[opp_team_found][week]
                week_info["opp_game_totals"] = opp_games
                
                # Compare Game 1-5 (includes Game 5 if played)
                for game_num in range(1, 6):
                    team_total = team_games.get(game_num, 0)
                    opp_total = opp_games.get(game_num, 0)
                    
                    # Only compare if at least one team has data for this game
                    if team_total > 0 or opp_total > 0:
                        if team_total > opp_total:
                            week_info["wins"] += 1
                        elif team_total < opp_total:
                            week_info["losses"] += 1
                        else:
                            week_info["ties"] += 1
        
        # Calculate weekly averages and totals
        for week, week_info in weekly_data.items():
            team_games = week_info["game_totals"]
            team_total = sum(team_games.values())
            opp_total = sum(week_info["opp_game_totals"].values())
            
            # Count number of individual games played (not just game numbers)
            # Count all non-zero game scores for this week
            total_games = 0
            for row in range(2, sheet.max_row + 1):
                row_team = sheet.cell(row=row, column=2).value
                row_season = sheet.cell(row=row, column=4).value
                row_week = sheet.cell(row=row, column=5).value
                substitute = sheet.cell(row=row, column=14).value
                
                if (row_season == season_num and
                    row_team and row_team.strip() == team_found and
                    self._safe_int(row_week, 0) == week and
                    not self._is_substitute(substitute)):
                    # Count games for this player
                    for col in range(6, 11):  # Game 1-5
                        game_score = sheet.cell(row=row, column=col).value
                        if game_score is not None:
                            game_float = self._safe_float(game_score)
                            if game_float > 0:
                                total_games += 1
            
            # Weekly average = total pins / number of individual games
            if total_games > 0:
                week_info["avg"] = team_total / total_games
            else:
                week_info["avg"] = 0
            
            week_info["pins_for"] = int(team_total)
            week_info["pins_against"] = int(opp_total)
        
        return {
            "team": team_found,
            "season": season or f"Season {season_num}",
            "weekly_summary": weekly_data
        }
    
    def get_league_stats(self, season: Optional[str] = None) -> Dict:
        """Get league statistics including top players, best weeks, best team totals, and best games."""
        season_num = self._get_season_number(season)
        if season_num is None:
            return {"error": f"Season '{season}' not found"}
        
        season_sheet = f"Season {season_num}"
        if season_sheet not in self.workbook.sheetnames:
            return {"error": f"Season '{season}' not found"}
        
        sheet = self.workbook[season_sheet]
        
        # Collect all data
        player_averages = {}  # player -> {team, average, games_count}
        player_weekly_totals = []  # [(player, team, week, total_pins)]
        team_weekly_totals = []  # [(team, week, total_pins)]
        individual_games = []  # [(player, team, week, game_score)]
        
        for row in range(2, sheet.max_row + 1):
            row_team = sheet.cell(row=row, column=2).value
            row_player = sheet.cell(row=row, column=3).value
            row_season = sheet.cell(row=row, column=4).value
            row_week = sheet.cell(row=row, column=5).value
            absent = sheet.cell(row=row, column=13).value
            substitute = sheet.cell(row=row, column=14).value
            
            if row_season != season_num:
                continue
            
            if not row_team or not isinstance(row_team, str):
                continue
            
            team = row_team.strip()
            is_sub = self._is_substitute(substitute)
            is_absent = self._is_absent(absent)
            
            # Skip substitutes for all stats
            if is_sub:
                continue
            
            # Get games for this row
            week_games = []
            for col in range(6, 11):  # Columns 6-10 (Game 1-5)
                game_score = sheet.cell(row=row, column=col).value
                if game_score is not None:
                    game_float = self._safe_float(game_score)
                    if game_float > 0:
                        week_games.append(game_float)
                        individual_games.append((row_player, team, self._safe_int(row_week, 0), game_float))
            
            week_total = sum(week_games)
            
            # For player averages: exclude absent
            if not is_absent and row_player and isinstance(row_player, str):
                player = row_player.strip()
                if player not in player_averages:
                    player_averages[player] = {
                        "team": team,
                        "games": [],
                        "total_pins": 0
                    }
                player_averages[player]["games"].extend(week_games)
                player_averages[player]["total_pins"] += week_total
                
                # Track weekly totals for players (with game count)
                if week_total > 0:
                    num_games = len(week_games)
                    player_weekly_totals.append((player, team, self._safe_int(row_week, 0), week_total, num_games))
            
            # For team weekly totals: include absent (but not substitutes)
            if row_week is not None:
                week = self._safe_int(row_week, 0)
                if week > 0 and week_total > 0:
                    team_weekly_totals.append((team, week, week_total, len(week_games)))
        
        # Calculate player averages
        player_avg_list = []
        for player, data in player_averages.items():
            games = data["games"]
            if games:
                avg = sum(games) / len(games)
                player_avg_list.append({
                    "player": player,
                    "team": data["team"],
                    "average": round(avg, 2),
                    "games": len(games)
                })
        
        # Sort player averages (highest first)
        player_avg_list.sort(key=lambda x: x["average"], reverse=True)
        
        # Sort player weekly totals by average (highest first)
        player_weekly_totals.sort(key=lambda x: x[3] / x[4] if x[4] else 0, reverse=True)
        top_player_weeks = player_weekly_totals[:10]  # (player, team, week, total, num_games)
        
        # Aggregate team weekly totals (sum all players for each team/week)
        team_week_dict = {}  # (team, week) -> [total, games]
        for team, week, total, games in team_weekly_totals:
            key = (team, week)
            if key not in team_week_dict:
                team_week_dict[key] = [0, 0]
            team_week_dict[key][0] += total
            team_week_dict[key][1] += games

        # Convert to list and sort by average
        team_totals_list = [
            (team, week, vals[0], vals[1])
            for (team, week), vals in team_week_dict.items()
        ]
        team_totals_list.sort(key=lambda x: x[2] / x[3] if x[3] else 0, reverse=True)
        top_team_totals = team_totals_list[:5]
        
        # Sort individual games (highest first)
        individual_games.sort(key=lambda x: x[3], reverse=True)
        top_games = individual_games[:10]
        
        return {
            "season": season or f"Season {season_num}",
            "player_averages": player_avg_list,
            "top_player_weeks": top_player_weeks,
            "top_team_totals": top_team_totals,
            "top_games": top_games
        }

    def get_all_time_stats(self) -> Dict:
        """Aggregate league stats across all seasons for all-time leaders."""
        all_individual_games = []   # (player, team, label, score)
        all_player_weeks = []       # (player, team, label, total, num_games)
        all_team_weeks = {}         # (team, label) -> total
        player_totals = {}          # player -> {team, games: []}

        # Iterate seasons from latest to earliest so player_totals["team"] reflects most recent team
        sorted_sheets = sorted(
            [s for s in self.workbook.sheetnames if s.startswith("Season") and s.split()[-1].isdigit()],
            key=lambda s: int(s.split()[-1]),
            reverse=True
        )
        for sheet_name in sorted_sheets:
            season_num = int(sheet_name.split()[-1])
            sheet = self.workbook[sheet_name]

            team_week_pins: Dict[tuple, float] = {}

            for row in range(2, sheet.max_row + 1):
                row_team   = sheet.cell(row=row, column=2).value
                row_player = sheet.cell(row=row, column=3).value
                row_season = sheet.cell(row=row, column=4).value
                row_week   = sheet.cell(row=row, column=5).value
                absent     = sheet.cell(row=row, column=13).value
                substitute = sheet.cell(row=row, column=14).value

                if row_season != season_num:
                    continue
                if not row_team or not isinstance(row_team, str):
                    continue

                team   = row_team.strip()
                week   = self._safe_int(row_week, 0)
                label  = f"S{season_num} W{week}"
                is_sub = self._is_substitute(substitute)
                is_absent = self._is_absent(absent)

                if is_sub:
                    continue

                week_games = []
                for col in range(6, 11):
                    g = self._safe_float(sheet.cell(row=row, column=col).value)
                    if g and g > 0:
                        week_games.append(g)
                        all_individual_games.append((row_player, team, label, g))

                week_total = sum(week_games)

                if not is_absent and row_player and isinstance(row_player, str):
                    player = row_player.strip()
                    if player not in player_totals:
                        player_totals[player] = {"team": team, "games": []}
                    player_totals[player]["games"].extend(week_games)

                    if week_total > 0:
                        all_player_weeks.append((row_player, team, label, week_total, len(week_games)))

                if week > 0 and week_total > 0:
                    key = (team, label)
                    if key not in team_week_pins:
                        team_week_pins[key] = [0, 0]
                    team_week_pins[key][0] += week_total
                    team_week_pins[key][1] += len(week_games)

            for (team, label), vals in team_week_pins.items():
                if label not in all_team_weeks:
                    all_team_weeks[(team, label)] = [0, 0]
                all_team_weeks[(team, label)][0] += vals[0]
                all_team_weeks[(team, label)][1] += vals[1]

        # Sort and trim
        all_individual_games.sort(key=lambda x: x[3], reverse=True)
        all_player_weeks.sort(key=lambda x: x[3] / x[4] if x[4] else 0, reverse=True)
        team_totals = sorted(
            [(t, lbl, vals[0], vals[1]) for (t, lbl), vals in all_team_weeks.items()],
            key=lambda x: x[2] / x[3] if x[3] else 0, reverse=True
        )

        def _std_dev(games):
            if len(games) < 2:
                return 0.0
            avg = sum(games) / len(games)
            return (sum((g - avg) ** 2 for g in games) / len(games)) ** 0.5

        player_avg_list = sorted(
            [{"player": p, "team": d["team"],
              "average": round(sum(d["games"]) / len(d["games"]), 2),
              "std_dev": round(_std_dev(d["games"]), 2),
              "highest_game": max(d["games"]),
              "lowest_game": min(d["games"]),
              "games": len(d["games"])}
             for p, d in player_totals.items() if d["games"]],
            key=lambda x: x["average"], reverse=True
        )

        return {
            "season": "All Time",
            "player_averages": player_avg_list,
            "top_player_weeks": all_player_weeks[:10],
            "top_team_totals": team_totals[:5],
            "top_games": all_individual_games[:10],
        }
    
    def get_player_scores(self, player_name: Optional[str] = None, season: Optional[str] = None, week: Optional[int] = None) -> Dict:
        """Get player scores from Excel. Excludes absent weeks from average calculation.
        If week is specified, returns individual games for that week.
        If season is None, uses the latest/current season."""
        # If no season specified, use current season
        if season is None:
            season = self._get_current_season()
        
        season_num = self._get_season_number(season)
        if season_num is None:
            return {"error": f"Season '{season}' not found"}
        
        season_sheet = f"Season {season_num}"
        if season_sheet not in self.workbook.sheetnames:
            return {"error": f"Season '{season}' not found"}
        
        sheet = self.workbook[season_sheet]
        results = {}
        player_data = {}  # player_name -> {team, scores, absent_count}
        
        # Column mapping: Index=1 (ignored), Team=2, Player=3, Season=4, Week=5, Game1=6, Game2=7, Game3=8, Game4=9, Game5=10, Average=11
        for row in range(2, sheet.max_row + 1):
            row_team = sheet.cell(row=row, column=2).value
            row_player = sheet.cell(row=row, column=3).value
            row_season = sheet.cell(row=row, column=4).value
            row_week = sheet.cell(row=row, column=5).value
            absent = sheet.cell(row=row, column=13).value  # Absent? column
            
            # Skip if not this season
            if row_season != season_num:
                continue
            
            # If week is specified, skip other weeks
            if week is not None:
                if self._safe_int(row_week, 0) != week:
                    continue
            
            if row_player and isinstance(row_player, str):
                player = row_player.strip()
                team = str(row_team).strip() if row_team else "Unknown"
                
                # Initialize player data
                if player not in player_data:
                    player_data[player] = {
                        "team": team,
                        "scores": [],
                        "absent_count": 0,
                        "weeks": [],
                        "highest_game": 0,
                        "lowest_game": 300
                    }
                
                # Get games for this week
                week_games = []
                for col in range(6, 11):  # Columns 6-10 (Game 1-5)
                    game_score = sheet.cell(row=row, column=col).value
                    if game_score is not None:
                        game_float = self._safe_float(game_score)
                        if game_float > 0:
                            week_games.append(game_float)
                
                # Get average for this week (from column 11)
                week_avg = sheet.cell(row=row, column=11).value
                if week_avg is not None:
                    week_avg = self._safe_float(week_avg)
                elif week_games:
                    week_avg = sum(week_games) / len(week_games)
                else:
                    week_avg = 0
                
                # If not absent, add to scores for average calculation
                is_absent = self._is_absent(absent)
                if not is_absent:
                    # Add individual game scores
                    player_data[player]["scores"].extend(week_games)
                    # Track highest and lowest games
                    for game_score in week_games:
                        if game_score > player_data[player]["highest_game"]:
                            player_data[player]["highest_game"] = game_score
                        if game_score < player_data[player]["lowest_game"]:
                            player_data[player]["lowest_game"] = game_score
                else:
                    player_data[player]["absent_count"] += 1
                
                # Store week info
                player_data[player]["weeks"].append({
                    "week": self._safe_int(row_week, 0),
                    "games": week_games,
                    "average": week_avg,
                    "absent": is_absent
                })
        
        # Calculate averages (excluding absent weeks)
        for player, data in player_data.items():
            scores = data["scores"]
            avg = sum(scores) / len(scores) if scores else 0
            
            # Calculate standard deviation
            std_dev = 0
            if scores and len(scores) > 1:
                variance = sum((x - avg) ** 2 for x in scores) / len(scores)
                std_dev = variance ** 0.5
            
            # Get highest and lowest games
            highest = data.get("highest_game", 0)
            lowest = data.get("lowest_game", 300)
            # If no games were recorded, calculate from scores
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
                "lowest_game": int(lowest)
            }
            
            # If week is specified and player matches, return week data
            if week is not None and player_name:
                if self._normalize(player_name) in self._normalize(player) or self._normalize(player) in self._normalize(player_name):
                    # Find the week data
                    week_info = None
                    for w in data["weeks"]:
                        if w["week"] == week:
                            week_info = w
                            break
                    
                    if week_info:
                        return {
                            "player": player,
                            "team": data["team"],
                            "week_data": {
                                "games": week_info["games"],
                                "average": week_info["average"],
                                "absent": week_info["absent"]
                            }
                        }
                    else:
                        return {"error": f"No data found for {player} in Week {week}"}
            
            if player_name is None:
                results[player] = result_data
            elif self._normalize(player_name) in self._normalize(player) or self._normalize(player) in self._normalize(player_name):
                return {"player": player, **result_data}
        
        if player_name:
            if week is not None:
                return {"error": f"Player '{player_name}' not found in Week {week} of {season}"}
            return {"error": f"Player '{player_name}' not found in {season}"}
        
        return results
    
    def add_score(self, player_name: str, score: int, week: Optional[int] = None, season: Optional[str] = None) -> bool:
        """Add a score for a player. Note: This modifies the Excel file.

        LIMITATION: The workbook is loaded with data_only=True, which caches formula results
        as static values. Saving after a write will permanently strip any Excel formulas in the
        file (e.g. the Average column). Do not use this method if you rely on Excel formulas
        being preserved. Manual edits in Excel are the recommended way to update scores.
        """
        season_num = self._get_season_number(season)
        if season_num is None:
            return False
        
        season_sheet = f"Season {season_num}"
        if season_sheet not in self.workbook.sheetnames:
            return False
        
        sheet = self.workbook[season_sheet]
        
        # Find the player's row for the specified week (or latest week if not specified)
        target_row = None
        
        if week is None:
            # Find the latest week for this player
            max_week = 0
            for row in range(2, sheet.max_row + 1):
                row_player = sheet.cell(row=row, column=3).value
                row_season = sheet.cell(row=row, column=4).value
                row_week = sheet.cell(row=row, column=5).value
                
                if (row_player and isinstance(row_player, str) and 
                    player_name.lower() in row_player.lower() and 
                    row_season == season_num):
                    week_num = self._safe_int(row_week, 0)
                    if week_num > max_week:
                        max_week = week_num
                        target_row = row
            
            if target_row:
                # Find first empty game column
                for col in range(6, 11):  # Game 1-5 columns
                    game_value = sheet.cell(row=target_row, column=col).value
                    if game_value is None or game_value == "":
                        sheet.cell(row=target_row, column=col, value=score)
                        self.workbook.save(self.file_path)
                        return True
        else:
            # Find specific week for this player
            for row in range(2, sheet.max_row + 1):
                row_player = sheet.cell(row=row, column=3).value
                row_season = sheet.cell(row=row, column=4).value
                row_week = sheet.cell(row=row, column=5).value
                
                if (row_player and isinstance(row_player, str) and 
                    player_name.lower() in row_player.lower() and 
                    row_season == season_num and 
                    self._safe_int(row_week, 0) == week):
                    
                    # Find first empty game column
                    for col in range(6, 11):  # Game 1-5 columns
                        game_value = sheet.cell(row=row, column=col).value
                        if game_value is None or game_value == "":
                            sheet.cell(row=row, column=col, value=score)
                            self.workbook.save(self.file_path)
                            return True
                    break
        
        return False

    def get_latest_week(self, season: Optional[str] = None) -> int:
        """Return the highest week number that has any data in the given season."""
        if season is None:
            season = self._get_current_season()
        season_num = self._get_season_number(season)
        if season_num is None:
            return 1
        sheet_name = f"Season {season_num}"
        if sheet_name not in self.workbook.sheetnames:
            return 1
        sheet = self.workbook[sheet_name]
        max_week = 1
        for row in range(2, sheet.max_row + 1):
            if sheet.cell(row=row, column=4).value != season_num:
                continue
            w = self._safe_int(sheet.cell(row=row, column=5).value, 0)
            if w > max_week:
                max_week = w
        return max_week

    def get_week_summary(self, week: int, season: Optional[str] = None) -> dict:
        """Return all player and league stats for a specific week."""
        if season is None:
            season = self._get_current_season()
        season_num = self._get_season_number(season)
        sheet_name = f"Season {season_num}"
        if sheet_name not in self.workbook.sheetnames:
            return {"error": f"Season '{season}' not found"}
        sheet = self.workbook[sheet_name]

        players = []
        all_scored_games = []  # (score, player_name, team_name)

        for row in range(2, sheet.max_row + 1):
            if sheet.cell(row=row, column=4).value != season_num:
                continue
            if self._safe_int(sheet.cell(row=row, column=5).value, 0) != week:
                continue

            player = sheet.cell(row=row, column=3).value
            team = sheet.cell(row=row, column=2).value
            if not player or not isinstance(player, str):
                continue

            is_absent = self._is_absent(sheet.cell(row=row, column=13).value)
            games = []
            for col in range(6, 11):
                g = sheet.cell(row=row, column=col).value
                if g is not None:
                    gf = self._safe_float(g)
                    if gf > 0:
                        games.append(int(gf))

            entry = {
                "name": player.strip(),
                "team": str(team).strip() if team else "Unknown",
                "games": games,
                "avg": round(sum(games) / len(games), 1) if games else 0,
                "high": max(games) if games else 0,
                "absent": is_absent,
            }
            players.append(entry)
            if not is_absent:
                for g in games:
                    all_scored_games.append((g, player.strip(), str(team).strip() if team else "Unknown"))

        players.sort(key=lambda x: x["avg"], reverse=True)

        high_game = low_game = None
        if all_scored_games:
            all_scored_games.sort(key=lambda x: x[0])
            lg = all_scored_games[0]
            hg = all_scored_games[-1]
            high_game = {"score": hg[0], "player": hg[1], "team": hg[2]}
            low_game  = {"score": lg[0], "player": lg[1], "team": lg[2]}

        scores_only = [g for g, _, _ in all_scored_games]
        return {
            "season": season,
            "week": week,
            "players": players,
            "high_game": high_game,
            "low_game": low_game,
            "league_avg": round(sum(scores_only) / len(scores_only), 1) if scores_only else 0,
            "total_players": len([p for p in players if not p["absent"]]),
            "games_200_plus": len([g for g in scores_only if g >= 200]),
            "total_games": len(scores_only),
        }

    def get_week_matchups(self, week: int, season: Optional[str] = None) -> dict:
        """Return team matchup results for a specific week — total pins, avg, and W/L/T."""
        if season is None:
            season = self._get_current_season()
        season_num = self._get_season_number(season)
        sheet_name = f"Season {season_num}"
        if sheet_name not in self.workbook.sheetnames:
            return {"error": f"Season '{season}' not found"}
        sheet = self.workbook[sheet_name]

        # team_name -> {game_pins: [g1_total, g2_total, ...], player_count, opponent}
        teams: Dict[str, dict] = {}

        for row in range(2, sheet.max_row + 1):
            if sheet.cell(row=row, column=4).value != season_num:
                continue
            if self._safe_int(sheet.cell(row=row, column=5).value, 0) != week:
                continue

            team = sheet.cell(row=row, column=2).value
            player = sheet.cell(row=row, column=3).value
            if not team or not isinstance(team, str):
                continue
            if not player or not isinstance(player, str):
                continue

            is_absent = self._is_absent(sheet.cell(row=row, column=13).value)
            is_sub    = self._is_substitute(sheet.cell(row=row, column=14).value)
            opponent  = sheet.cell(row=row, column=15).value or ""

            team = team.strip()
            if team not in teams:
                teams[team] = {
                    "game_pins": [],  # list of per-game team totals
                    "player_count": 0,
                    "opponent": opponent.strip() if opponent else "",
                }

            # Include absent players (their avg counts as blind score) but exclude substitutes
            if not is_sub:
                teams[team]["player_count"] += 1
                for i, col in enumerate(range(6, 11)):  # Game 1-5
                    g = self._safe_float(sheet.cell(row=row, column=col).value)
                    if g and g > 0:
                        if i >= len(teams[team]["game_pins"]):
                            teams[team]["game_pins"].append(int(g))
                        else:
                            teams[team]["game_pins"][i] += int(g)

        # Build matchups — W/L determined per game, not total pins
        matched = set()
        matchups = []
        for team_name, td in teams.items():
            if team_name in matched:
                continue
            opp_name = td["opponent"]
            opp = teams.get(opp_name)

            total_h = sum(td["game_pins"])
            num_games = len(td["game_pins"])
            avg_h = round(total_h / (td["player_count"] * num_games), 1) if td["player_count"] and num_games else 0

            if not opp_name or not opp:
                matchups.append({
                    "home": {"name": team_name, "pins": total_h, "avg": avg_h,
                             "game_pins": td["game_pins"], "wins": 0, "result": "—"},
                    "away": None,
                })
                matched.add(team_name)
                continue

            matched.add(team_name)
            matched.add(opp_name)

            total_a = sum(opp["game_pins"])
            avg_a = round(total_a / (opp["player_count"] * len(opp["game_pins"])), 1) if opp["player_count"] and opp["game_pins"] else 0

            # Score per game
            h_wins = a_wins = ties = 0
            num_games = max(len(td["game_pins"]), len(opp["game_pins"]))
            game_results = []
            for i in range(num_games):
                hp = td["game_pins"][i]  if i < len(td["game_pins"])  else 0
                ap = opp["game_pins"][i] if i < len(opp["game_pins"]) else 0
                if hp > ap:
                    h_wins += 1
                    game_results.append(("W", "L", hp, ap))
                elif ap > hp:
                    a_wins += 1
                    game_results.append(("L", "W", hp, ap))
                else:
                    ties += 1
                    game_results.append(("T", "T", hp, ap))

            if h_wins > a_wins:
                h_result, a_result = "W", "L"
            elif a_wins > h_wins:
                h_result, a_result = "L", "W"
            else:
                h_result = a_result = "T"

            matchups.append({
                "home": {"name": team_name, "pins": total_h, "avg": avg_h,
                         "game_pins": td["game_pins"], "wins": h_wins, "result": h_result},
                "away": {"name": opp_name,  "pins": total_a, "avg": avg_a,
                         "game_pins": opp["game_pins"], "wins": a_wins, "result": a_result},
                "game_results": game_results,
            })

        matchups.sort(key=lambda m: m["home"]["name"])
        return {"season": season, "week": week, "matchups": matchups}

    def find_player_names(self, search: str, season: Optional[str] = None) -> List[str]:
        """Return all unique player names that match the search term (case-insensitive substring)."""
        if season is None:
            season = self._get_current_season()
        season_num = self._get_season_number(season)
        if season_num is None:
            return []
        sheet_name = f"Season {season_num}"
        if sheet_name not in self.workbook.sheetnames:
            return []
        sheet = self.workbook[sheet_name]
        seen = set()
        matches = []
        normalized_search = self._normalize(search)
        for row in range(2, sheet.max_row + 1):
            row_season = sheet.cell(row=row, column=4).value
            if row_season != season_num:
                continue
            player = sheet.cell(row=row, column=3).value
            if not player or not isinstance(player, str):
                continue
            player = player.strip()
            if player in seen:
                continue
            seen.add(player)
            if normalized_search in self._normalize(player) or self._normalize(player) in normalized_search:
                matches.append(player)
        return matches


# ---------------------------------------------------------------------------
# Google Sheets proxy — mimics the openpyxl cell/worksheet/workbook API so
# GSheetHandler can inherit all of ExcelHandler's logic unchanged.
# ---------------------------------------------------------------------------

class _CellProxy:
    """Wraps a raw string value from gspread with type coercion."""
    def __init__(self, raw):
        if raw is None or raw == "":
            self.value = None
            return
        # Try int first, then float, fall back to the raw string
        try:
            self.value = int(raw)
            return
        except (ValueError, TypeError):
            pass
        try:
            self.value = float(raw)
            return
        except (ValueError, TypeError):
            pass
        self.value = raw


class _WorksheetProxy:
    """Wraps a list-of-lists (gspread get_all_values) as an openpyxl worksheet."""
    def __init__(self, rows: list):
        self._rows = rows  # 0-indexed list of lists of strings

    @property
    def max_row(self) -> int:
        return len(self._rows)

    def cell(self, row: int, column: int) -> _CellProxy:
        """row and column are 1-indexed, matching openpyxl convention."""
        try:
            return _CellProxy(self._rows[row - 1][column - 1])
        except IndexError:
            return _CellProxy(None)


class _WorkbookProxy:
    """Wraps a dict of sheet-name -> _WorksheetProxy as an openpyxl workbook."""
    def __init__(self):
        self._sheets: dict = {}

    @property
    def sheetnames(self) -> list:
        return list(self._sheets.keys())

    def __getitem__(self, name: str) -> _WorksheetProxy:
        return self._sheets[name]

    def __contains__(self, name: str) -> bool:
        return name in self._sheets


# ---------------------------------------------------------------------------
# Google Sheets handler
# ---------------------------------------------------------------------------

class GSheetHandler(ExcelHandler):
    """Reads data from a Google Sheet using gspread.
    Inherits all query logic from ExcelHandler via the proxy layer.
    Data is loaded once at startup; restart the bot to pick up new scores."""

    def __init__(self, sheet_id: str, credentials_json: str):
        self.sheet_id = sheet_id
        self.credentials_json = credentials_json
        self.file_path = None  # not used
        self.workbook = None
        self._load_workbook()

    def _load_workbook(self):
        import gspread
        import json
        from google.oauth2.service_account import Credentials

        creds_dict = json.loads(self.credentials_json)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ],
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(self.sheet_id)

        wb = _WorkbookProxy()
        for ws in spreadsheet.worksheets():
            wb._sheets[ws.title] = _WorksheetProxy(ws.get_all_values())
            print(f"[GSheets] Loaded sheet: {ws.title} ({len(wb._sheets[ws.title]._rows)} rows)")
        self.workbook = wb
        print(f"[GSheets] Connected — {len(wb.sheetnames)} sheets loaded")

    def add_score(self, player_name: str, score: int, week=None, season=None) -> bool:
        """Write-back is not supported for Google Sheets."""
        return False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_sheet_handler(handler_type: str = "excel", **kwargs) -> SheetHandler:
    """
    Factory function to get the appropriate sheet handler.

    handler_type:
        "excel"   — local Excel file (kwargs: file_path)
        "gsheets" — Google Sheets via service account (kwargs: sheet_id, credentials_json)
    """
    if handler_type.lower() == "excel":
        if "file_path" not in kwargs:
            raise ValueError("file_path is required for Excel handler")
        return ExcelHandler(kwargs["file_path"])
    elif handler_type.lower() == "gsheets":
        if "sheet_id" not in kwargs or "credentials_json" not in kwargs:
            raise ValueError("sheet_id and credentials_json are required for GSheetHandler")
        return GSheetHandler(kwargs["sheet_id"], kwargs["credentials_json"])
    else:
        raise ValueError(f"Unknown handler type: {handler_type}")
