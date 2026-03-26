# src/mcp/server.py

import asyncio
from fastapi import FastAPI, HTTPException, Depends
from dotenv import load_dotenv
import os
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
from fastapi import Request


# --- Path Setup ---
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)
# ---
from .errors import mcp_exception_handler
from src.event_store import OptimisticConcurrencyError
from src.event_store import EventStore



class McpErrorDetail(BaseModel):
    error_type: str
    message: str
    suggested_action: str | None = None
    context: dict = Field(default_factory=dict)

async def mcp_exception_handler(request: Request, exc: Exception):
    # For our own ValueErrors (which aggregates raise), create a specific error
    if isinstance(exc, ValueError):
        error_detail = McpErrorDetail(
            error_type="PreconditionFailed",
            message=str(exc),
            suggested_action="Review agent logic and preconditions for this tool."
        )
        return JSONResponse(status_code=400, content=error_detail.model_dump())
    
    # For all other unexpected errors, return a generic 500
    error_detail = McpErrorDetail(
        error_type="InternalServerError",
        message="An unexpected internal error occurred.",
        context={"detail": str(exc)}
    )
    return JSONResponse(status_code=500, content=error_detail.model_dump())
# --- End of Error Handling Code ---
# --- THIS IS THE NEW PATTERN: DEPENDENCY INJECTION ---
# --- App Initialization ---
load_dotenv()
app = FastAPI(title="The Ledger - MCP", version="1.0.0")

app.add_exception_handler(Exception, mcp_exception_handler)
app.add_exception_handler(ValueError, mcp_exception_handler)
app.add_exception_handler(OptimisticConcurrencyError, mcp_exception_handler)
# This is a "singleton" pattern to ensure we only have one EventStore instance.
_event_store = None

async def get_event_store() -> EventStore:
    """
    This is a dependency that FastAPI will manage.
    It creates the EventStore and connects it on the first request,
    then reuses the same instance for all subsequent requests.
    """
    global _event_store
    if _event_store is None:
        print("MCP: First request, creating and connecting EventStore...")
        db_url = os.environ.get("DATABASE_URL")
        if not db_url: raise RuntimeError("DATABASE_URL not configured")
        _event_store = EventStore(db_url)
        await _event_store.connect()
        print("MCP: EventStore connected.")
    return _event_store

# We remove the "startup" and "shutdown" events, as this pattern handles it.

# --- API Endpoints ---

@app.get("/")
async def get_root():
    return {"status": "MCP is running"}

@app.get("/applications/{application_id}/history")
async def get_application_history(
    application_id: str,
    # This tells FastAPI: before running this function, run `get_event_store`
    # and pass its return value in as the `event_store` argument.
    event_store: EventStore = Depends(get_event_store)
):
    """
    Retrieves the full, unified event history for a given loan application.
    """
    print(f"MCP: Received request for history of {application_id}")
    
    stream_prefixes = ["loan", "docpkg", "credit", "fraud", "compliance"]
    stream_ids = [f"{prefix}-{application_id}" for prefix in stream_prefixes]
    
    all_events = []
    
    try:
        tasks = [event_store.load_stream(stream_id) for stream_id in stream_ids]
        stream_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in stream_results:
            if isinstance(result, list): all_events.extend(result)
            elif isinstance(result, Exception): print(f"-> WARNING: {result}")

        sorted_events = sorted(
            [event.model_dump(mode="json") for event in all_events], 
            key=lambda e: e.get("global_position") or 0
        )
        
        print(f"  -> Found {len(sorted_events)} total events for {application_id}.")
        return sorted_events
        
    except Exception as e:
        print(f"  -> ERROR fetching history for {application_id}: {e}")
        raise HTTPException(status_code=500, detail="An error occurred.")
    

class McpErrorDetail(BaseModel):
    error_type: str
    message: str
    suggested_action: str | None = None
    context: dict = Field(default_factory=dict)



async def mcp_exception_handler(request: Request, exc: Exception):
    # For our own ValueErrors (which our aggregates raise), we can make a nice error
    if isinstance(exc, ValueError):
        error_detail = McpErrorDetail(
            error_type="PreconditionFailed",
            message=str(exc),
            suggested_action="Review agent logic and preconditions for this tool."
        )
        return JSONResponse(status_code=400, content=error_detail.model_dump())
    
    # For all other unexpected errors
    error_detail = McpErrorDetail(
        error_type="InternalServerError",
        message="An unexpected internal error occurred.",
        context={"detail": str(exc)}
    )
    return JSONResponse(status_code=500, content=error_detail.model_dump())

# Now, in your main app creation, add the handler
# app = FastAPI(...)
# app.add_exception_handler(Exception, mcp_exception_handler)

from . import tools
from . import resources