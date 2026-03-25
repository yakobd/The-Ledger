# mcp.py

import asyncio
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import os

# --- Add sys.path modification at the very top ---
import sys
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)
# ---

from src.event_store import EventStore

# --- App Initialization ---

# Load environment variables from .env file
load_dotenv()

# Create a global EventStore instance that the API can use
event_store = EventStore(os.environ.get("DATABASE_URL"))

# Create the FastAPI application instance
app = FastAPI(
    title="The Ledger - Master Control Program (MCP)",
    description="API for auditing and interacting with the loan processing system.",
    version="1.0.0"
)

# --- API Lifecycle Events ---

@app.on_event("startup")
async def startup_event():
    """Connect to the database when the API server starts."""
    print("MCP starting up...")
    if not event_store._pool:
        await event_store.connect()
    print("MCP connected to database.")

@app.on_event("shutdown")
async def shutdown_event():
    """Disconnect from the database when the API server shuts down."""
    print("MCP shutting down...")
    if event_store._pool:
        await event_store.close()
    print("MCP disconnected from database.")


# --- API Endpoints ---

@app.get("/")
async def get_root():
    """Root endpoint to check if the server is running."""
    return {"status": "MCP is running"}


# --- TODO: Implement the main audit endpoint ---
@app.get("/applications/{application_id}/history")
async def get_application_history(application_id: str):
    """
    Retrieves the full, unified event history for a given loan application.
    """
    print(f"MCP: Received request for history of {application_id}")
    
    # Define all the streams related to a single application
    stream_prefixes = ["loan", "docpkg", "credit", "fraud", "compliance"]
    stream_ids = [f"{prefix}-{application_id}" for prefix in stream_prefixes]
    
    all_events = []
    
    try:
        # Load events from all related streams concurrently
        tasks = [event_store.load_stream(stream_id) for stream_id in stream_ids]
        stream_results = await asyncio.gather(*tasks)
        
        # Flatten the list of lists into a single list of events
        for event_list in stream_results:
            all_events.extend(event_list)
            
        # Sort the unified list by global_position to get the true chronological order
        # Pydantic models need to be converted to dicts for the response
        sorted_events = sorted(
            [event.model_dump(mode="json") for event in all_events], 
            key=lambda e: e.get("global_position")
        )
        
        print(f"  -> Found {len(sorted_events)} total events for {application_id}.")
        return sorted_events
        
    except Exception as e:
        print(f"  -> ERROR fetching history for {application_id}: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while fetching event history.")

