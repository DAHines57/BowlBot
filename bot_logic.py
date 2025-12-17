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
        
        elif command.command_type == CommandType.LIST_PLAYERS:
            return self._handle_list_players(command_season)
        
        elif command.command_type == CommandType.LIST_TEAMS:
            return self._handle_list_teams(command_season)
        
        elif command.command_type == CommandType.STATS:
            return self._handle_stats(command_season)
        
        elif command.command_type == CommandType.PLAYER_AVERAGES:
            return self._handle_player_averages(command_season)
        
        elif command.command_type == CommandType.BEST_PLAYER_WEEKS:
            return self._handle_best_player_weeks(command_season)
        
        elif command.command_type == CommandType.BEST_TEAM_WEEKS:
            return self._handle_best_team_weeks(command_season)
        
        elif command.command_type == CommandType.BEST_GAMES:
            return self._handle_best_games(command_season)
        
        elif command.command_type == CommandType.TEAM_SCORES:
            return self._handle_team_scores(
                command.params.get("team_name"), 
                command_season,
                command.params.get("week")
            )
        
        elif command.command_type == CommandType.TEAM_RECORD:
            return self._handle_team_record(command.params.get("team_name"), command_season)
        
        elif command.command_type == CommandType.PLAYER_SCORES:
            return self._handle_player_scores(
                command.params.get("player_name"), 
                command_season,
                command.params.get("week")
            )
        
        elif command.command_type == CommandType.ADD_SCORE:
            return self._handle_add_score(
                command.params.get("player_name"),
                command.params.get("score"),
                command.params.get("week"),
                command_season
            )
        
        else:
            return "❓ I didn't understand that command. Type `help` for available commands."
    
    def _handle_team_scores(self, team_name: Optional[str], season: Optional[str], week: Optional[int] = None) -> str:
        """Handle team scores query."""
        try:
            data = self.sheet_handler.get_team_scores(team_name, season, week)
            
            if "error" in data:
                error_msg = f"❌ {data['error']}"
                if season:
                    error_msg += f" (Season: {season})"
                if week:
                    error_msg += f" (Week: {week})"
                return error_msg
            
            if team_name:
                # Single team
                team = data.get("team", team_name)
                
                # If week is specified, show individual games for that week
                if week is not None:
                    week_data = data.get("week_data")
                    if not week_data:
                        return f"❌ No data found for {team} in Week {week}"
                    
                    response = f"🏆 *{team}* - Week {week}"
                    if season:
                        response += f" ({season})"
                    response += f"\n\n"
                    
                    opponent = week_data.get("opponent", "Unknown")
                    players_games = week_data.get("players", {})
                    week_wins = self._safe_int(week_data.get("wins", 0))
                    week_losses = self._safe_int(week_data.get("losses", 0))
                    week_ties = self._safe_int(week_data.get("ties", 0))
                    
                    response += f"vs {opponent}\n"
                    record_str = f"{week_wins}-{week_losses}"
                    if week_ties > 0:
                        record_str += f"-{week_ties}"
                    response += f"📊 Record: {record_str}\n\n"
                    response += f"👥 *Players:*\n"
                    
                    for player, games in sorted(players_games.items()):
                        games_clean = [self._safe_float(g) for g in games if g > 0]
                        if games_clean:
                            avg = sum(games_clean) / len(games_clean)
                            games_str = ", ".join([str(int(g)) for g in games_clean])
                            response += f"  • {player}: {games_str} (Avg: {avg:.1f})\n"
                    
                    team_total = week_data.get("total", 0)
                    response += f"\n🎳 Team Total: {int(team_total)}"
                    
                    return response
                
                # No week specified - show season stats
                wins = self._safe_int(data.get("wins", 0))
                losses = self._safe_int(data.get("losses", 0))
                ties = self._safe_int(data.get("ties", 0))
                avg = self._safe_float(data.get("avg_per_game", 0))
                pins_for = self._safe_int(data.get("pins_for", 0))
                players = data.get("players", {})
                
                response = f"🏆 *{team}*"
                if season:
                    response += f" ({season})"
                response += f"\n\n"
                response += f"📊 Record: {wins}-{losses}"
                if ties > 0:
                    response += f"-{ties}"
                response += f"\n"
                response += f"📈 Team Average: {avg:.1f}\n"
                response += f"🎳 Total pins: {pins_for}\n\n"
                
                # Add players and their averages
                if players:
                    response += f"👥 *Players:*\n"
                    # Sort players by average (descending)
                    sorted_players = sorted(players.items(), key=lambda x: x[1], reverse=True)
                    for player, player_avg in sorted_players:
                        response += f"  • {player}: {player_avg:.1f}\n"
                
                return response.strip()
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
    
    def _handle_team_record(self, team_name: Optional[str], season: Optional[str]) -> str:
        """Handle team weekly record query."""
        if not team_name:
            return "❌ Please specify a team name. Example: `team Pin Seekers record`"
        
        try:
            data = self.sheet_handler.get_team_weekly_summary(team_name, season)
            
            if "error" in data:
                error_msg = f"❌ {data['error']}"
                if season:
                    error_msg += f" (Season: {season})"
                return error_msg
            
            team = data.get("team", team_name)
            season_str = data.get("season", season or "Current Season")
            weekly_summary = data.get("weekly_summary", {})
            
            if not weekly_summary:
                return f"❌ No weekly data found for {team}"
            
            # Calculate total W-L-T
            total_wins = sum(week_info.get("wins", 0) for week_info in weekly_summary.values())
            total_losses = sum(week_info.get("losses", 0) for week_info in weekly_summary.values())
            total_ties = sum(week_info.get("ties", 0) for week_info in weekly_summary.values())
            
            response = f"📊 *{team} Weekly Record*"
            if season_str:
                response += f" ({season_str})"
            response += "\n\n"
            response += f"*Total Record: {total_wins}-{total_losses}"
            if total_ties > 0:
                response += f"-{total_ties}"
            response += "*\n\n"
            
            # Sort by week
            for week in sorted(weekly_summary.keys()):
                week_info = weekly_summary[week]
                opponent = week_info.get("opponent", "Unknown")
                wins = week_info.get("wins", 0)
                losses = week_info.get("losses", 0)
                ties = week_info.get("ties", 0)
                pins_for = week_info.get("pins_for", 0)
                pins_against = week_info.get("pins_against", 0)
                avg = week_info.get("avg", 0)
                
                record = f"{wins}-{losses}"
                if ties > 0:
                    record += f"-{ties}"
                
                response += f"*Week {week}* vs {opponent}\n"
                response += f"  {record} | {pins_for} - {pins_against} | Avg: {avg:.1f}\n\n"
            
            return response.strip()
        
        except Exception as e:
            return f"❌ Error retrieving team record: {str(e)}"
    
    def _handle_stats(self, season: Optional[str]) -> str:
        """Handle league statistics query."""
        try:
            data = self.sheet_handler.get_league_stats(season)
            
            if "error" in data:
                error_msg = f"❌ {data['error']}"
                if season:
                    error_msg += f" (Season: {season})"
                return error_msg
            
            season_str = data.get("season", season or "Current Season")
            player_averages = data.get("player_averages", [])
            top_player_weeks = data.get("top_player_weeks", [])
            top_team_totals = data.get("top_team_totals", [])
            top_games = data.get("top_games", [])
            
            response = f"📊 *League Statistics*"
            if season_str:
                response += f" ({season_str})"
            response += "\n\n"
            
            # Player averages (all players sorted)
            response += "🏆 *Player Averages:*\n"
            for i, player_data in enumerate(player_averages, 1):
                player = player_data["player"]
                team = player_data["team"]
                avg = player_data["average"]
                games = player_data["games"]
                response += f"{i}. {player} ({team}): {avg:.1f} ({games} games)\n"
            
            response += "\n"
            
            # Top 10 player weeks
            response += "⭐ *Top 10 Individual Player Weeks:*\n"
            for i, (player, team, week, total) in enumerate(top_player_weeks, 1):
                response += f"{i}. {player} ({team}) - Week {week}: {int(total)} pins\n"
            
            response += "\n"
            
            # Top 5 team totals
            response += "🏅 *Top 5 Team Weekly Totals:*\n"
            for i, (team, week, total) in enumerate(top_team_totals, 1):
                response += f"{i}. {team} - Week {week}: {int(total)} pins\n"
            
            response += "\n"
            
            # Top 10 individual games
            response += "🎯 *Top 10 Individual Games:*\n"
            for i, (player, team, week, score) in enumerate(top_games, 1):
                response += f"{i}. {player} ({team}) - Week {week}: {int(score)}\n"
            
            return response.strip()
        
        except Exception as e:
            return f"❌ Error retrieving statistics: {str(e)}"
    
    def _handle_player_averages(self, season: Optional[str]) -> str:
        """Handle player averages query."""
        try:
            data = self.sheet_handler.get_league_stats(season)
            
            if "error" in data:
                error_msg = f"❌ {data['error']}"
                if season:
                    error_msg += f" (Season: {season})"
                return error_msg
            
            season_str = data.get("season", season or "Current Season")
            player_averages = data.get("player_averages", [])
            
            response = f"🏆 *Player Averages*"
            if season_str:
                response += f" ({season_str})"
            response += "\n\n"
            
            for i, player_data in enumerate(player_averages, 1):
                player = player_data["player"]
                team = player_data["team"]
                avg = player_data["average"]
                games = player_data["games"]
                response += f"{i}. {player} ({team}): {avg:.1f} ({games} games)\n"
            
            return response.strip()
        
        except Exception as e:
            return f"❌ Error retrieving player averages: {str(e)}"
    
    def _handle_best_player_weeks(self, season: Optional[str]) -> str:
        """Handle best player weeks query."""
        try:
            data = self.sheet_handler.get_league_stats(season)
            
            if "error" in data:
                error_msg = f"❌ {data['error']}"
                if season:
                    error_msg += f" (Season: {season})"
                return error_msg
            
            season_str = data.get("season", season or "Current Season")
            top_player_weeks = data.get("top_player_weeks", [])
            player_averages = data.get("player_averages", [])
            
            # Create a lookup for player averages
            avg_lookup = {p["player"]: p["average"] for p in player_averages}
            
            response = f"⭐ *Top 10 Individual Player Weeks*"
            if season_str:
                response += f" ({season_str})"
            response += "\n\n"
            
            for i, week_data in enumerate(top_player_weeks, 1):
                if len(week_data) == 5:
                    player, team, week, total, num_games = week_data
                else:
                    # Fallback for old format
                    player, team, week, total = week_data
                    num_games = 4  # Default estimate
                
                avg = avg_lookup.get(player, 0)
                # Calculate average for this week
                week_avg = total / num_games if num_games > 0 else 0
                response += f"{i}. {player} ({team}) - Week {week}: {int(total)} pins (Week Avg: {week_avg:.1f}, Season Avg: {avg:.1f})\n"
            
            return response.strip()
        
        except Exception as e:
            return f"❌ Error retrieving best player weeks: {str(e)}"
    
    def _handle_best_team_weeks(self, season: Optional[str]) -> str:
        """Handle best team weeks query."""
        try:
            data = self.sheet_handler.get_league_stats(season)
            
            if "error" in data:
                error_msg = f"❌ {data['error']}"
                if season:
                    error_msg += f" (Season: {season})"
                return error_msg
            
            season_str = data.get("season", season or "Current Season")
            top_team_totals = data.get("top_team_totals", [])
            
            response = f"🏅 *Top 5 Team Weekly Totals*"
            if season_str:
                response += f" ({season_str})"
            response += "\n\n"
            
            for i, (team, week, total) in enumerate(top_team_totals, 1):
                response += f"{i}. {team} - Week {week}: {int(total)} pins\n"
            
            return response.strip()
        
        except Exception as e:
            return f"❌ Error retrieving best team weeks: {str(e)}"
    
    def _handle_best_games(self, season: Optional[str]) -> str:
        """Handle best games query."""
        try:
            data = self.sheet_handler.get_league_stats(season)
            
            if "error" in data:
                error_msg = f"❌ {data['error']}"
                if season:
                    error_msg += f" (Season: {season})"
                return error_msg
            
            season_str = data.get("season", season or "Current Season")
            top_games = data.get("top_games", [])
            
            response = f"🎯 *Top 10 Highest Individual Games*"
            if season_str:
                response += f" ({season_str})"
            response += "\n\n"
            
            for i, (player, team, week, score) in enumerate(top_games, 1):
                response += f"{i}. {player} ({team}) - Week {week}: {int(score)}\n"
            
            return response.strip()
        
        except Exception as e:
            return f"❌ Error retrieving best games: {str(e)}"
    
    def _handle_player_scores(self, player_name: Optional[str], season: Optional[str], week: Optional[int] = None) -> str:
        """Handle player scores query."""
        try:
            data = self.sheet_handler.get_player_scores(player_name, season, week)
            
            if "error" in data:
                error_msg = f"❌ {data['error']}"
                if season:
                    error_msg += f" (Season: {season})"
                if week:
                    error_msg += f" (Week: {week})"
                return error_msg
            
            if player_name:
                # Single player
                player = data.get("player", player_name)
                team = data.get("team", "Unknown")
                
                # If week is specified, show individual games for that week
                if week is not None:
                    week_data = data.get("week_data")
                    if not week_data:
                        return f"❌ No data found for {player} in Week {week}"
                    
                    response = f"🎳 *{player}* - Week {week}"
                    if season:
                        response += f" ({season})"
                    response += f"\n"
                    response += f"Team: {team}\n\n"
                    
                    games = week_data.get("games", [])
                    week_avg = week_data.get("average", 0)
                    is_absent = week_data.get("absent", False)
                    
                    if games:
                        games_clean = [int(self._safe_float(g)) for g in games]
                        total = sum(games_clean)
                        response += f"🎯 Games: {', '.join(map(str, games_clean))}\n"
                        response += f"📊 Week Average: {week_avg:.1f}\n"
                        response += f"🎳 Total: {total}"
                        if is_absent:
                            response += f"\n⚠️ Absent (average used)"
                    else:
                        response += "No games recorded for this week."
                    
                    return response
                
                # No week specified - show season stats
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
                    highest = self._safe_int(data.get("highest_game", 0))
                    lowest = self._safe_int(data.get("lowest_game", 0))
                    std_dev = self._safe_float(data.get("std_dev", 0))
                    
                    response += f"📊 Average: {avg:.1f}\n"
                    response += f"📏 Std Dev: {std_dev:.1f}\n"
                    response += f"🎯 Highest Game: {highest}\n"
                    response += f"📉 Lowest Game: {lowest}\n"
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
    
    def _handle_list_players(self, season: Optional[str]) -> str:
        """Handle list players query."""
        try:
            data = self.sheet_handler.get_player_scores(None, season)
            
            if not data:
                error_msg = "❌ No players found."
                if season:
                    error_msg += f" (Season: {season})"
                return error_msg
            
            season_str = season or "Current Season"
            response = f"👥 *All Players*"
            if season_str:
                response += f" ({season_str})"
            response += "\n\n"
            
            # Sort players by average (highest to lowest)
            sorted_players = sorted(data.items(), key=lambda x: self._safe_float(x[1].get("average", 0)), reverse=True)
            
            for player_name, player_data in sorted_players:
                team = player_data.get("team", "Unknown")
                avg = self._safe_float(player_data.get("average", 0))
                games = len(player_data.get("scores", []))
                response += f"• {player_name} ({team}) - Avg: {avg:.1f} ({games} games)\n"
            
            return response.strip()
        
        except Exception as e:
            return f"❌ Error retrieving players: {str(e)}"
    
    def _handle_list_teams(self, season: Optional[str]) -> str:
        """Handle list teams query."""
        try:
            data = self.sheet_handler.get_team_scores(None, season)
            
            if not data:
                error_msg = "❌ No teams found."
                if season:
                    error_msg += f" (Season: {season})"
                return error_msg
            
            season_str = season or "Current Season"
            response = f"🏆 *All Teams*"
            if season_str:
                response += f" ({season_str})"
            response += "\n\n"
            
            # Sort teams by average (highest to lowest)
            sorted_teams = sorted(data.items(), key=lambda x: self._safe_float(x[1].get("avg_per_game", 0)), reverse=True)
            
            for team_name, team_data in sorted_teams:
                wins = self._safe_int(team_data.get("wins", 0))
                losses = self._safe_int(team_data.get("losses", 0))
                ties = self._safe_int(team_data.get("ties", 0))
                avg = self._safe_float(team_data.get("avg_per_game", 0))
                
                record = f"{wins}-{losses}"
                if ties > 0:
                    record += f"-{ties}"
                
                response += f"• {team_name} - {record} | Avg: {avg:.1f}\n"
            
            return response.strip()
        
        except Exception as e:
            return f"❌ Error retrieving teams: {str(e)}"
    
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

