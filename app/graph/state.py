"""
LangGraph AgentState definition.
"""

from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

class AgentState(TypedDict):
    """
    State for the ReAct Agent.
    Requires exactly 'messages' to be compatible with standard Agent routines,
    but can be extended if additional data needs tracking.
    """
    messages: Annotated[list[AnyMessage], add_messages]
