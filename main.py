from flask import Flask, request, jsonify
import requests
import os
from os.path import join, dirname
from dotenv import load_dotenv

app = Flask(__name__)

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Replace with your actual Meta API credentials
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")  # Set a random string

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

                    # Respond back to the sender
                    send_whatsapp_message(sender_number_id, sender_number, f"You said: {message_text}", message.get("id"))

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
