# src/mcp/server.py

import asyncio
from fastapi import FastAPI, HTTPException, Depends
from dotenv import load_dotenv
import os

# --- Path Setup ---
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)
# ---

from src.event_store import EventStore

# --- App Initialization ---
load_dotenv()
app = FastAPI(title="The Ledger - MCP", version="1.0.0")

# --- THIS IS THE NEW PATTERN: DEPENDENCY INJECTION ---

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
    

from . import tools
from . import resources