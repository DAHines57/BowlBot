"""
Command parser for WhatsApp messages.
Parses user messages into structured commands.
"""
import re
from typing import Dict, Optional, Tuple
from enum import Enum


class CommandType(Enum):
    """Types of commands the bot can handle."""
    TEAM_SCORES = "team_scores"
    TEAM_RECORD = "team_record"
    PLAYER_SCORES = "player_scores"
    ADD_SCORE = "add_score"
    LIST_SEASONS = "list_seasons"
    LIST_PLAYERS = "list_players"
    LIST_TEAMS = "list_teams"
    STATS = "stats"
    PLAYER_AVERAGES = "player_averages"
    BEST_PLAYER_WEEKS = "best_player_weeks"
    BEST_TEAM_WEEKS = "best_team_weeks"
    BEST_GAMES = "best_games"
    HELP = "help"
    UNKNOWN = "unknown"


class Command:
    """Represents a parsed command."""
    
    def __init__(self, command_type: CommandType, params: Dict = None):
        self.command_type = command_type
        self.params = params or {}
    
    def __repr__(self):
        return f"Command(type={self.command_type}, params={self.params})"


class CommandParser:
    """Parses WhatsApp messages into Command objects."""
    
    # Common patterns for team queries
    TEAM_PATTERNS = [
        r'team\s+(.+)',  # "team Red"
        r'team\s+scores',  # "team scores"
        r'teams?',  # "team" or "teams"
        r'standings?',  # "standings"
    ]
    
    # Patterns for team record
    TEAM_RECORD_PATTERNS = [
        r'team\s+(.+)\s+record',  # "team Red record"
        r'team\s+record\s+(.+)',  # "team record Red"
        r'record\s+(.+)',  # "record Red"
    ]
    
    # Common patterns for player queries
    PLAYER_PATTERNS = [
        r'player\s+(.+)',  # "player John"
        r'score\s+(.+)',  # "score John"
        r'(.+)\s+score',  # "John score"
        r'my\s+score',  # "my score"
        r'(.+)\s+stats?',  # "John stats"
    ]
    
    # Common patterns for adding scores
    ADD_SCORE_PATTERNS = [
        r'add\s+score\s+(\d+)\s+(.+)',  # "add score 150 John"
        r'enter\s+score\s+(\d+)\s+(.+)',  # "enter score 150 John"
        r'score\s+(\d+)\s+(.+)',  # "score 150 John"
        r'(.+)\s+(\d+)',  # "John 150" (simple format)
    ]
    
    def _extract_season_and_week(self, message: str) -> Tuple[str, Optional[str], Optional[int]]:
        """
        Extract season and week information from message and return (cleaned_message, season, week).
        
        Args:
            message: The original message
            
        Returns:
            Tuple of (cleaned message without season/week, season string or None, week number or None)
        """
        # Patterns to match season specifications
        season_patterns = [
            r'\bseason\s+(\d+)\b',  # "season 9" or "season 10"
            r'\bs(\d+)\b',  # "s9" or "s10" (short form)
        ]
        
        # Patterns to match week specifications
        week_patterns = [
            r'\bweek\s+(\d+)\b',  # "week 5" or "week 10"
            r'\bw(\d+)\b',  # "w5" or "w10" (short form)
        ]
        
        season = None
        week = None
        cleaned_message = message
        
        # Extract season
        for pattern in season_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                season_num = match.group(1)
                season = f"Season {season_num}"
                # Remove season from message
                cleaned_message = re.sub(pattern, '', cleaned_message, flags=re.IGNORECASE).strip()
                break
        
        # Extract week
        for pattern in week_patterns:
            match = re.search(pattern, cleaned_message, re.IGNORECASE)
            if match:
                week_num = match.group(1)
                week = int(week_num)
                # Remove week from message
                cleaned_message = re.sub(pattern, '', cleaned_message, flags=re.IGNORECASE).strip()
                break
        
        # Clean up extra spaces
        cleaned_message = re.sub(r'\s+', ' ', cleaned_message)
        
        return cleaned_message, season, week
    
    def parse(self, message: str) -> Command:
        """
        Parse a message into a Command object.
        
        Args:
            message: The user's message text
            
        Returns:
            Command object
        """
        original_message = message.strip()
        message = original_message.lower()
        
        # Extract season and week information first
        cleaned_message, season, week = self._extract_season_and_week(message)
        message = cleaned_message.lower()
        
        # Help command
        if message in ['help', '?', 'commands']:
            return Command(CommandType.HELP)
        
        # List seasons command
        if message in ['seasons', 'list seasons', 'show seasons']:
            params = {}
            if season:
                params["season"] = season
            if week:
                params["week"] = week
            return Command(CommandType.LIST_SEASONS, params)
        
        # List players command
        if message in ['players', 'list players', 'show players', 'all players']:
            params = {}
            if season:
                params["season"] = season
            if week:
                params["week"] = week
            return Command(CommandType.LIST_PLAYERS, params)
        
        # List teams command
        if message in ['teams', 'list teams', 'show teams', 'all teams']:
            params = {}
            if season:
                params["season"] = season
            if week:
                params["week"] = week
            return Command(CommandType.LIST_TEAMS, params)
        
        # Stats/summary commands
        if message in ['stats', 'statistics', 'summary', 'summaries']:
            params = {}
            if season:
                params["season"] = season
            return Command(CommandType.STATS, params)
        
        # Player averages
        if message in ['averages', 'player averages', 'avg', 'avgs']:
            params = {}
            if season:
                params["season"] = season
            return Command(CommandType.PLAYER_AVERAGES, params)
        
        # Best player weeks
        if message in ['best weeks', 'player weeks', 'best player weeks', 'top weeks']:
            params = {}
            if season:
                params["season"] = season
            return Command(CommandType.BEST_PLAYER_WEEKS, params)
        
        # Best team weeks
        if message in ['best team weeks', 'team weeks', 'top team weeks']:
            params = {}
            if season:
                params["season"] = season
            return Command(CommandType.BEST_TEAM_WEEKS, params)
        
        # Best games
        if message in ['best games', 'high games', 'top games', 'highest games']:
            params = {}
            if season:
                params["season"] = season
            return Command(CommandType.BEST_GAMES, params)
        
        # Check for team record (before team scores to catch "team X record")
        for pattern in self.TEAM_RECORD_PATTERNS:
            match = re.match(pattern, message, re.IGNORECASE)
            if match:
                team_name = match.group(1).strip() if match.groups() else None
                params = {}
                if season:
                    params["season"] = season
                if week:
                    params["week"] = week
                if team_name:
                    params["team_name"] = team_name
                return Command(CommandType.TEAM_RECORD, params)
        
        # Check for team scores
        for pattern in self.TEAM_PATTERNS:
            match = re.match(pattern, message, re.IGNORECASE)
            if match:
                team_name = match.group(1) if match.groups() and match.group(1) else None
                params = {}
                if season:
                    params["season"] = season
                if week:
                    params["week"] = week
                if team_name and team_name.lower() not in ['scores', 'score']:
                    params["team_name"] = team_name.strip()
                    return Command(CommandType.TEAM_SCORES, params)
                else:
                    return Command(CommandType.TEAM_SCORES, params)
        
        # Check for player scores
        for pattern in self.PLAYER_PATTERNS:
            match = re.match(pattern, message, re.IGNORECASE)
            if match:
                params = {}
                if season:
                    params["season"] = season
                if week:
                    params["week"] = week
                if match.groups():
                    player_name = match.group(1).strip()
                    if player_name.lower() not in ['my', 'score', 'scores']:
                        params["player_name"] = player_name
                        return Command(CommandType.PLAYER_SCORES, params)
                else:
                    # "my score" - would need phone number mapping, for now return generic
                    return Command(CommandType.PLAYER_SCORES, params)
        
        # Check for adding scores
        for pattern in self.ADD_SCORE_PATTERNS:
            match = re.match(pattern, message, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    # Try to determine which is score and which is name
                    try:
                        score = int(groups[0])
                        player_name = groups[1].strip()
                    except ValueError:
                        try:
                            score = int(groups[1])
                            player_name = groups[0].strip()
                        except ValueError:
                            continue
                    
                    if 0 <= score <= 300:  # Valid bowling score range
                        params = {
                            "player_name": player_name,
                            "score": score
                        }
                        if season:
                            params["season"] = season
                        return Command(CommandType.ADD_SCORE, params)
        
        # Unknown command
        return Command(CommandType.UNKNOWN)
    
    def get_help_message(self) -> str:
        """Get help message with available commands."""
        return """🏳️ *BowlBot Commands:*

*Team Scores:*
• `team` or `teams` - Show all team standings (sorted by average)
• `team [name]` - Show specific team stats with players
• `team [name] record` - Show weekly breakdown for team
• `team [name] season [N]` - Show team stats for specific season
• `season [N] team [name]` - Alternative format

*Player Scores:*
• `player [name]` or `[name] stats` - Show player stats (avg, std dev, highest/lowest)
• `score [name]` or `[name] score` - Show player scores (same as above)
• `player [name] season [N]` - Show player stats for specific season

*Add Scores:*
• `add score [score] [player]` - Add a score
• `enter score [score] [player]` - Enter a score
• `[player] [score]` - Quick add (e.g., "John 150")
• `add score [score] [player] season [N]` - Add score to specific season

*Seasons & Weeks:*
• `seasons` - List all available seasons
• Use `season [N]` or `s[N]` to specify a season (e.g., "season 9" or "s9")
• Use `week [N]` or `w[N]` to specify a week (e.g., "week 5" or "w5")
• If not specified, uses current season
• When week is specified, shows individual games for that week

*Lists:*
• `players` - List all players (sorted by average)
• `teams` - List all teams (sorted by average)

*Statistics:*
• `stats` or `summary` - Show all league statistics
• `averages` - Show all player averages
• `best weeks` - Show top 10 individual player weeks
• `best team weeks` - Show top 5 team weekly totals
• `best games` - Show top 10 highest individual games

*Other:*
• `help` - Show this message

*Examples:*
• `team Rolling Stoned`
• `team Rolling Stoned record`
• `team Rolling Stoned season 9`
• `player John season 10`
• `players` - List all players
• `averages` - Show player averages
• `best games` - Show top games
• `add score 180 Dylan`
• `add score 180 Dylan season 10`"""

