"""
Command parser for WhatsApp messages.
Parses user messages into structured commands.
"""
import re
import os
import json
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
    WEEKLY_SUMMARY = "weekly_summary"
    WEEKLY_RESULTS = "weekly_results"
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
        # Patterns to match relative season references
        if re.search(r'\blast\s+season\b', message, re.IGNORECASE):
            cleaned_message = re.sub(r'\blast\s+season\b', '', message, flags=re.IGNORECASE).strip()
            cleaned_message = re.sub(r'\s+', ' ', cleaned_message)
            return cleaned_message, "last", None

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
        
        # Weekly matchup results image
        if message in ['results', 'matchups', 'weekly results', 'week results', 'matchup recap']:
            params = {}
            if season:
                params["season"] = season
            if week:
                params["week"] = week
            return Command(CommandType.WEEKLY_RESULTS, params)

        # Weekly summary image
        if message in ['summary', 'recap', 'weekly summary', 'weekly recap', 'week summary', 'week recap']:
            params = {}
            if season:
                params["season"] = season
            if week:
                params["week"] = week
            return Command(CommandType.WEEKLY_SUMMARY, params)

        # Leaders / top stats command
        if message in ['leaders', 'top', 'best']:
            params = {}
            if season:
                params["season"] = season
            return Command(CommandType.LEADERS, params)

        if re.search(r'\ball\s*time\b', message, re.IGNORECASE) and re.search(r'\b(leaders?|top|best|games?|stats?)\b', message, re.IGNORECASE):
            return Command(CommandType.LEADERS, {"season": "all"})

        if message in ['leaders all', 'all time leaders', 'all time', 'all-time leaders']:
            return Command(CommandType.LEADERS, {"season": "all"})
        
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
        
        # Unknown command — try LLM fallback before giving up
        return self._llm_fallback(original_message, season, week)

    def _llm_fallback(self, message: str, season: Optional[str], week: Optional[int]) -> Command:
        """
        Use Claude as a fallback intent parser for freeform messages that didn't
        match any regex pattern. Returns a Command based on structured JSON from the API.
        Only called when direct pattern matching fails.
        """
        api_key = os.environ.get("CLAUDE_API_KEY")
        if not api_key:
            return Command(CommandType.UNKNOWN)

        try:
            import anthropic
            print(f"[LLM] No regex match for {message!r} — calling Claude fallback")
            client = anthropic.Anthropic(api_key=api_key)

            prompt = (
                "You are a bowling league stats bot intent parser.\n"
                "Extract the intent from the user's message and return ONLY valid JSON, no explanation or markdown.\n\n"
                "Fields:\n"
                '- intent: one of "player_stats", "team_stats", "team_record", "leaders", "list_players", "list_seasons", "weekly_summary", "weekly_results", "help", "unknown"\n'
                '  weekly_summary = player leaderboard/scores for a specific week (e.g. "how did everyone do this week", "weekly recap")\n'
                '  weekly_results = team matchup results for a specific week (e.g. "who won this week", "show me the matchups", "weekly results")\n'
                '- subject: the player or team name mentioned, or null if asking about all\n'
                '- subject_type: "player", "team", or "all"\n'
                '- time_range: "current_season" (default), "all_time", or "season_N" where N is the number.\n'
                '  Use "all_time" for any of these signals: "all time", "ever", "career", "historically",\n'
                '  "across all seasons", "of all time", "best ever", "greatest", "highest ever",\n'
                '  "in history", "since the beginning", "going back", "across seasons", or any phrasing\n'
                '  that implies spanning more than one season rather than the current one.\n'
                '  Only use season_N if the user says an explicit number like "season 8" or "s8".\n\n'
                f'Message: "{message}"\n'
            )

            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            raw = response.content[0].text.strip()
            print(f"[LLM] Response: {raw}")
            # Strip markdown code fences if present (e.g. ```json ... ```)
            if raw.startswith("```"):
                raw = re.sub(r'^```[a-z]*\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw).strip()
            data = json.loads(raw)

            intent = data.get("intent", "unknown")
            subject = data.get("subject")
            subject_type = data.get("subject_type", "all")
            time_range = data.get("time_range", "current_season")

            # Resolve season from LLM time_range (only if not already extracted by regex)
            if season is None:
                if time_range == "all_time":
                    season = "all"
                elif time_range and time_range.startswith("season_"):
                    try:
                        season = f"Season {time_range.split('_')[1]}"
                    except IndexError:
                        pass
                # "current_season" → leave as None (default behaviour)

            params = {}
            if season:
                params["season"] = season
            if week:
                params["week"] = week

            if intent == "player_stats":
                if subject:
                    params["player_name"] = subject
                return Command(CommandType.PLAYER_SCORES, params)

            elif intent == "team_stats":
                if subject:
                    params["team_name"] = subject
                return Command(CommandType.TEAM_SCORES, params)

            elif intent == "team_record":
                if subject:
                    params["team_name"] = subject
                return Command(CommandType.TEAM_RECORD, params)

            elif intent == "leaders":
                return Command(CommandType.LEADERS, params)

            elif intent == "weekly_summary":
                return Command(CommandType.WEEKLY_SUMMARY, params)

            elif intent == "weekly_results":
                return Command(CommandType.WEEKLY_RESULTS, params)

            elif intent == "list_players":
                return Command(CommandType.LIST_PLAYERS, params)

            elif intent == "list_seasons":
                return Command(CommandType.LIST_SEASONS, params)

            elif intent == "help":
                return Command(CommandType.HELP)

        except Exception:
            pass

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

