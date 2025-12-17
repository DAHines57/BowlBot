# BowlBot

A WhatsApp bot for managing bowling league scores and statistics.

## Features

- Query team standings and statistics
- Query individual player scores and averages  
- Add new scores via WhatsApp
- Support for multiple seasons
- Handles absent players and substitutes correctly

## Quick Start

1. Install dependencies: `pip install -r requirements.txt`
2. Set up `.env` file with WhatsApp credentials
3. Run: `python main.py`

See [SETUP.md](SETUP.md) for detailed setup instructions.

## Excel File Structure

The bot reads from Excel files with one row per week per player:
- Columns: Team, Player, Season, Week, Game 1-5, Average, Playoffs?, Absent?, Substitute?
- One sheet per season (e.g., "Season 9", "Season 10")

## Commands

- `team [name]` - Get team stats
- `player [name]` - Get player stats  
- `add score [score] [player]` - Add a score
- `seasons` - List all seasons
- `help` - Show all commands
