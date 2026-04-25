import logging
from typing import List, Dict, Any
from langchain_core.tools import tool

from app.services.google_calendar import get_free_slots, create_event
from app.services.google_sheets import append_patient_log

logger = logging.getLogger(__name__)

@tool
def think(reflection: str) -> str:
    """
    You MUST use this tool to think carefully about how to handle the provided request data.
    This tool allows you to log your step-by-step reasoning before taking an action.
    """
    logger.info(f"[THINK] {reflection}")
    return "Thought recorded. Proceed with the next step."

@tool
def get_availability(appointment_datetime: str) -> str:
    """
    Returns the availability on the Office Calendar for the given start timestamp.
    You MUST call this to find available timeslots.
    
    Args:
        appointment_datetime: ISO 8601 datetime string. Examples: '2025-05-12T03:30:00Z', '2025-05-12T09:00:00+05:30'.
    """
    logger.info(f"[TOOL: get_availability] Checking format: {appointment_datetime}")
    try:
        # Parse for day name to give better context
        from datetime import datetime
        dt_clean = appointment_datetime.replace("Z", "+00:00")
        dt_obj = datetime.fromisoformat(dt_clean)
        day_name = dt_obj.strftime("%A")

        slots = get_free_slots(appointment_datetime)
        
        if slots:
            return f"On {day_name}, I found {len(slots)} available slots: {slots}. You can now offer these to the patient."
        
        # Check if it was a weekend
        if dt_obj.weekday() >= 5:
            return f"The requested date ({appointment_datetime}) is a {day_name}. The clinic is CLOSED on weekends. DO NOT check other times on this day. Tell the patient we are only open Monday-Friday."
            
        return f"No available slots found on {day_name} at that specific time. You may check one more time for a different part of the day, but prioritize a quick response."
    except Exception as e:
        return f"Error checking availability: {str(e)}"

@tool
def create_appointment(start_timestamp: str, patient_name: str) -> str:
    """
    Creates a 1-hour appointment event for the provided start time.
    This tool may only be called ONCE in a given request. Do NOT use this tool multiple times.
    
    Args:
        start_timestamp: ISO 8601 datetime string in IST. Example: '2025-05-12T09:00:00+05:30'.
        patient_name: Name of the patient.
    """
    logger.info(f"[TOOL: create_appointment] {patient_name} at {start_timestamp}")
    try:
        result = create_event(start_timestamp, patient_name)
        return f"Appointment successfully booked. Event ID: {result.get('eventId', 'Unknown')}"
    except Exception as e:
        return f"Failed to book appointment: {str(e)}"

@tool
def log_patient_details(
    patient_name: str,
    insurance_provider: str,
    patient_question_concern: str,
    start_timestamp: str
) -> str:
    """
    Logs the call details and patient details to a Google Sheet.
    This should ONLY be called once at the very end of the call when all details are provided.
    
    Args:
        patient_name: Name of the patient.
        insurance_provider: Insurance provider.
        patient_question_concern: Patient's concerns.
        start_timestamp: Timestamp of the booked appointment.
    """
    logger.info(f"[TOOL: log_patient_details] Patient: {patient_name}")
    try:
        success = append_patient_log(
            patient_name=patient_name,
            insurance_provider=insurance_provider,
            patient_question_concern=patient_question_concern,
            start_timestamp=start_timestamp
        )
        if success:
            return "Patient details successfully logged to Google Sheets."
        else:
            return "Failed to log patient details to Google Sheets."
    except Exception as e:
        return f"Error logging patient details: {str(e)}"
