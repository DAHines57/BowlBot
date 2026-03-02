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
- `teams` - All team standings (record and average). Uses most recent season, or `s[N]` if specified (e.g., `teams s9`)
- `team [name]` - Season stats for one team: record, average, total pins, and each player's average. Uses most recent season, or `s[N]` if specified (e.g., `team Rolling Stoned s9`)
- `team [name] weekly` - Week-by-week breakdown: opponent, record, total pins, and average per week. Uses most recent season, or `s[N]` if specified (e.g., `team Rolling Stoned weekly s9`)

**Player Commands:**
- `players` - All players sorted by average. Use `s[N]` for a specific season (e.g., `players s9`)
- `player [name]` or `[name] stats` - Stats for one player: average, std dev, highest/lowest game. Use `s[N]` or `w[N]` to filter (e.g., `player Dylan s9`, `player Dylan w5`)

**League Leaders:**
- `leaders` - Top 10 individual games, top 10 player weeks, top 5 team weeks. Use `s[N]` for a specific season (e.g., `leaders s9`)

**Seasons & Weeks:**
- `seasons` - List all available seasons
- Add `s[N]` or `season [N]` to any command for a specific season (e.g., `teams s8`, `player Dylan season 9`)
- Add `w[N]` or `week [N]` to team/player commands to see individual games for that week (e.g., `team Pin Seekers w5`, `player Dylan w5`)
- If not specified, the most recent season is used automatically

**Scores:**
- `add score [score] [player]` - Add a game score (e.g., `add score 180 Dylan`)
- `add score [score] [player] s[N]` - Add a score to a specific season

**Help:**
- `help` - Show available commands

### Examples

```
User: teams
Bot: 🏆 Team Standings (Season 9)
     1. *Rolling Stoned* — 13-15 | Avg: 185.2
     2. *Pin Seekers* — 15-13 | Avg: 180.5
     ...

User: team Rolling Stoned s9
Bot: 🏆 Rolling Stoned (Season 9)
     📊 Record: 13-15
     📈 Team Average: 185.2
     🎳 Total pins: 18500
     👥 Players:
       • Player1: 190.5
       • Player2: 180.3

User: team Rolling Stoned weekly
Bot: 📊 Rolling Stoned Weekly Record (Season 9)
     *Total Record: 13-15*
     *Week 1* vs Pin Seekers
       3-1 | 2850 - 2750 | Avg: 178.1
     ...

User: team Pin Seekers w5
Bot: 🏆 Pin Seekers - Week 5
     vs Rolling Stoned
     📊 Record: 2-3
     👥 Players: ...

User: players
Bot: 👥 All Players (Season 9)
     • Dylan (Rolling Stoned) - Avg: 185.5 (36 games)
     ...

User: player Dylan s9
Bot: 🎳 Dylan (Season 9)
     Team: Rolling Stoned
     📊 Average: 175.5
     📏 Std Dev: 25.3
     🎯 Highest Game: 280
     📉 Lowest Game: 120
     📈 Games: 28

User: leaders
Bot: 🏆 League Leaders (Season 9)
     🎯 Top 10 Individual Games: ...
     ⭐ Top 10 Player Weeks: ...
     🏅 Top 5 Team Weeks: ...

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
- Wins/losses are calculated per game (Game 1 vs Game 1, Game 2 vs Game 2, etc.) - up to 5 games per week
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
