"""
Google Sheets service.
Handles logging patient details to a configured Google Sheet.
"""

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from googleapiclient.discovery import build

from app.services.google_auth import get_credentials

from pathlib import Path

# Resolve path to .env
_PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Appointments")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

# Column headers — make sure your Google Sheet has these as the first row
HEADERS = [
    "Patient Name",
    "Insurance Provider",
    "Question / Concern",
    "Appointment Time",
    "Logged At (UTC)",
]


_service_cache = None

def _get_service():
    """Build and return an authenticated Google Sheets service."""
    global _service_cache
    if _service_cache is None:
        creds = get_credentials()
        _service_cache = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return _service_cache


def ensure_headers():
    """
    Check if the sheet has headers in row 1. If empty, add them.
    If the tab does not exist, create it and then add headers.
    """
    service = _get_service()
    range_name = f"{SHEET_NAME}!A1:E1"
    
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=SHEET_ID, range=range_name)
            .execute()
        )
        existing = result.get("values", [])
    except Exception as e:
        # If the tab does not exist, we get a 400 Unable to parse range error
        if "Unable to parse range" in str(e):
            print(f"Tab '{SHEET_NAME}' not found. Creating it...")
            # Create the tab
            body = {
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": SHEET_NAME
                            }
                        }
                    }
                ]
            }
            service.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID, body=body
            ).execute()
            existing = []
        else:
            raise e

    if not existing:
        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=range_name,
            valueInputOption="RAW",
            body={"values": [HEADERS]},
        ).execute()


def append_patient_log(
    patient_name: str,
    insurance_provider: str,
    patient_question_concern: str,
    start_timestamp: str,
) -> bool:
    """
    Append a patient log row to the configured Google Sheet.

    Args:
        patient_name: First name of the patient
        insurance_provider: Insurance company name
        patient_question_concern: Question or concern noted during call
        start_timestamp: Confirmed appointment time (ISO string)

    Returns:
        True on success, raises on failure
    """
    logged_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    row = [
        patient_name,
        insurance_provider,
        patient_question_concern,
        start_timestamp,
        logged_at_utc,
    ]

    service = _get_service()
    range_name = f"{SHEET_NAME}!A:E"

    service.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range=range_name,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    return True
