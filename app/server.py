"""
FastAPI Server.
Defines the unified webhook endpoint for the LangGraph ReAct Voice Agent.
"""

import json
import logging
from fastapi import FastAPI, HTTPException, Request
from langchain_core.messages import HumanMessage

from app.graph.graph import agent

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Voice Agent LangGraph Backend",
    description="Unified webhook endpoint for ElevenLabs voice agent tool calls",
)

@app.on_event("startup")
def startup_event():
    """Run initialization logic on server startup."""
    from app.services.google_sheets import ensure_headers
    try:
        ensure_headers()
        logger.info("[DONE] Google Sheets initialized successfully.")
    except Exception as e:
        logger.error(f"[ERROR] Failed to initialize Google Sheets: {e}")

@app.get("/")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "service": "Voice Agent Backend"}

@app.post("/chatbot")
async def chatbot_webhook(request: Request):
    """
    Unified ElevenLabs Webhook Endpoint.
    Receives JSON payload which contains the 'tool' to be executed and its arguments.
    It passes the instruction to the ReAct agent to fulfill the request intelligently.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    # CF-Ray header used as session ID to maintain history within a single call if requested multiple times
    session_id = request.headers.get("cf-ray", "default_thread")
    
    logger.info(f"Received webhook request on session {session_id}: {payload}")
    
    # We construct a natural language prompt for the agent containing the payload
    human_msg = HumanMessage(content=f"Please handle the following request payload:\n{json.dumps(payload, indent=2)}")
    
    config = {"configurable": {"thread_id": session_id}}
    
    try:
        # Run the LangGraph agent
        result = agent.invoke({"messages": [human_msg]}, config=config)
        
        # The final answer from the agent should be the last message.
        final_msg_obj = result["messages"][-1]
        
        # Extract content securely whether it's a string or a list of blocks
        if isinstance(final_msg_obj.content, str):
            final_text = final_msg_obj.content
        elif isinstance(final_msg_obj.content, list):
            # Concatenate text blocks if response is a list (common in newer Gemini/Gemma models)
            final_text = "".join([block.get("text", "") if isinstance(block, dict) else str(block) for block in final_msg_obj.content])
        else:
            final_text = str(final_msg_obj.content)

        logger.info(f"Agent finished. Final response: {final_text}")
        
        # Parse it as JSON so FastAPI returns proper JSON payload
        try:
            # Strip markdown json block wrappers if the model wrapped it
            clean_message = final_text.replace("```json", "").replace("```", "").strip()
            response_json = json.loads(clean_message)
            return response_json
        except json.JSONDecodeError:
            # If the model didn't return perfect JSON, return as text
            return {"response": final_text}
            
    except Exception as e:
        logger.exception(f"Error executing agent thread {session_id}")
        return {"error": str(e)}

