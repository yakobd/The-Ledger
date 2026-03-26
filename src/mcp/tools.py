# src/mcp/tools.py

from fastapi import Depends
from src.commands.models import StartAgentSession, RecordFraudScreening
from src.commands.handlers import handle_start_agent_session, handle_record_fraud_screening
from src.event_store import EventStore
from src.mcp.server import get_event_store, app # Import from our server file

# This file defines the "Command" side of the MCP API

@app.post("/tools/start_agent_session", status_code=202, tags=["MCP Tools"])
async def tool_start_agent_session(
    cmd: StartAgentSession,
    event_store: EventStore = Depends(get_event_store)
):
    """
    MCP Tool to formally start a new agent session and record its context.
    This implements the Gas Town pattern's entry point.
    """
    # We run the handler in the background to respond immediately
    # In a real system, this would use a proper background task runner like Celery.
    # For now, this is sufficient to acknowledge the request quickly.
    # asyncio.create_task(handle_start_agent_session(cmd, event_store))
    
    # For our simple test, we will await it directly.
    await handle_start_agent_session(cmd, event_store)
    return {"status": "accepted", "message": "Agent session started.", "session_id": cmd.session_id}

@app.post("/tools/record_fraud_screening", status_code=202, tags=["MCP Tools"])
async def tool_record_fraud_screening(
    cmd: RecordFraudScreening,
    event_store: EventStore = Depends(get_event_store)
):
    """
    MCP Tool for an agent to submit the results of its fraud screening.

    **Precondition:** An active agent session must have been started for the
    `session_id` provided in the command. Calling this tool without a valid,
    started session may result in an error.
    
    **Error Types:**
    - `OptimisticConcurrencyError`: Indicates a write conflict. The suggested
      action is to reload the relevant aggregates and retry the command.
    """
    await handle_record_fraud_screening(cmd, event_store)
    return {"status": "accepted", "application_id": cmd.application_id}


