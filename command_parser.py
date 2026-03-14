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
    BEST_PLAYER = "best_player"
    TOP_N = "top_n"
    RELOAD = "reload"
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
        
        # ── Regex intent matching (kept for reference, bypassed in favour of LLM) ──────
        # # Help command
        # if message in ['help', '?', 'commands']:
        #     return Command(CommandType.HELP)
        # # List seasons
        # if message in ['seasons', 'list seasons', 'show seasons']:
        #     ...
        # # List players
        # if message in ['players', 'list players']:
        #     ...
        # # Weekly results / summary / leaders / top-n / best-player / team / player patterns
        # # (all commented out — LLM handles intent classification)
        # ────────────────────────────────────────────────────────────────────────────

        # Reload command — direct match, never sent to LLM
        if re.match(r'^reload(\s+data)?$', message.strip()):
            return Command(CommandType.RELOAD)

        # Add score is structural enough to keep as regex (score + player name)
        for pattern in self.ADD_SCORE_PATTERNS:
            match = re.match(pattern, message, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
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
        
        # Skip LLM for messages that are clearly too long to be a valid command
        if len(original_message) > 150:
            return Command(CommandType.UNKNOWN)

        # Route everything through LLM for intent classification
        return self._llm_fallback(original_message, season, week)

    def _llm_fallback(self, message: str, season: Optional[str], week: Optional[int]) -> Command:
        """Use Claude to classify intent from any message."""
        api_key = os.environ.get("CLAUDE_API_KEY")
        if not api_key:
            return Command(CommandType.UNKNOWN)

        try:
            import anthropic
            print(f"[LLM] Classifying intent for: {message!r}")
            client = anthropic.Anthropic(api_key=api_key)

            prompt = (
                "You are a bowling league stats bot intent parser.\n"
                "Return ONLY valid JSON — no explanation, no markdown.\n\n"
                "Fields:\n"
                '- intent: one of:\n'
                '    "player_stats"    — stats for a specific player\n'
                '    "team_stats"      — standings/stats for a team or all teams\n'
                '    "team_record"     — week-by-week breakdown for a team\n'
                '    "leaders"         — league-wide top stats (games, weeks, team weeks)\n'
                '    "best_player"     — who is/was the single best bowler (by average)\n'
                '    "worst_player"    — who is/was the single worst bowler (by average)\n'
                '    "top_n"           — ranked list of top or bottom N players or individual scores\n'
                '    "list_players"    — full list of all players and their averages\n'
                '    "list_seasons"    — list available seasons\n'
                '    "weekly_summary"  — player scores/leaderboard for a specific week\n'
                '    "weekly_results"  — team matchup W/L results for a specific week\n'
                '    "help"            — asking what the bot can do\n'
                '    "unknown"         — cannot determine intent\n\n'
                '- subject: player or team name if mentioned, else null\n'
                '- subject_type: "player", "team", or "all"\n'
                '- time_range: "current_season" (default), "all_time", or "season_N" (N = number).\n'
                '  Use "all_time" for: "ever", "all time", "career", "historically", "of all time",\n'
                '  "best ever", "in history", "across all seasons", "greatest", or similar.\n'
                '  Use "season_N" only for explicit numbers like "season 8" or "s8".\n'
                '  "last season" is handled externally — treat it as "current_season".\n\n'
                '- For top_n only, also include:\n'
                '    "n": number of players/scores requested (integer, default 5)\n'
                '    "direction": "best" (top) or "worst" (bottom)\n'
                '    "metric": "average" (player averages) or "game" (individual game scores)\n\n'
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

            elif intent == "best_player":
                return Command(CommandType.BEST_PLAYER, params)

            elif intent == "worst_player":
                params["direction"] = "worst"
                return Command(CommandType.BEST_PLAYER, params)

            elif intent == "top_n":
                raw_n = data.get("n") or 5
                _word_nums = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10}
                try:
                    n = int(raw_n)
                except (ValueError, TypeError):
                    n = _word_nums.get(str(raw_n).lower(), 5)
                params["n"] = n
                params["direction"] = data.get("direction", "best")
                params["metric"] = data.get("metric", "average")
                return Command(CommandType.TOP_N, params)

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

