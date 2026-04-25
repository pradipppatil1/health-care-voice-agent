"""
Google Calendar service.
Handles availability checks and appointment creation.
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from googleapiclient.discovery import build

from app.services.google_auth import get_credentials

from pathlib import Path

# Resolve path to .env
_PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
IST = ZoneInfo(TIMEZONE)
UTC = ZoneInfo("UTC")

# Clinic hours in IST
CLINIC_OPEN_HOUR = 9   # 9:00 AM IST
CLINIC_CLOSE_HOUR = 18  # 6:00 PM IST
SLOT_DURATION_HOURS = 1
MAX_SLOTS_TO_RETURN = 2


_service_cache = None

def _get_service():
    """Build and return an authenticated Google Calendar service."""
    global _service_cache
    if _service_cache is None:
        creds = get_credentials()
        _service_cache = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return _service_cache


def get_free_slots(appointment_datetime_iso: str) -> list[str]:
    """
    Given a requested appointment datetime (ISO UTC string),
    return up to 2 available 1-hour slots for that day between 9AM–6PM IST.

    Args:
        appointment_datetime_iso: ISO format datetime string e.g. "2025-05-12T03:30:00Z"

    Returns:
        List of available slot start times as ISO strings in IST.
        Empty list if no slots available or if date falls on weekend.
    """
    # Parse the incoming datetime — support both Z-suffix and +offset formats
    appointment_datetime_iso = appointment_datetime_iso.replace("Z", "+00:00")
    try:
        requested_dt = datetime.fromisoformat(appointment_datetime_iso)
    except ValueError:
        raise ValueError(f"Invalid datetime format: {appointment_datetime_iso}")

    # Convert to IST to determine the actual date
    requested_ist = requested_dt.astimezone(IST)

    # Reject weekends
    if requested_ist.weekday() >= 5:  # 5=Saturday, 6=Sunday
        return []

    # Build the full day window in IST: 9AM to 6PM
    day_start_ist = requested_ist.replace(
        hour=CLINIC_OPEN_HOUR, minute=0, second=0, microsecond=0
    )
    day_end_ist = requested_ist.replace(
        hour=CLINIC_CLOSE_HOUR, minute=0, second=0, microsecond=0
    )

    # Convert window to UTC for Google API
    day_start_utc = day_start_ist.astimezone(UTC)
    day_end_utc = day_end_ist.astimezone(UTC)

    # Query Google Calendar FreeBusy API
    service = _get_service()
    body = {
        "timeMin": day_start_utc.isoformat(),
        "timeMax": day_end_utc.isoformat(),
        "timeZone": "UTC",
        "items": [{"id": CALENDAR_ID}],
    }
    freebusy_result = service.freebusy().query(body=body).execute()
    busy_blocks = freebusy_result.get("calendars", {}).get(CALENDAR_ID, {}).get("busy", [])

    # Convert busy blocks to datetime ranges
    busy_ranges = []
    for block in busy_blocks:
        start = datetime.fromisoformat(block["start"].replace("Z", "+00:00")).astimezone(IST)
        end = datetime.fromisoformat(block["end"].replace("Z", "+00:00")).astimezone(IST)
        busy_ranges.append((start, end))

    # Find free 1-hour slots
    free_slots = []
    current = day_start_ist

    while current + timedelta(hours=SLOT_DURATION_HOURS) <= day_end_ist:
        slot_end = current + timedelta(hours=SLOT_DURATION_HOURS)

        # Check if this slot overlaps with any busy block
        is_busy = any(
            not (slot_end <= busy_start or current >= busy_end)
            for busy_start, busy_end in busy_ranges
        )

        if not is_busy:
            free_slots.append(current.isoformat())
            if len(free_slots) >= MAX_SLOTS_TO_RETURN:
                break

        current += timedelta(hours=SLOT_DURATION_HOURS)

    return free_slots


def create_event(start_timestamp_iso: str, patient_name: str) -> dict:
    """
    Create a 1-hour appointment event in Google Calendar.

    Args:
        start_timestamp_iso: ISO format start time (IST or UTC)
        patient_name: First name of the patient

    Returns:
        dict with eventId and htmlLink
    """
    # Parse and normalise to IST
    start_timestamp_iso = start_timestamp_iso.replace("Z", "+00:00")
    start_dt = datetime.fromisoformat(start_timestamp_iso).astimezone(IST)
    end_dt = start_dt + timedelta(hours=SLOT_DURATION_HOURS)

    service = _get_service()
    event_body = {
        "summary": f"Appointment - {patient_name}",
        "description": f"Initial appointment for patient: {patient_name}",
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 60},
                {"method": "popup", "minutes": 15},
            ],
        },
    }

    created_event = service.events().insert(
        calendarId=CALENDAR_ID, body=event_body
    ).execute()

    return {
        "eventId": created_event.get("id"),
        "htmlLink": created_event.get("htmlLink"),
        "start": start_dt.strftime("%A, %d %B at %I:%M %p IST"),
    }
