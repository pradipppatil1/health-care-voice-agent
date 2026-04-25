"""
Run this script ONCE to authorize Google Calendar + Sheets access.
It will open a browser, you log in, and it saves token.json.
After that, your main app uses token.json silently (auto-refreshes).

Prerequisites:
  - Download your OAuth2 client_secret.json from GCP Console
  - Place it in the same folder as this script
  - Run: python auth_setup.py
"""

import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
]

TOKEN_FILE = "token.json"
CLIENT_SECRET_FILE = "client_secret.json"


def main():
    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"ERROR: '{CLIENT_SECRET_FILE}' not found in current directory.")
        print("  1. Go to GCP Console → APIs & Services → Credentials")
        print("  2. Create OAuth 2.0 Client ID (Desktop app)")
        print("  3. Download JSON → rename to client_secret.json → place here")
        return

    creds = None

    # Load existing token if available
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid credentials, do browser login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("Opening browser for Google authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future use
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"\n✅ Authorization successful! Token saved to '{TOKEN_FILE}'")
        print("   Add token.json to .gitignore — keep it secret!")
    else:
        print(f"✅ Token already valid. Found at '{TOKEN_FILE}'")

    # Quick API test
    print("\nTesting Google Calendar access...")
    from googleapiclient.discovery import build
    service = build("calendar", "v3", credentials=creds)
    cal_list = service.calendarList().list().execute()
    calendars = cal_list.get("items", [])
    print(f"✅ Found {len(calendars)} calendar(s) in your account:")
    for cal in calendars:
        print(f"   - {cal['summary']} (ID: {cal['id']})")

    print("\nTesting Google Sheets access...")
    sheets_service = build("sheets", "v4", credentials=creds)
    print("✅ Google Sheets API connected successfully.")

    print("\n🎉 Setup complete! You can now run the main application.")
    print("   Make sure to note your Google Calendar ID from the list above.")


if __name__ == "__main__":
    main()
