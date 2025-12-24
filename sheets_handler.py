"""
Sheet handler module for reading/writing bowling league data.
Supports local Excel files with one row per week per player structure.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from openpyxl import load_workbook


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
        """Safely convert to float."""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        return default
    
    def _safe_int(self, value, default=0):
        """Safely convert to int."""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except (ValueError, TypeError):
                return default
        return default
    
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
            if week is not None:
                if self._safe_int(row_week, 0) != week:
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
                if team_name.lower() in team.lower() or team.lower() in team_name.lower():
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
            elif team_name.lower() in team.lower() or team.lower() in team_name.lower():
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
                if team_name.lower() in row_team.strip().lower() or row_team.strip().lower() in team_name.lower():
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
            # We'll aggregate these by team and week below
            if row_week is not None:
                week = self._safe_int(row_week, 0)
                if week > 0 and week_total > 0:
                    team_weekly_totals.append((team, week, week_total))
        
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
        
        # Sort player weekly totals (highest first)
        player_weekly_totals.sort(key=lambda x: x[3], reverse=True)
        top_player_weeks = player_weekly_totals[:10]  # (player, team, week, total, num_games)
        
        # Aggregate team weekly totals (sum all players for each team/week)
        team_week_dict = {}  # (team, week) -> total
        for team, week, total in team_weekly_totals:
            key = (team, week)
            if key not in team_week_dict:
                team_week_dict[key] = 0
            team_week_dict[key] += total
        
        # Convert to list and sort
        team_totals_list = [(team, week, total) for (team, week), total in team_week_dict.items()]
        team_totals_list.sort(key=lambda x: x[2], reverse=True)
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
                if player_name.lower() in player.lower() or player.lower() in player_name.lower():
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
            elif player_name.lower() in player.lower() or player.lower() in player_name.lower():
                return {"player": player, **result_data}
        
        if player_name:
            if week is not None:
                return {"error": f"Player '{player_name}' not found in Week {week} of {season}"}
            return {"error": f"Player '{player_name}' not found in {season}"}
        
        return results
    
    def add_score(self, player_name: str, score: int, week: Optional[int] = None, season: Optional[str] = None) -> bool:
        """Add a score for a player. Note: This modifies the Excel file."""
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
    
    def get_seasons(self) -> List[str]:
        """Get list of available season sheet names."""
        return [sheet for sheet in self.workbook.sheetnames if sheet.startswith('Season')]


def get_sheet_handler(handler_type: str = "excel", **kwargs) -> SheetHandler:
    """
    Factory function to get the appropriate sheet handler.
    
    Args:
        handler_type: "excel"
        **kwargs: Arguments for the handler
            - For Excel: file_path (required)
    
    Returns:
        SheetHandler instance
    """
    if handler_type.lower() == "excel":
        if "file_path" not in kwargs:
            raise ValueError("file_path is required for Excel handler")
        return ExcelHandler(kwargs["file_path"])
    else:
        raise ValueError(f"Unknown handler type: {handler_type}")
