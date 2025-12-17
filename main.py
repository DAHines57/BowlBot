from flask import Flask, request, jsonify
import requests
import os
from os.path import join, dirname
from dotenv import load_dotenv

# Import bot modules
from sheets_handler import get_sheet_handler
from command_parser import CommandParser
from bot_logic import BotLogic

app = Flask(__name__)

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Replace with your actual Meta API credentials
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")  # Set a random string

# Initialize sheet handler
# Default to Excel for testing, can be switched to Google Sheets via environment variable
SHEET_HANDLER_TYPE = os.environ.get("SHEET_HANDLER_TYPE", "excel").lower()
EXCEL_FILE_PATH = os.environ.get("EXCEL_FILE_PATH", "Bowling- Friends League v4.xlsx")
GOOGLE_SHEETS_ID = os.environ.get("GOOGLE_SHEETS_ID")
GOOGLE_CREDENTIALS_PATH = os.environ.get("GOOGLE_CREDENTIALS_PATH")

# Initialize sheet handler
try:
    if SHEET_HANDLER_TYPE == "excel":
        sheet_handler = get_sheet_handler("excel", file_path=EXCEL_FILE_PATH)
    elif SHEET_HANDLER_TYPE in ["googlesheets", "google", "gsheets"]:
        if not GOOGLE_SHEETS_ID:
            raise ValueError("GOOGLE_SHEETS_ID environment variable is required for Google Sheets")
        sheet_handler = get_sheet_handler(
            "googlesheets",
            spreadsheet_id=GOOGLE_SHEETS_ID,
            credentials_path=GOOGLE_CREDENTIALS_PATH
        )
    else:
        raise ValueError(f"Unknown SHEET_HANDLER_TYPE: {SHEET_HANDLER_TYPE}")
except Exception as e:
    print(f"Error initializing sheet handler: {e}")
    sheet_handler = None

# Initialize bot components
command_parser = CommandParser()
bot_logic = BotLogic(sheet_handler) if sheet_handler else None

# Webhook verification
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Verifies the webhook with the token."""
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Verification failed.", 403

# Handle incoming messages
@app.route("/webhook", methods=["POST"])
def receive_message():
    """Receives and processes incoming WhatsApp messages."""
    data = request.get_json()

    if data.get("entry"):
        for entry in data["entry"]:
            for change in entry["changes"]:
                if "messages" in change["value"]:
                    message = change["value"]["messages"][0]
                    sender_number = message["from"]
                    sender_number_id = change["value"].get("metadata", {}).get("phone_number_id")
                    message_text = message.get("text", {}).get("body", "")

                    # Process command and generate response
                    if bot_logic:
                        # Parse the command
                        command = command_parser.parse(message_text)
                        
                        # Get optional season from message or use current
                        season = None  # Could extract from message if needed
                        
                        # Execute command
                        response_text = bot_logic.handle_command(command, season)
                    else:
                        response_text = "❌ Bot is not properly configured. Please check sheet handler setup."

                    # Send response
                    send_whatsapp_message(sender_number_id, sender_number, response_text, message.get("id"))

    return jsonify({"status": "received"}), 200

def send_whatsapp_message(recipient_id, recipient_number, message_text, message_id=None):
    """Sends a message to the WhatsApp user."""
    url = f"https://graph.facebook.com/v18.0/{recipient_id}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_number,
        "type": "text",
        "text": {"body": message_text},
        "context": {"message_id": message_id},
    }
    requests.post(url, json=payload, headers=headers)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000,debug=True)
