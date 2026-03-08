# Google Sheets Migration Plan

## Goal
Replace the local Excel file with a Google Sheet read via the Sheets API.
This allows the bot to run on Railway (or any cloud host) without needing a file on disk.

---

## Step 1 — Google Cloud Setup (you)

1. Go to https://console.cloud.google.com and create a new project (e.g. "BowlBot")
2. Enable the following APIs:
   - **Google Sheets API**
   - **Google Drive API**
3. Go to **IAM & Admin → Service Accounts** and create a new service account (name doesn't matter)
4. On the service account, go to **Keys → Add Key → Create new key → JSON**
   - This downloads a `.json` credentials file — keep it safe, don't commit it
5. Note the service account's email address (looks like `name@project.iam.gserviceaccount.com`)

---

## Step 2 — Google Sheet Setup (you)

1. Upload `Bowling-Friends League v5.xlsx` to Google Drive
2. Open it in Google Drive and go to **File → Save as Google Sheets**
   - This creates a native Google Sheet (do not just use the xlsx directly)
3. Share the new Google Sheet with the service account email from Step 1
   - Permission level: **Viewer** is sufficient
4. Copy the **Sheet ID** from the URL:
   - URL format: `https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit`

---

## Step 3 — Local .env Update (you)

Add the following to your `.env` file:

```
SHEET_HANDLER_TYPE=gsheets
GOOGLE_SHEET_ID=your_sheet_id_here
GOOGLE_CREDENTIALS={"type":"service_account","project_id":"..."}   # paste the full JSON contents on one line
```

- `GOOGLE_CREDENTIALS` is the entire contents of the downloaded JSON file, minified to one line
- On Railway, these are set as environment variables in the dashboard (not in `.env`)

---

## Step 4 — Code Changes (me)

When you're ready, provide this file and ask to implement the Google Sheets migration. I will:

1. Add `gspread` and `google-auth` back to `requirements.txt`
2. Add a `GSheetHandler` class to `sheets_handler.py` that reads data via the Sheets API
   - Same column structure as the Excel file, same method signatures
   - Sheet tabs map directly to season names (e.g. "Season 12")
3. Update the `get_sheet_handler()` factory to support `type=gsheets`
4. Update `main.py` to read `GOOGLE_CREDENTIALS` and `GOOGLE_SHEET_ID` from env
5. Fix the port to use Railway's injected `PORT` env variable
6. Add a `Procfile` for Railway deployment

---

## Step 5 — Railway Deployment (you, after code changes)

1. Push code to a GitHub repo (Railway deploys from GitHub)
2. Go to https://railway.app, sign up and create a new project from your GitHub repo
   - The free tier ($5 trial credits, then $1/month or free tier available) is sufficient for this bot
3. In Railway dashboard, add environment variables:
   - `ACCESS_TOKEN`
   - `VERIFY_TOKEN`
   - `SHEET_HANDLER_TYPE=gsheets`
   - `GOOGLE_SHEET_ID`
   - `GOOGLE_CREDENTIALS` (full JSON, one line)
4. Railway will auto-deploy on every push to main
5. Use the Railway-provided URL as your WhatsApp webhook URL in the Meta dashboard

---

## Step 6 — Phone Number Setup via Twilio (you)

Meta requires a permanent phone number registered with the WhatsApp Business API.
The free test number Meta provides only works with 5 pre-approved contacts, so a real number is needed for a group.

1. Go to https://twilio.com and create an account
2. In the Twilio console, go to **Phone Numbers → Buy a Number**
   - Search for a local number (~$1/month)
   - You don't need SMS or voice capabilities, but they're usually included
   - Purchase the number
3. Go to https://developers.facebook.com → your Meta app → **WhatsApp → API Setup**
4. Under **Add a phone number**, click **Add phone number**
5. Enter your Twilio number when prompted
6. Meta will call or SMS the number to verify it — forward that verification to your Twilio number:
   - In Twilio console, go to your number's settings
   - Set the **A call comes in** webhook to forward to your personal number temporarily, or check the Twilio call logs for the verification code
7. Once verified, the Twilio number is your permanent WhatsApp Business number
8. Update the **Callback URL** in Meta's WhatsApp → Configuration → Webhook to your Railway URL:
   - `https://yourapp.up.railway.app/webhook`
9. The `VERIFY_TOKEN` in Railway env vars must match what you set in the Meta webhook config

**Cost summary:**
- Twilio number: ~$1/month
- Railway: $0/month (free tier)
- Google Sheets API: $0
- **Total: ~$1/month**

---

## Notes

- The `.env` file should **not** be committed to git — make sure it's in `.gitignore`
- The Excel file can stay in the repo as a backup but won't be used once gsheets is active
- `SHEET_HANDLER_TYPE=excel` still works locally if you want to test without hitting Google
