"""
Bot logic for handling commands and generating responses.
"""
import time
from typing import Dict, Optional
from sheets_handler import SheetHandler
from command_parser import Command, CommandParser, CommandType
from utils import safe_float, safe_int

PENDING_TTL = 60  # seconds before a pending clarification expires


class BotLogic:
    """Handles bot command execution and response generation."""
    
    def __init__(self, sheet_handler: SheetHandler):
        self.sheet_handler = sheet_handler
        self._pending: Dict[str, dict] = {}  # phone -> {command_type, params, options, expires_at}
    
    def _safe_float(self, value, default=0.0):
        return safe_float(value, default)

    def _safe_int(self, value, default=0):
        return safe_int(value, default)
    
    def _normalize(self, text: str) -> str:
        return text.lower().replace('\u2018', "'").replace('\u2019', "'")

    def handle_command(self, command: Command, season: Optional[str] = None,
                       user_phone: Optional[str] = None, raw_message: Optional[str] = None) -> str:
        """
        Execute a command and return a formatted response.
        
        Args:
            command: The parsed command
            season: Optional season to query (defaults to current, overridden by command params)
            user_phone: Sender's phone number, used for pending clarification state
            raw_message: Original raw message text, used to resolve pending clarifications
            
        Returns:
            Formatted response string
        """
        # Check if this user has a pending clarification to resolve
        if user_phone and raw_message:
            resolved = self._resolve_pending(user_phone, raw_message)
            if resolved is not None:
                return resolved

        # Get season from command params if specified, otherwise use passed season
        command_season = command.params.get("season", season)

        # Resolve relative season references
        if command_season == "last":
            seasons = sorted(
                [s for s in self.sheet_handler.get_seasons() if s.startswith("Season")],
                key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 0
            )
            if len(seasons) >= 2:
                command_season = seasons[-2]
            elif seasons:
                command_season = seasons[-1]
            else:
                command_season = None

        # Always resolve to an explicit season name so it shows in every response
        if command_season is None:
            command_season = self.sheet_handler._get_current_season()
        
        if command.command_type == CommandType.HELP:
            parser = CommandParser()
            return parser.get_help_message()
        
        elif command.command_type == CommandType.LIST_SEASONS:
            return self._handle_list_seasons()
        
        elif command.command_type == CommandType.LIST_PLAYERS:
            return self._handle_list_players(command_season)
        
        elif command.command_type == CommandType.LEADERS:
            return self._handle_leaders(command_season)

        elif command.command_type == CommandType.WEEKLY_SUMMARY:
            return self._handle_weekly_summary(command_season, command.params.get("week"))

        elif command.command_type == CommandType.WEEKLY_RESULTS:
            return self._handle_weekly_results(command_season, command.params.get("week"))
        
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
                command.params.get("week"),
                user_phone=user_phone
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
    
    def _store_pending(self, user_phone: str, command_type: CommandType,
                       params: dict, options: list) -> str:
        """Store a pending clarification and return the prompt message."""
        self._pending[user_phone] = {
            "command_type": command_type,
            "params": params,
            "options": options,
            "expires_at": time.time() + PENDING_TTL,
        }
        lines = ["❓ Multiple matches found. Reply with a number to choose:"]
        for i, name in enumerate(options, 1):
            lines.append(f"  {i}. {name}")
        return "\n".join(lines)

    def _resolve_pending(self, user_phone: str, raw_message: str) -> Optional[str]:
        """
        Try to resolve a pending clarification for this user.
        Returns a response string if resolved, None if no pending state or not resolvable.
        """
        pending = self._pending.get(user_phone)
        if not pending:
            return None
        if time.time() > pending["expires_at"]:
            del self._pending[user_phone]
            return None

        options = pending["options"]
        text = raw_message.strip()

        # Match by number (e.g. "1", "2")
        chosen = None
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(options):
                chosen = options[idx]
        else:
            # Match by partial name
            normalized = self._normalize(text)
            hits = [o for o in options if normalized in self._normalize(o)]
            if len(hits) == 1:
                chosen = hits[0]

        if chosen is None:
            return None  # Not a valid selection — let normal parsing handle it

        del self._pending[user_phone]
        params = {**pending["params"], "player_name": chosen}
        command = Command(pending["command_type"], params)
        print(f"[Pending] Resolved to: {chosen}")
        return self.handle_command(command, user_phone=user_phone)

    def _handle_weekly_summary(self, season: Optional[str], week: Optional[int] = None):
        """Generate and return a weekly summary PNG as raw bytes."""
        try:
            from image_generator import build_html, generate_image
            if week is None:
                week = self.sheet_handler.get_latest_week(season)
            data = self.sheet_handler.get_week_summary(week, season)
            if "error" in data:
                return f"❌ {data['error']}"
            if not data.get("players"):
                return f"❌ No data found for Week {week} of {season}."
            html = build_html(data)
            print(f"[Summary] Generating image for {season} Week {week}")
            return generate_image(html)  # returns bytes — main.py sends as image
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"❌ Error generating summary: {str(e)}"

    def _handle_weekly_results(self, season: Optional[str], week: Optional[int] = None):
        """Generate and return a weekly matchup results PNG as raw bytes."""
        try:
            from image_generator import build_matchups_html, generate_image
            if week is None:
                week = self.sheet_handler.get_latest_week(season)
            data = self.sheet_handler.get_week_matchups(week, season)
            if "error" in data:
                return f"❌ {data['error']}"
            if not data.get("matchups"):
                return f"❌ No matchup data found for Week {week} of {season}."
            html = build_matchups_html(data)
            print(f"[Results] Generating matchup image for {season} Week {week}")
            return generate_image(html)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"❌ Error generating results: {str(e)}"

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
                # All teams — image
                if not data:
                    return "❌ No team data found." + (f" ({season})" if season else "")
                from image_generator import build_teams_html, generate_image
                print(f"[Teams] Generating standings image for {season}")
                return generate_image(build_teams_html(data, season or "Current Season"))
        
        except Exception as e:
            return f"❌ Error retrieving team scores: {str(e)}"
    
    def _handle_team_record(self, team_name: Optional[str], season: Optional[str]):
        """Handle team weekly breakdown query — returns image."""
        if not team_name:
            return "❌ Please specify a team name. Example: `team Pin Seekers weekly`"
        try:
            from image_generator import build_team_weekly_html, generate_image
            data = self.sheet_handler.get_team_weekly_summary(team_name, season)
            if "error" in data:
                return f"❌ {data['error']}" + (f" ({season})" if season else "")
            team = data.get("team", team_name)
            weekly_summary = data.get("weekly_summary", {})
            if not weekly_summary:
                return f"❌ No weekly data found for {team}"
            season_str = data.get("season", season or "Current Season")
            print(f"[Team Weekly] Generating image for {team} {season_str}")
            return generate_image(build_team_weekly_html(team, season_str, weekly_summary))
        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Error retrieving team record: {str(e)}"
    
    def _handle_leaders(self, season: Optional[str]):
        """Handle league leaders query — returns image."""
        try:
            from image_generator import build_leaders_html, generate_image
            if season == "all":
                data = self.sheet_handler.get_all_time_stats()
            else:
                data = self.sheet_handler.get_league_stats(season)
            if "error" in data:
                return f"❌ {data['error']}" + (f" ({season})" if season else "")
            print(f"[Leaders] Generating leaders image for {data.get('season')}")
            return generate_image(build_leaders_html(data))
        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Error retrieving leaders: {str(e)}"
    
    def _handle_player_scores(self, player_name: Optional[str], season: Optional[str],
                              week: Optional[int] = None, user_phone: Optional[str] = None) -> str:
        """Handle player scores query."""
        try:
            # Check for ambiguous player name before fetching full stats
            if player_name:
                matches = self.sheet_handler.find_player_names(player_name, season)
                if len(matches) > 1 and user_phone:
                    params = {"season": season, "week": week}
                    return self._store_pending(user_phone, CommandType.PLAYER_SCORES, params, matches)
                if len(matches) == 1:
                    player_name = matches[0]  # Use the exact name

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
    
    def _handle_list_players(self, season: Optional[str]):
        """Handle list players query — returns image."""
        try:
            from image_generator import build_players_html, generate_image
            if season == "all":
                stats = self.sheet_handler.get_all_time_stats()
                # Convert list of player dicts to the {name: stats} shape build_players_html expects
                data = {
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
                data = self.sheet_handler.get_player_scores(None, season)
                subtitle = season or "Current Season"
            if not data:
                return f"❌ No players found." + (f" ({season})" if season else "")
            print(f"[Players] Generating leaderboard image for {season}")
            return generate_image(build_players_html(data, subtitle))
        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Error retrieving players: {str(e)}"
    
    
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

