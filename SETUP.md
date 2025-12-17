# BowlBot Setup Guide

## Overview

BowlBot is a WhatsApp bot that connects to your bowling league Excel file to query team scores, player scores, and enter new scores.

## Features

- ✅ Query team standings and statistics
- ✅ Query individual player scores and averages
- ✅ Add new scores for players
- ✅ Support for multiple seasons
- ✅ Natural language command parsing
- ✅ Handles absent players (excludes from averages)
- ✅ Handles substitutes (excludes from team averages)

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

## Usage

### Commands

**Team Scores:**
- `team` or `teams` - Show all team standings
- `team [name]` - Show specific team stats (e.g., `team Rolling Stoned`)
- `team [name] season [N]` - Show team stats for specific season

**Player Scores:**
- `player [name]` - Show player stats
- `score [name]` - Show player scores
- `[name] stats` - Show player statistics
- `player [name] season [N]` - Show player stats for specific season

**Add Scores:**
- `add score [score] [player]` - Add a score (e.g., `add score 180 Dylan`)
- `enter score [score] [player]` - Enter a score
- `[player] [score]` - Quick add (e.g., `Dylan 180`)

**Seasons:**
- `seasons` - List all available seasons
- Use `season [N]` or `s[N]` to specify a season (e.g., "season 9" or "s9")
- If not specified, uses current season

**Help:**
- `help` - Show available commands

### Examples

```
User: team Rolling Stoned
Bot: 🏆 Rolling Stoned
     📊 Record: 13-15
     📈 Avg per game: 185.2
     🎳 Total pins: 18500

User: player Dylan season 9
Bot: 🎳 Dylan (Season 9)
     Team: Irregular Bowl Movements
     📊 Average: 175.5
     🎯 Scores: 180, 165, 190, 167
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
- The bot automatically uses the most recent season if no season is specified
- Player and team name matching is case-insensitive and supports partial matches

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
