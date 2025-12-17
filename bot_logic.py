"""
Bot logic for handling commands and generating responses.
"""
from typing import Dict, Optional
from sheets_handler import SheetHandler
from command_parser import Command, CommandType


class BotLogic:
    """Handles bot command execution and response generation."""
    
    def __init__(self, sheet_handler: SheetHandler):
        self.sheet_handler = sheet_handler
    
    def _safe_float(self, value, default=0.0):
        """Safely convert a value to float, handling strings and None."""
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
        """Safely convert a value to int, handling strings and None."""
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
    
    def handle_command(self, command: Command, season: Optional[str] = None) -> str:
        """
        Execute a command and return a formatted response.
        
        Args:
            command: The parsed command
            season: Optional season to query (defaults to current, overridden by command params)
            
        Returns:
            Formatted response string
        """
        # Get season from command params if specified, otherwise use passed season
        command_season = command.params.get("season", season)
        
        if command.command_type == CommandType.HELP:
            from command_parser import CommandParser
            parser = CommandParser()
            return parser.get_help_message()
        
        elif command.command_type == CommandType.LIST_SEASONS:
            return self._handle_list_seasons()
        
        elif command.command_type == CommandType.TEAM_SCORES:
            return self._handle_team_scores(command.params.get("team_name"), command_season)
        
        elif command.command_type == CommandType.PLAYER_SCORES:
            return self._handle_player_scores(command.params.get("player_name"), command_season)
        
        elif command.command_type == CommandType.ADD_SCORE:
            return self._handle_add_score(
                command.params.get("player_name"),
                command.params.get("score"),
                command.params.get("week"),
                command_season
            )
        
        else:
            return "❓ I didn't understand that command. Type `help` for available commands."
    
    def _handle_team_scores(self, team_name: Optional[str], season: Optional[str]) -> str:
        """Handle team scores query."""
        try:
            data = self.sheet_handler.get_team_scores(team_name, season)
            
            if "error" in data:
                error_msg = f"❌ {data['error']}"
                if season:
                    error_msg += f" (Season: {season})"
                return error_msg
            
            if team_name:
                # Single team
                team = data.get("team", team_name)
                wins = self._safe_int(data.get("wins", 0))
                losses = self._safe_int(data.get("losses", 0))
                ties = self._safe_int(data.get("ties", 0))
                avg = self._safe_float(data.get("avg_per_game", 0))
                pins_for = self._safe_int(data.get("pins_for", 0))
                
                response = f"🏆 *{team}*"
                if season:
                    response += f" ({season})"
                response += f"\n\n"
                response += f"📊 Record: {wins}-{losses}"
                if ties > 0:
                    response += f"-{ties}"
                response += f"\n"
                response += f"📈 Avg per game: {avg:.1f}\n"
                response += f"🎳 Total pins: {pins_for}"
                
                return response
            else:
                # All teams
                if not data:
                    error_msg = "❌ No team data found."
                    if season:
                        error_msg += f" (Season: {season})"
                    return error_msg
                
                response = "🏆 *Team Standings*"
                if season:
                    response += f" ({season})"
                response += "\n\n"
                # Sort by wins (or win percentage)
                sorted_teams = sorted(
                    data.items(),
                    key=lambda x: (self._safe_int(x[1].get("wins", 0)), -self._safe_int(x[1].get("losses", 0))),
                    reverse=True
                )
                
                for i, (team, stats) in enumerate(sorted_teams, 1):
                    wins = self._safe_int(stats.get("wins", 0))
                    losses = self._safe_int(stats.get("losses", 0))
                    ties = self._safe_int(stats.get("ties", 0))
                    avg = self._safe_float(stats.get("avg_per_game", 0))
                    
                    record = f"{wins}-{losses}"
                    if ties > 0:
                        record += f"-{ties}"
                    
                    response += f"{i}. *{team}*\n"
                    response += f"   {record} | Avg: {avg:.1f}\n\n"
                
                return response.strip()
        
        except Exception as e:
            return f"❌ Error retrieving team scores: {str(e)}"
    
    def _handle_player_scores(self, player_name: Optional[str], season: Optional[str]) -> str:
        """Handle player scores query."""
        try:
            data = self.sheet_handler.get_player_scores(player_name, season)
            
            if "error" in data:
                error_msg = f"❌ {data['error']}"
                if season:
                    error_msg += f" (Season: {season})"
                return error_msg
            
            if player_name:
                # Single player
                player = data.get("player", player_name)
                team = data.get("team", "Unknown")
                scores = data.get("scores", [])
                # Safely convert scores to floats, then to ints for display
                scores_clean = [self._safe_float(s) for s in scores if s is not None]
                avg = self._safe_float(data.get("average", 0))
                
                response = f"🎳 *{player}*"
                if season:
                    response += f" ({season})"
                response += f"\n"
                response += f"Team: {team}\n\n"
                
                if scores_clean:
                    response += f"📊 Average: {avg:.1f}\n"
                    response += f"🎯 Scores: {', '.join(map(str, [int(s) for s in scores_clean]))}\n"
                    response += f"📈 Games: {len(scores_clean)}"
                else:
                    response += "No scores recorded yet."
                
                return response
            else:
                # All players (could be large, maybe limit?)
                if not data:
                    error_msg = "❌ No player data found."
                    if season:
                        error_msg += f" (Season: {season})"
                    return error_msg
                
                response = "🎳 *Player Scores*"
                if season:
                    response += f" ({season})"
                response += "\n\n"
                # Sort by average
                sorted_players = sorted(
                    data.items(),
                    key=lambda x: self._safe_float(x[1].get("average", 0)),
                    reverse=True
                )
                
                for i, (player, stats) in enumerate(sorted_players[:20], 1):  # Limit to top 20
                    avg = self._safe_float(stats.get("average", 0))
                    team = stats.get("team", "Unknown")
                    scores_list = stats.get("scores", [])
                    games = len([s for s in scores_list if s is not None])
                    
                    response += f"{i}. *{player}* ({team})\n"
                    response += f"   Avg: {avg:.1f} | Games: {games}\n\n"
                
                if len(sorted_players) > 20:
                    response += f"... and {len(sorted_players) - 20} more players"
                
                return response.strip()
        
        except Exception as e:
            return f"❌ Error retrieving player scores: {str(e)}"
    
    def _handle_list_seasons(self) -> str:
        """Handle listing available seasons."""
        try:
            seasons = self.sheet_handler.get_seasons()
            if not seasons:
                return "❌ No seasons found."
            
            # Sort seasons by number (extract number from "Season N")
            def get_season_num(season_name):
                try:
                    return int(season_name.split()[-1])
                except (ValueError, IndexError):
                    return 0
            
            sorted_seasons = sorted(seasons, key=get_season_num, reverse=True)
            
            response = "📅 *Available Seasons:*\n\n"
            for i, season in enumerate(sorted_seasons, 1):
                response += f"{i}. {season}\n"
            
            response += f"\nUse `season [N]` or `s[N]` with any command to query a specific season."
            
            return response
        
        except Exception as e:
            return f"❌ Error retrieving seasons: {str(e)}"
    
    def _handle_add_score(self, player_name: Optional[str], score: Optional[int], 
                         week: Optional[int], season: Optional[str]) -> str:
        """Handle adding a score."""
        if not player_name:
            return "❌ Please specify a player name. Example: `add score 150 John`"
        
        if score is None:
            return "❌ Please specify a score. Example: `add score 150 John`"
        
        if not (0 <= score <= 300):
            return "❌ Invalid score. Scores must be between 0 and 300."
        
        try:
            success = self.sheet_handler.add_score(player_name, score, week, season)
            
            if success:
                week_text = f" (Week {week})" if week else ""
                return f"✅ Score of {score} added for {player_name}{week_text}!"
            else:
                return f"❌ Could not add score. Player '{player_name}' not found or error occurred."
        
        except Exception as e:
            return f"❌ Error adding score: {str(e)}"

