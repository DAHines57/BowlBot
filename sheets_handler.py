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
    def get_team_scores(self, team_name: Optional[str] = None, season: Optional[str] = None) -> Dict:
        """Get team scores. If team_name is None, return all teams."""
        pass
    
    @abstractmethod
    def get_player_scores(self, player_name: Optional[str] = None, season: Optional[str] = None) -> Dict:
        """Get player scores. If player_name is None, return all players."""
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
    
    def get_team_scores(self, team_name: Optional[str] = None, season: Optional[str] = None) -> Dict:
        """Get team scores from Excel. Excludes substitute entries."""
        season_num = self._get_season_number(season)
        if season_num is None:
            return {"error": f"Season '{season}' not found"}
        
        season_sheet = f"Season {season_num}"
        if season_sheet not in self.workbook.sheetnames:
            return {"error": f"Season '{season}' not found"}
        
        sheet = self.workbook[season_sheet]
        results = {}
        team_stats = {}  # team_name -> {total_pins, total_games, pins_against, games_against}
        
        # Column mapping: Team=1, Player=2, Season=3, Week=4, Game1=5, Game2=6, Game3=7, Game4=8, Game5=9, Average=10
        # Read from row 2 onwards (row 1 is headers)
        for row in range(2, sheet.max_row + 1):
            row_team = sheet.cell(row=row, column=1).value
            row_season = sheet.cell(row=row, column=3).value
            substitute = sheet.cell(row=row, column=13).value  # Substitute? column
            
            # Skip if not this season or if substitute
            if row_season != season_num or self._is_substitute(substitute):
                continue
            
            if row_team and isinstance(row_team, str):
                team = row_team.strip()
                
                # Get games (Game 1-5)
                games = []
                for col in range(5, 10):  # Columns 5-9 (Game 1-5)
                    game_score = sheet.cell(row=row, column=col).value
                    if game_score is not None:
                        game_float = self._safe_float(game_score)
                        if game_float > 0:
                            games.append(game_float)
                
                # Calculate week total
                week_total = sum(games)
                
                # Initialize team stats
                if team not in team_stats:
                    team_stats[team] = {
                        "total_pins": 0,
                        "total_games": 0,
                        "pins_against": 0,
                        "games_against": 0
                    }
                
                # Add to team totals
                team_stats[team]["total_pins"] += week_total
                team_stats[team]["total_games"] += len(games)
        
        # Calculate team averages and create results
        for team, stats in team_stats.items():
            total_pins = stats["total_pins"]
            total_games = stats["total_games"]
            avg_per_game = total_pins / total_games if total_games > 0 else 0
            
            # For now, we don't have wins/losses in this structure
            # You might need to add that separately or calculate from matchups
            team_data = {
                "wins": 0,  # Not available in current structure
                "losses": 0,  # Not available in current structure
                "ties": 0,  # Not available in current structure
                "pins_for": int(total_pins),
                "pins_against": 0,  # Would need opponent data
                "avg_per_game": round(avg_per_game, 2)
            }
            
            if team_name is None:
                results[team] = team_data
            elif team_name.lower() in team.lower() or team.lower() in team_name.lower():
                return {"team": team, **team_data}
        
        if team_name:
            return {"error": f"Team '{team_name}' not found in {season}"}
        
        return results
    
    def get_player_scores(self, player_name: Optional[str] = None, season: Optional[str] = None) -> Dict:
        """Get player scores from Excel. Excludes absent weeks from average calculation."""
        season_num = self._get_season_number(season)
        if season_num is None:
            return {"error": f"Season '{season}' not found"}
        
        season_sheet = f"Season {season_num}"
        if season_sheet not in self.workbook.sheetnames:
            return {"error": f"Season '{season}' not found"}
        
        sheet = self.workbook[season_sheet]
        results = {}
        player_data = {}  # player_name -> {team, scores, absent_count}
        
        # Column mapping: Team=1, Player=2, Season=3, Week=4, Game1=5, Game2=6, Game3=7, Game4=8, Game5=9, Average=10
        for row in range(2, sheet.max_row + 1):
            row_team = sheet.cell(row=row, column=1).value
            row_player = sheet.cell(row=row, column=2).value
            row_season = sheet.cell(row=row, column=3).value
            row_week = sheet.cell(row=row, column=4).value
            absent = sheet.cell(row=row, column=12).value  # Absent? column
            
            # Skip if not this season
            if row_season != season_num:
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
                        "weeks": []
                    }
                
                # Get games for this week
                week_games = []
                for col in range(5, 10):  # Columns 5-9 (Game 1-5)
                    game_score = sheet.cell(row=row, column=col).value
                    if game_score is not None:
                        game_float = self._safe_float(game_score)
                        if game_float > 0:
                            week_games.append(game_float)
                
                # Get average for this week (from column 10)
                week_avg = sheet.cell(row=row, column=10).value
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
            
            result_data = {
                "team": data["team"],
                "scores": scores,
                "average": round(avg, 2),
                "weeks_played": len(data["weeks"]) - data["absent_count"],
                "weeks_absent": data["absent_count"]
            }
            
            if player_name is None:
                results[player] = result_data
            elif player_name.lower() in player.lower() or player.lower() in player_name.lower():
                return {"player": player, **result_data}
        
        if player_name:
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
                row_player = sheet.cell(row=row, column=2).value
                row_season = sheet.cell(row=row, column=3).value
                row_week = sheet.cell(row=row, column=4).value
                
                if (row_player and isinstance(row_player, str) and 
                    player_name.lower() in row_player.lower() and 
                    row_season == season_num):
                    week_num = self._safe_int(row_week, 0)
                    if week_num > max_week:
                        max_week = week_num
                        target_row = row
            
            if target_row:
                # Find first empty game column
                for col in range(5, 10):  # Game 1-5 columns
                    game_value = sheet.cell(row=target_row, column=col).value
                    if game_value is None or game_value == "":
                        sheet.cell(row=target_row, column=col, value=score)
                        self.workbook.save(self.file_path)
                        return True
        else:
            # Find specific week for this player
            for row in range(2, sheet.max_row + 1):
                row_player = sheet.cell(row=row, column=2).value
                row_season = sheet.cell(row=row, column=3).value
                row_week = sheet.cell(row=row, column=4).value
                
                if (row_player and isinstance(row_player, str) and 
                    player_name.lower() in row_player.lower() and 
                    row_season == season_num and 
                    self._safe_int(row_week, 0) == week):
                    
                    # Find first empty game column
                    for col in range(5, 10):  # Game 1-5 columns
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
