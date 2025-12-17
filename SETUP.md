# BowlBot Setup Guide

## Overview

BowlBot is a WhatsApp bot that connects to your bowling league data (Google Sheets or Excel) to query team scores, player scores, and enter new scores.

## Features

- ✅ Query team standings and statistics
- ✅ Query individual player scores and averages
- ✅ Add new scores for players
- ✅ Support for both Google Sheets and Excel files
- ✅ Natural language command parsing

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
   
   # Sheet handler configuration
   SHEET_HANDLER_TYPE=excel  # or "googlesheets" for Google Sheets
   EXCEL_FILE_PATH=Bowling- Friends League v4.xlsx
   
   # Google Sheets configuration (if using Google Sheets)
   # GOOGLE_SHEETS_ID=your_spreadsheet_id
   # GOOGLE_CREDENTIALS_PATH=path/to/credentials.json
   ```

## Google Sheets Setup (Optional)

If you want to use Google Sheets instead of Excel:

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable Google Sheets API:**
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Sheets API" and enable it
   - Also enable "Google Drive API"

3. **Create Service Account:**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Create a service account and download the JSON key file

4. **Share your Google Sheet:**
   - Open your Google Sheet
   - Click "Share" and add the service account email (found in the JSON file)
   - Give it "Editor" permissions

5. **Update .env:**
   ```env
   SHEET_HANDLER_TYPE=googlesheets
   GOOGLE_SHEETS_ID=your_spreadsheet_id_from_url
   GOOGLE_CREDENTIALS_PATH=path/to/your-credentials.json
   ```

## Usage

### Commands

**Team Scores:**
- `team` or `teams` - Show all team standings
- `team [name]` - Show specific team stats (e.g., `team Rolling Stoned`)

**Player Scores:**
- `player [name]` - Show player stats (e.g., `player John`)
- `score [name]` - Show player scores
- `[name] stats` - Show player statistics

**Add Scores:**
- `add score [score] [player]` - Add a score (e.g., `add score 180 Dylan`)
- `enter score [score] [player]` - Enter a score
- `[player] [score]` - Quick add (e.g., `Dylan 180`)

**Help:**
- `help` - Show available commands

### Examples

```
User: team Rolling Stoned
Bot: 🏆 Rolling Stoned
     📊 Record: 13-15
     📈 Avg per game: 185.2
     🎳 Total pins: 18500

User: player Dylan
Bot: 🎳 Dylan
     Team: Irregular Bowl Movements
     📊 Average: 175.5
     🎯 Scores: 180, 165, 190, 167
     📈 Games: 4

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
├── sheets_handler.py       # Sheet data access (Excel/Google Sheets)
├── command_parser.py       # WhatsApp message parsing
├── bot_logic.py           # Command execution and responses
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create this)
└── Bowling- Friends League v4.xlsx  # Excel file (for testing)
```

## Notes

- The bot defaults to using Excel files for easy local testing
- Excel file modifications are saved directly to the file
- For production, consider using Google Sheets for better multi-user access
- The bot automatically uses the most recent season if no season is specified
- Player and team name matching is case-insensitive and supports partial matches

## Troubleshooting

**Bot not responding:**
- Check that your WhatsApp webhook is properly configured
- Verify `ACCESS_TOKEN` and `VERIFY_TOKEN` in `.env`
- Check Flask server logs for errors

**Sheet handler errors:**
- For Excel: Ensure the file path is correct and the file exists
- For Google Sheets: Verify service account credentials and sheet sharing permissions

**Command not recognized:**
- Type `help` to see available commands
- Commands are case-insensitive
- Use exact player/team names or partial matches

