"""
Sheet handler module for reading/writing bowling league data.
Supports both Google Sheets API and local Excel files.
"""
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import openpyxl
from openpyxl import load_workbook

# Google Sheets imports (optional, will fail gracefully if not configured)
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False


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
    """Handler for local Excel files."""
    
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
    
    def _find_team_row(self, sheet, team_name: str, start_row: int = 2) -> Optional[int]:
        """Find the row number for a team in the standings section."""
        # Teams are typically in column B starting around row 3
        for row in range(start_row, min(start_row + 20, sheet.max_row + 1)):
            cell_value = sheet.cell(row=row, column=2).value
            if cell_value and isinstance(cell_value, str):
                if team_name.lower() in cell_value.lower() or cell_value.lower() in team_name.lower():
                    return row
        return None
    
    def _find_player_row(self, sheet, player_name: str, start_row: int = 13) -> Optional[int]:
        """Find the row number for a player in the player scores section."""
        # Players are typically in column C starting around row 13-14
        for row in range(start_row, sheet.max_row + 1):
            cell_value = sheet.cell(row=row, column=3).value
            if cell_value and isinstance(cell_value, str):
                if player_name.lower() in cell_value.lower() or cell_value.lower() in player_name.lower():
                    return row
        return None
    
    def get_team_scores(self, team_name: Optional[str] = None, season: Optional[str] = None) -> Dict:
        """Get team scores from Excel."""
        if season is None:
            season = self._get_current_season()
        
        if season not in self.workbook.sheetnames:
            return {"error": f"Season '{season}' not found"}
        
        sheet = self.workbook[season]
        results = {}
        
        # Find team standings section (usually starts around row 2-3)
        start_row = 2
        for row in range(start_row, min(start_row + 15, sheet.max_row + 1)):
            team_cell = sheet.cell(row=row, column=2).value
            if team_cell and isinstance(team_cell, str) and team_cell.strip():
                # Check if this is a team name (not a header)
                if team_cell.lower() not in ['team', 'wins', 'losses', 'ties']:
                    wins = sheet.cell(row=row, column=3).value
                    losses = sheet.cell(row=row, column=4).value
                    ties = sheet.cell(row=row, column=5).value
                    pins_for = sheet.cell(row=row, column=6).value
                    pins_against = sheet.cell(row=row, column=7).value
                    avg_per_game = sheet.cell(row=row, column=8).value
                    
                    team_data = {
                        "wins": wins if wins is not None else 0,
                        "losses": losses if losses is not None else 0,
                        "ties": ties if ties is not None else 0,
                        "pins_for": pins_for if pins_for is not None else 0,
                        "pins_against": pins_against if pins_against is not None else 0,
                        "avg_per_game": avg_per_game if avg_per_game is not None else 0
                    }
                    
                    if team_name is None:
                        results[team_cell] = team_data
                    elif team_name.lower() in team_cell.lower() or team_cell.lower() in team_name.lower():
                        return {"team": team_cell, **team_data}
        
        if team_name:
            return {"error": f"Team '{team_name}' not found in {season}"}
        
        return results
    
    def get_player_scores(self, player_name: Optional[str] = None, season: Optional[str] = None) -> Dict:
        """Get player scores from Excel."""
        if season is None:
            season = self._get_current_season()
        
        if season not in self.workbook.sheetnames:
            return {"error": f"Season '{season}' not found"}
        
        sheet = self.workbook[season]
        results = {}
        
        # Find player scores section (usually starts around row 13-14)
        start_row = 13
        current_team = None
        
        for row in range(start_row, sheet.max_row + 1):
            team_cell = sheet.cell(row=row, column=2).value
            player_cell = sheet.cell(row=row, column=3).value
            
            # Update current team if found
            if team_cell and isinstance(team_cell, str) and team_cell.strip():
                if team_cell.lower() not in ['team', 'player', 'team averages']:
                    current_team = team_cell
            
            # Check for player name
            if player_cell and isinstance(player_cell, str) and player_cell.strip():
                if player_cell.lower() not in ['player', 'team averages', 'average']:
                    # Get scores for this player (weeks are typically in columns 4+)
                    scores = []
                    for col in range(4, min(20, sheet.max_column + 1)):
                        score = sheet.cell(row=row, column=col).value
                        if score is not None:
                            try:
                                scores.append(float(score))
                            except (ValueError, TypeError):
                                pass
                    
                    player_data = {
                        "team": current_team,
                        "scores": scores,
                        "average": sum(scores) / len(scores) if scores else 0
                    }
                    
                    if player_name is None:
                        results[player_cell] = player_data
                    elif player_name.lower() in player_cell.lower() or player_cell.lower() in player_name.lower():
                        return {"player": player_cell, **player_data}
        
        if player_name:
            return {"error": f"Player '{player_name}' not found in {season}"}
        
        return results
    
    def add_score(self, player_name: str, score: int, week: Optional[int] = None, season: Optional[str] = None) -> bool:
        """Add a score for a player. Note: This modifies the Excel file."""
        if season is None:
            season = self._get_current_season()
        
        if season not in self.workbook.sheetnames:
            return False
        
        sheet = self.workbook[season]
        
        # Find the player
        player_row = self._find_player_row(sheet, player_name)
        if not player_row:
            return False
        
        # Determine which column to write to (week column)
        # Weeks typically start at column 4 (D)
        if week is None:
            # Find the first empty week column
            for col in range(4, sheet.max_column + 1):
                cell_value = sheet.cell(row=player_row, column=col).value
                if cell_value is None or cell_value == "":
                    sheet.cell(row=player_row, column=col, value=score)
                    self.workbook.save(self.file_path)
                    return True
        else:
            # Write to specific week column (week 1 = column 4, week 2 = column 5, etc.)
            col = 3 + week
            sheet.cell(row=player_row, column=col, value=score)
            self.workbook.save(self.file_path)
            return True
        
        return False


class GoogleSheetsHandler(SheetHandler):
    """Handler for Google Sheets API."""
    
    def __init__(self, spreadsheet_id: str, credentials_path: Optional[str] = None):
        if not GSPREAD_AVAILABLE:
            raise ImportError("gspread and google-auth are required for Google Sheets support")
        
        self.spreadsheet_id = spreadsheet_id
        
        # Initialize credentials
        if credentials_path:
            scope = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file(credentials_path, scopes=scope)
            self.client = gspread.authorize(creds)
        else:
            # Try to use environment variable or default credentials
            self.client = gspread.service_account()
        
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)
    
    def get_seasons(self) -> List[str]:
        """Get list of available season sheet names."""
        return [sheet.title for sheet in self.spreadsheet.worksheets() if sheet.title.startswith('Season')]
    
    def _get_current_season(self) -> str:
        """Get the most recent season."""
        seasons = self.get_seasons()
        if not seasons:
            return None
        seasons.sort(key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 0, reverse=True)
        return seasons[0]
    
    def get_team_scores(self, team_name: Optional[str] = None, season: Optional[str] = None) -> Dict:
        """Get team scores from Google Sheets."""
        if season is None:
            season = self._get_current_season()
        
        try:
            worksheet = self.spreadsheet.worksheet(season)
        except gspread.exceptions.WorksheetNotFound:
            return {"error": f"Season '{season}' not found"}
        
        # Get all values
        all_values = worksheet.get_all_values()
        
        results = {}
        # Find team standings (usually around row 2-3)
        for i, row in enumerate(all_values[1:15], start=2):
            if len(row) > 1 and row[1] and row[1].strip():
                team = row[1].strip()
                if team.lower() not in ['team', 'wins', 'losses', 'ties']:
                    try:
                        team_data = {
                            "wins": int(row[2]) if len(row) > 2 and row[2] else 0,
                            "losses": int(row[3]) if len(row) > 3 and row[3] else 0,
                            "ties": int(row[4]) if len(row) > 4 and row[4] else 0,
                            "pins_for": int(row[5]) if len(row) > 5 and row[5] else 0,
                            "pins_against": int(row[6]) if len(row) > 6 and row[6] else 0,
                            "avg_per_game": float(row[7]) if len(row) > 7 and row[7] else 0
                        }
                        
                        if team_name is None:
                            results[team] = team_data
                        elif team_name.lower() in team.lower() or team.lower() in team_name.lower():
                            return {"team": team, **team_data}
                    except (ValueError, IndexError):
                        continue
        
        if team_name:
            return {"error": f"Team '{team_name}' not found in {season}"}
        
        return results
    
    def get_player_scores(self, player_name: Optional[str] = None, season: Optional[str] = None) -> Dict:
        """Get player scores from Google Sheets."""
        if season is None:
            season = self._get_current_season()
        
        try:
            worksheet = self.spreadsheet.worksheet(season)
        except gspread.exceptions.WorksheetNotFound:
            return {"error": f"Season '{season}' not found"}
        
        all_values = worksheet.get_all_values()
        results = {}
        current_team = None
        
        # Find player scores (usually around row 13+)
        for i, row in enumerate(all_values[12:], start=13):
            if len(row) > 1:
                team = row[1].strip() if len(row) > 1 and row[1] else None
                if team and team.lower() not in ['team', 'player', 'team averages']:
                    current_team = team
                
                if len(row) > 2 and row[2]:
                    player = row[2].strip()
                    if player.lower() not in ['player', 'team averages', 'average']:
                        # Get scores
                        scores = []
                        for col_idx in range(3, min(len(row), 20)):
                            if row[col_idx]:
                                try:
                                    scores.append(float(row[col_idx]))
                                except ValueError:
                                    pass
                        
                        player_data = {
                            "team": current_team,
                            "scores": scores,
                            "average": sum(scores) / len(scores) if scores else 0
                        }
                        
                        if player_name is None:
                            results[player] = player_data
                        elif player_name.lower() in player.lower() or player.lower() in player_name.lower():
                            return {"player": player, **player_data}
        
        if player_name:
            return {"error": f"Player '{player_name}' not found in {season}"}
        
        return results
    
    def add_score(self, player_name: str, score: int, week: Optional[int] = None, season: Optional[str] = None) -> bool:
        """Add a score for a player in Google Sheets."""
        if season is None:
            season = self._get_current_season()
        
        try:
            worksheet = self.spreadsheet.worksheet(season)
        except gspread.exceptions.WorksheetNotFound:
            return False
        
        # Find player row
        all_values = worksheet.get_all_values()
        player_row = None
        
        for i, row in enumerate(all_values[12:], start=13):
            if len(row) > 2 and row[2]:
                player = row[2].strip()
                if player_name.lower() in player.lower() or player.lower() in player_name.lower():
                    player_row = i + 1  # gspread uses 1-based indexing
                    break
        
        if not player_row:
            return False
        
        # Determine column
        if week is None:
            # Find first empty column
            row_values = worksheet.row_values(player_row)
            for col_idx in range(4, len(row_values) + 5):
                try:
                    cell_value = worksheet.cell(player_row, col_idx).value
                    if not cell_value or cell_value == "":
                        worksheet.update_cell(player_row, col_idx, score)
                        return True
                except:
                    worksheet.update_cell(player_row, col_idx, score)
                    return True
        else:
            col = 3 + week
            worksheet.update_cell(player_row, col, score)
            return True
        
        return False


def get_sheet_handler(handler_type: str = "excel", **kwargs) -> SheetHandler:
    """
    Factory function to get the appropriate sheet handler.
    
    Args:
        handler_type: "excel" or "googlesheets"
        **kwargs: Arguments for the handler
            - For Excel: file_path (required)
            - For Google Sheets: spreadsheet_id (required), credentials_path (optional)
    
    Returns:
        SheetHandler instance
    """
    if handler_type.lower() == "excel":
        if "file_path" not in kwargs:
            raise ValueError("file_path is required for Excel handler")
        return ExcelHandler(kwargs["file_path"])
    elif handler_type.lower() in ["googlesheets", "google", "gsheets"]:
        if "spreadsheet_id" not in kwargs:
            raise ValueError("spreadsheet_id is required for Google Sheets handler")
        return GoogleSheetsHandler(
            kwargs["spreadsheet_id"],
            kwargs.get("credentials_path")
        )
    else:
        raise ValueError(f"Unknown handler type: {handler_type}")

