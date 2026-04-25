"""
LangGraph ReAct Agent assembly.
Compiles an intelligent agent powered by Google GenAI (Gemma) capable of handling
ElevenLabs webhook calls with dynamic reasoning and stateful checkpoints.
"""

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage

from app.graph.state import AgentState
from app.graph.tools import think, get_availability, create_appointment, log_patient_details

import os

SYSTEM_PROMPT = """## Role
You are a fast-acting AI agent responsible for handling back-office operations at a clinic. 
You are connected to an ElevenLabs voice agent. **SPEED IS CRITICAL.** You must provide a response within 15 seconds.

## Tool Usage Instructions:
  - `think` → Use this briefly to plan your next step.
  - `get_availability` → Returns availability in IST. If the first slot is taken, find the nearest available slots. 
    **CRITICAL:** Do NOT loop more than twice. If you cannot find slots quickly, inform the patient and ask them to suggest a different day.
  - `create_appointment` → Creates a 1-hour appointment. Call ONLY ONCE.
  - `log_patient_details` → Logs info to Google Sheets. Call ONLY ONCE at the end.

## Constraints:
1. **Weekend Check:** If `get_availability` reports it is a Weekend, STOP searching immediately. Tell the patient we are closed on weekends.
2. **Time Format:** Always return times in a human-readable format for the voice agent.
3. **Output:** Return ONLY a valid JSON object string. Do not include extra conversational filler.

Example Response: { "availableSlots": ["2025-05-12T09:00:00+05:30"] }
"""

def build_graph():
    # Tools available to the LLM
    tools = [think, get_availability, create_appointment, log_patient_details]
    
    # Use gemma-2-9b-it as requested
    model_name = os.getenv("MODEL_NAME", "gemma-4-31b-it")
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0, max_retries=1)
    
    import sqlite3
    # Initialize SQLite memory checkpointer
    conn = sqlite3.connect("app_memory.db", check_same_thread=False)
    memory = SqliteSaver(conn)
    
    # Create the ReAct agent
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SystemMessage(content=SYSTEM_PROMPT),
        checkpointer=memory,
    )
    return agent

agent = build_graph()

