# src/integrity/gas_town.py

import json
from typing import NamedTuple, List

from src.event_store import EventStore

# Define a simple data class to hold the reconstructed context
class AgentContext(NamedTuple):
    context_text: str
    last_event_position: int
    session_health_status: str
    pending_work: List[str] # e.g., "HEALTHY", "NEEDS_RECONCILIATION"

async def reconstruct_agent_context(
    store: EventStore,
    agent_id: str,
    session_id: str,
    token_budget: int = 4000,
) -> AgentContext:
    """
    Reconstructs an agent's context from its event stream to recover from a crash.
    """
    print(f"\n--- Reconstructing Agent Context for Session: {session_id} ---")
    
    stream_id = f"agent-{agent_id}-{session_id}"
    events = await store.load_stream(stream_id)

    if not events:
        raise ValueError(f"No event stream found for session {session_id}")

    # 1. Identify last state
    last_event = events[-1]
    last_event_position = last_event.stream_position
    session_health = "HEALTHY"
    
    # Check for partial completion (a critical Gas Town requirement)
    # A simple check: if the last event isn't `AgentSessionCompleted`, something is wrong.
    # Identify pending work by looking at the last event
    pending_work = []
    if last_event.event_type != "AgentSessionCompleted":
        session_health = "NEEDS_RECONCILIATION"
        print("  -> WARNING: Session did not complete cleanly.")
        
        # Determine next logical step based on last event
        if last_event.event_type == "AgentSessionStarted":
            pending_work.append("EXECUTE_FIRST_NODE")
        elif last_event.event_type == "AgentNodeExecuted":
            # If a node just ran, the next step is to run the *next* node
            last_node = last_event.payload.get("node_name", "unknown")
            pending_work.append(f"EXECUTE_NODE_AFTER:{last_node}")
        else:
            pending_work.append("FINISH_WORKFLOW")
            
        print(f"  -> Determined pending work: {pending_work}")
    else:
        print("  -> Session completed cleanly.")

    # 2. & 3. Summarize and Preserve Events for the context window
    context_lines = []
    current_tokens = 0

    # Go through events in reverse to prioritize the most recent ones
    for event in reversed(events):
        event_str = ""
        # Preserve the last 3 events verbatim to maintain high-fidelity recent context
        if last_event_position - event.stream_position < 3:
            event_str = f"EVENT (verbatim): {event.event_type} - {json.dumps(event.payload, indent=2)}\n"
        # Summarize older events to save tokens
        else:
            event_str = f"EVENT (summary): {event.event_type} occurred at {event.recorded_at.isoformat()}.\n"
        
        # A rough token estimation (1 token ~= 4 chars)
        event_tokens = len(event_str) / 4
        
        if current_tokens + event_tokens > token_budget:
            print(f"  -> Token budget of {token_budget} reached. Halting history reconstruction.")
            break
            
        context_lines.append(event_str)
        current_tokens += event_tokens

    # Reverse again to put the context in chronological order
    context_lines.reverse()
    
    final_context_text = "".join(context_lines)
    
    print(f"  -> Reconstructed context with ~{int(current_tokens)} tokens.")

    return AgentContext(
        context_text="".join(context_lines),
        last_event_position=last_event_position,
        session_health_status=session_health,
        pending_work=pending_work # Include the new field
    )
