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
    PLAYER_SCORES = "player_scores"
    ADD_SCORE = "add_score"
    LIST_SEASONS = "list_seasons"
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
    
    def _extract_season(self, message: str) -> Tuple[str, Optional[str]]:
        """
        Extract season information from message and return (cleaned_message, season).
        
        Args:
            message: The original message
            
        Returns:
            Tuple of (cleaned message without season, season string or None)
        """
        # Patterns to match season specifications
        season_patterns = [
            r'\bseason\s+(\d+)\b',  # "season 9" or "season 10"
            r'\bs(\d+)\b',  # "s9" or "s10" (short form)
        ]
        
        season = None
        cleaned_message = message
        
        for pattern in season_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                season_num = match.group(1)
                season = f"Season {season_num}"
                # Remove season from message
                cleaned_message = re.sub(pattern, '', cleaned_message, flags=re.IGNORECASE).strip()
                # Clean up extra spaces
                cleaned_message = re.sub(r'\s+', ' ', cleaned_message)
                break
        
        return cleaned_message, season
    
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
        
        # Extract season information first
        cleaned_message, season = self._extract_season(message)
        message = cleaned_message.lower()
        
        # Help command
        if message in ['help', '?', 'commands']:
            return Command(CommandType.HELP)
        
        # List seasons command
        if message in ['seasons', 'list seasons', 'show seasons']:
            params = {}
            if season:
                params["season"] = season
            return Command(CommandType.LIST_SEASONS, params)
        
        # Check for team scores
        for pattern in self.TEAM_PATTERNS:
            match = re.match(pattern, message, re.IGNORECASE)
            if match:
                team_name = match.group(1) if match.groups() and match.group(1) else None
                params = {}
                if season:
                    params["season"] = season
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
• `team` or `teams` - Show all team standings
• `team [name]` - Show specific team stats
• `team [name] season [N]` - Show team stats for specific season
• `season [N] team [name]` - Alternative format

*Player Scores:*
• `player [name]` - Show player stats
• `score [name]` - Show player scores
• `[name] stats` - Show player statistics
• `player [name] season [N]` - Show player stats for specific season

*Add Scores:*
• `add score [score] [player]` - Add a score
• `enter score [score] [player]` - Enter a score
• `[player] [score]` - Quick add (e.g., "John 150")
• `add score [score] [player] season [N]` - Add score to specific season

*Seasons:*
• `seasons` - List all available seasons
• Use `season [N]` or `s[N]` to specify a season (e.g., "season 9" or "s9")
• If not specified, uses current season

*Other:*
• `help` - Show this message

*Examples:*
• `team Rolling Stoned`
• `team Rolling Stoned season 9`
• `player John season 10`
• `add score 180 Dylan`
• `add score 180 Dylan season 10`"""

