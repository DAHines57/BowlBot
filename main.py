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
EXCEL_FILE_PATH = os.environ.get("EXCEL_FILE_PATH", "Bowling-Friends League v5.xlsx")

# Initialize sheet handler
try:
    sheet_handler = get_sheet_handler("excel", file_path=EXCEL_FILE_PATH)
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
    print(f"Received webhook data: {data}")

    if data and data.get("entry"):
        for entry in data["entry"]:
            for change in entry["changes"]:
                if "messages" in change["value"]:
                    message = change["value"]["messages"][0]
                    sender_number = message["from"]
                    sender_number_id = change["value"].get("metadata", {}).get("phone_number_id")
                    message_text = message.get("text", {}).get("body", "")
                    
                    print(f"Received message from {sender_number}: {message_text}")
                    print(f"Sender number ID: {sender_number_id}")

                    # Process command and generate response
                    try:
                        if bot_logic:
                            # Parse the command
                            command = command_parser.parse(message_text)
                            
                            # Get optional season from message or use current
                            season = None  # Could extract from message if needed
                            
                            # Execute command
                            response_text = bot_logic.handle_command(command, season)
                        else:
                            response_text = "❌ Bot is not properly configured. Please check sheet handler setup."
                    except Exception as e:
                        print(f"Error processing command: {e}")
                        import traceback
                        traceback.print_exc()
                        response_text = f"❌ Error processing command: {str(e)}"

                    # Send response
                    try:
                        send_whatsapp_message(sender_number_id, sender_number, response_text, message.get("id"))
                    except Exception as e:
                        print(f"Error sending message: {e}")
                        import traceback
                        traceback.print_exc()

    return jsonify({"status": "received"}), 200

def send_whatsapp_message(recipient_id, recipient_number, message_text, message_id=None):
    """Sends a message to the WhatsApp user."""
    if not ACCESS_TOKEN:
        print("ERROR: ACCESS_TOKEN not set!")
        return
    
    if not recipient_id:
        print(f"ERROR: recipient_id is None! sender_number_id: {recipient_id}")
        return
    
    url = f"https://graph.facebook.com/v18.0/{recipient_id}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_number,
        "type": "text",
        "text": {"body": message_text},
        "context": {"message_id": message_id},
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        print(f"Message sent successfully to {recipient_number}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending WhatsApp message: {e}")
        print(f"Response: {response.text if 'response' in locals() else 'No response'}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000,debug=True)
