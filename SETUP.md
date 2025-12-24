# BowlBot Setup Guide

## Overview

BowlBot is a WhatsApp bot that connects to your bowling league Excel file to query team scores, player scores, and enter new scores.

## Features

- ✅ Query team standings and statistics
- ✅ Query individual player scores and averages (with standard deviation)
- ✅ Weekly team records with wins/losses/ties
- ✅ Add new scores for players
- ✅ Support for multiple seasons
- ✅ Natural language command parsing
- ✅ Handles absent players (excludes from averages)
- ✅ Handles substitutes (excludes from team averages)
- ✅ League statistics (top players, best weeks, best games)
- ✅ Wins/losses calculated per game (up to 4 games per week)

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   Create a `.env` file in the project root with:
   ```env
   # WhatsApp API credentials (required)
   ACCESS_TOKEN=your_whatsapp_access_token
   VERIFY_TOKEN=your_webhook_verify_token
   
   # Excel file path (optional, defaults to "Bowling-Friends League v5.xlsx")
   EXCEL_FILE_PATH=Bowling-Friends League v5.xlsx
   ```

## Excel File Structure

Your Excel file should have:
- **One sheet per season** (e.g., "Season 9", "Season 10")
- **One row per week per player** with columns:
  - Team
  - Player
  - Season
  - Week
  - Game 1
  - Game 2
  - Game 3
  - Game 4
  - Game 5 (optional)
  - Average (calculated field - bot can read this)
  - Playoffs?
  - Absent? (Y/N - excludes week from player average)
  - Substitute? (Y/N - excludes from team averages)
  - Opponent (team name for the week)

## Usage

### Commands

**Team Commands:**
- `team` or `teams` - Show all team standings (record and average). Uses most recent season, or `s[N]` if specified (e.g., `teams s9`)
- `team [name]` - Show overall standing, record, average, total pins, and each player's average. Uses most recent season, or `s[N]` if specified (e.g., `team Rolling Stoned s9`)
- `team [name] weekly` - Weekly breakdown showing opponent, record, total pins, and average for each week. Uses most recent season, or `s[N]` if specified (e.g., `team Rolling Stoned weekly s9`)

**Player Scores:**
- `player [name]` or `[name] stats` - Show player stats (average, std dev, highest/lowest game)
- `score [name]` or `[name] score` - Show player scores (same as above)
- `player [name] season [N]` - Show player stats for specific season

**Add Scores:**
- `add score [score] [player]` - Add a score (e.g., `add score 180 Dylan`)
- `enter score [score] [player]` - Enter a score
- `[player] [score]` - Quick add (e.g., `Dylan 180`)
- `add score [score] [player] season [N]` - Add score to specific season

**Seasons:**
- `seasons` - List all available seasons
- Use `season [N]` or `s[N]` to specify a season (e.g., "season 9" or "s9")
- If not specified, uses most recent season automatically

**Lists:**
- `players` - List all players (sorted by average)
- `teams` - List all teams (sorted by average)

**Statistics:**
- `stats` or `summary` - Show all league statistics
- `averages` - Show all player averages
- `best weeks` - Show top 10 individual player weeks
- `best team weeks` - Show top 5 team weekly totals
- `best games` - Show top 10 highest individual games

**Help:**
- `help` - Show available commands

### Examples

```
User: team
Bot: 🏆 Team Standings (Season 9)
     
     1. *Rolling Stoned*
        13-15-0 | Avg: 185.2
     
     2. *Pin Seekers*
        15-13-0 | Avg: 180.5
     ...

User: team Rolling Stoned
Bot: 🏆 Rolling Stoned (Season 9)
     
     📊 Record: 13-15-0
     📈 Team Average: 185.2
     🎳 Total pins: 18500
     
     👥 Players:
       • Player1: 190.5
       • Player2: 180.3
       • Player3: 175.0

User: team Rolling Stoned weekly
Bot: 📊 Rolling Stoned Weekly Record (Season 9)
     
     *Total Record: 13-15-0*
     
     *Week 1* vs Pin Seekers
       3-1-0 | 2850 - 2750 | Avg: 178.1
     
     *Week 2* vs Team Name
       2-2-0 | 2800 - 2800 | Avg: 175.0
     ...

User: player Dylan season 9
Bot: 🎳 Dylan (Season 9)
     Team: Rolling Stoned
     
     📊 Average: 175.5
     📏 Std Dev: 25.3
     🎯 Highest Game: 280
     📉 Lowest Game: 120
     📈 Games: 28

User: add score 195 Dylan
Bot: ✅ Score of 195 added for Dylan!
```

## Running the Bot

1. **Start the Flask server:**
   ```bash
   python main.py
   ```

2. **Set up WhatsApp Webhook:**
   - Your webhook URL should be: `https://your-domain.com/webhook`
   - Use the `VERIFY_TOKEN` from your `.env` file when setting up the webhook
   - Make sure the "messages" field is subscribed in your webhook configuration

## File Structure

```
BowlBot/
├── main.py                 # Flask app and webhook handlers
├── sheets_handler.py       # Excel data access
├── command_parser.py       # WhatsApp message parsing
├── bot_logic.py           # Command execution and responses
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create this)
└── Bowling-Friends League v5.xlsx  # Excel file
```

## Notes

- The bot reads calculated fields (formulas) from Excel
- Absent weeks are excluded from player average calculations
- Substitute entries are excluded from team average calculations
- Total pins includes absences (weeks where average was taken) but never substitutes
- Wins/losses are calculated per game (Game 1 vs Game 1, Game 2 vs Game 2, etc.) - up to 4 games per week
- Team average is the average of individual player averages (excluding absent/substitute weeks)
- The bot automatically uses the most recent season if no season is specified
- Player and team name matching is case-insensitive and supports partial matches
- Lists (players, teams) are sorted by average (highest to lowest)

## Troubleshooting

**Bot not responding:**
- Check that your WhatsApp webhook is properly configured
- Verify `ACCESS_TOKEN` and `VERIFY_TOKEN` in `.env`
- Check Flask server logs for errors

**Sheet handler errors:**
- Ensure the Excel file path is correct and the file exists
- Verify the Excel file has the correct structure (one row per week per player)
- Check that season sheets are named "Season N" format

**Command not recognized:**
- Type `help` to see available commands
- Commands are case-insensitive
- Use exact player/team names or partial matches
