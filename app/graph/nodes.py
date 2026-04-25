"""
LangGraph node functions — one per ElevenLabs tool + a router.

Node execution flow:
    START → route_tool (conditional) → [tool node] → END
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.graph.state import AgentState
from app.services.google_calendar import get_free_slots, create_event
from app.services.google_sheets import append_patient_log

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


# ── Router ──────────────────────────────────────────────────────────────────

def route_tool(state: AgentState) -> str:
    """
    Reads state["tool_name"] and returns the name of the next node to execute.
    This is used as the conditional edge function in the graph.
    """
    tool = state.get("tool_name", "")
    valid_tools = {
        "get_availability":    "get_availability_node",
        "create_appointment":  "create_appointment_node",
        "log_patient_details": "log_patient_node",
    }
    next_node = valid_tools.get(tool)
    if not next_node:
        raise ValueError(f"Unknown tool_name: '{tool}'. Must be one of: {list(valid_tools.keys())}")
    return next_node


# ── Node 1: Get Availability ─────────────────────────────────────────────────

def get_availability_node(state: AgentState) -> AgentState:
    """
    Checks Google Calendar for free 1-hour slots on the requested date.
    Returns up to 2 available slots in IST.
    """
    payload = state["input_payload"]
    appointment_datetime = payload.get("appointmentDateTime")

    if not appointment_datetime:
        return {**state, "error": "Missing field: appointmentDateTime", "response": {"availableSlots": []}}

    try:
        logger.info(f"[get_availability] Checking slots for: {appointment_datetime}")
        slots = get_free_slots(appointment_datetime)
        logger.info(f"[get_availability] Found {len(slots)} slot(s): {slots}")

        return {
            **state,
            "error": None,
            "response": {"availableSlots": slots},
        }
    except Exception as e:
        logger.error(f"[get_availability] Error: {e}")
        return {**state, "error": str(e), "response": {"availableSlots": []}}


# ── Node 2: Create Appointment ───────────────────────────────────────────────

def create_appointment_node(state: AgentState) -> AgentState:
    """
    Validates the requested slot and creates a Google Calendar event.
    Guards: no weekends, not before 9AM IST.
    """
    payload = state["input_payload"]
    start_timestamp = payload.get("start_timestamp")
    patient_name = payload.get("patient_name", "Patient")

    if not start_timestamp:
        return {**state, "error": "Missing field: start_timestamp", "response": {"success": False, "message": "Missing start_timestamp"}}

    try:
        # Parse and validate
        ts = start_timestamp.replace("Z", "+00:00")
        start_dt = datetime.fromisoformat(ts).astimezone(IST)

        # Guard: no weekends
        if start_dt.weekday() >= 5:
            return {
                **state,
                "error": "Weekend booking rejected",
                "response": {
                    "success": False,
                    "message": "Appointments are not available on weekends. Please choose a weekday.",
                },
            }

        # Guard: not before 9AM IST
        if start_dt.hour < 9:
            return {
                **state,
                "error": "Before clinic hours",
                "response": {
                    "success": False,
                    "message": "Appointments cannot be booked before 9:00 AM IST.",
                },
            }

        logger.info(f"[create_appointment] Booking for {patient_name} at {start_dt}")
        result = create_event(start_timestamp, patient_name)
        logger.info(f"[create_appointment] Created event: {result['eventId']}")

        friendly_time = start_dt.strftime("%A, %d %B at %I:%M %p IST")

        return {
            **state,
            "error": None,
            "response": {
                "success": True,
                "message": f"Appointment booked for {patient_name} on {friendly_time}.",
                "eventId": result["eventId"],
            },
        }

    except Exception as e:
        logger.error(f"[create_appointment] Error: {e}")
        return {
            **state,
            "error": str(e),
            "response": {"success": False, "message": f"Failed to book appointment: {str(e)}"},
        }


# ── Node 3: Log Patient Details ───────────────────────────────────────────────

def log_patient_node(state: AgentState) -> AgentState:
    """
    Logs patient information to Google Sheets after appointment is confirmed.
    """
    payload = state["input_payload"]

    patient_name = payload.get("patient_name", "")
    insurance_provider = payload.get("insurance_provider", "")
    concern = payload.get("patient_question_concern", "")
    start_timestamp = payload.get("start_timestamp", "")

    try:
        logger.info(f"[log_patient] Logging details for patient: {patient_name}")
        success = append_patient_log(
            patient_name=patient_name,
            insurance_provider=insurance_provider,
            patient_question_concern=concern,
            start_timestamp=start_timestamp,
        )
        logger.info(f"[log_patient] Log written: {success}")

        return {
            **state,
            "error": None,
            "response": {"logged": True},
        }

    except Exception as e:
        logger.error(f"[log_patient] Error: {e}")
        return {
            **state,
            "error": str(e),
            "response": {"logged": False, "error": str(e)},
        }
