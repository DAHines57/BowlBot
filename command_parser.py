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
    LEADERS = "leaders"
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
        r'teams?',  # "team" or "teams"
        r'standings?',  # "standings"
    ]
    
    # Patterns for team weekly breakdown
    TEAM_RECORD_PATTERNS = [
        r'team\s+(.+)\s+weekly',  # "team Red weekly"
        r'team\s+weekly\s+(.+)',  # "team weekly Red"
    ]
    
    # Common patterns for player queries
    PLAYER_PATTERNS = [
        r'player\s+(.+)',   # "player John"
        r'(.+)\s+stats?',   # "John stats"
    ]
    
    # Common patterns for adding scores
    ADD_SCORE_PATTERNS = [
        r'add\s+score\s+(\d+)\s+(.+)',  # "add score 150 John"
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
        if message in ['players', 'list players']:
            params = {}
            if season:
                params["season"] = season
            return Command(CommandType.LIST_PLAYERS, params)
        
        # Leaders / top stats command
        if message in ['leaders', 'top', 'best']:
            params = {}
            if season:
                params["season"] = season
            return Command(CommandType.LEADERS, params)
        
        # Check for team weekly (before team scores to catch "team X weekly")
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
                # Handle "team" or "teams" without a name (show all teams)
                if team_name and team_name.lower() not in ['scores', 'score', 'weekly']:
                    params["team_name"] = team_name.strip()
                    return Command(CommandType.TEAM_SCORES, params)
                else:
                    # No team name specified - show all teams
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
        return """🎳 *BowlBot Commands:*

*Teams:*
• `teams` - All team standings (record & average)
• `team [name]` - Season stats for one team
• `team [name] weekly` - Week-by-week breakdown for one team

*Players:*
• `players` - All players sorted by average
• `player [name]` or `[name] stats` - Stats for one player

*League Leaders:*
• `leaders` - Top games, top player weeks, top team weeks

*Seasons:*
• `seasons` - List all available seasons
• Add `s[N]` to any command for a specific season (e.g., `teams s8`)
• Add `w[N]` to team/player commands for a specific week (e.g., `team Pin Seekers w5`)
• If not specified, the most recent season is used automatically

*Scores:*
• `add score [score] [player]` - Add a game score (e.g., `add score 180 Dylan`)

*Other:*
• `help` - Show this message

*Examples:*
• `teams` or `teams s8`
• `team Rolling Stoned` or `team Rolling Stoned s8`
• `team Rolling Stoned weekly` or `team Rolling Stoned weekly s8`
• `team Pin Seekers w5`
• `players` or `players s8`
• `player Dylan` or `Dylan stats`
• `player Dylan s8` or `player Dylan w5`
• `leaders` or `leaders s8`"""

