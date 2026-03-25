#Phase-2 Step-2: Implement AgentSessionAggregate (Gas Town Memory)
from __future__ import annotations
from typing import List
from src.event_store import EventStore
from src.models.events import StoredEvent
from src.models.events import BaseEvent 


class AgentSessionAggregate:
    def __init__(self, agent_id: str, session_id: str):
        self.agent_id = agent_id
        self.session_id = session_id
        self.context_loaded = False
        self.model_version = None
        self.version = -1

    def start_session(self, application_id: str, model_version: str):
        # The guard clause is removed from here.
        from src.models.events import AgentSessionStarted
        return AgentSessionStarted(
            session_id=self.session_id,
            agent_type=self.agent_id, # Assuming agent_id is the type
            agent_id=self.agent_id,
            application_id=application_id,
            model_version=model_version,
            langgraph_graph_version="v1",
            context_source="stream_history",
            context_token_count=0,
            started_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)
        )

    def record_node_execution(self, node_name: str, sequence: int, duration: int):
        self.assert_context_loaded()
        from src.models.events import AgentNodeExecuted
        return AgentNodeExecuted(
            session_id=self.session_id,
            agent_type=self.agent_id,
            node_name=node_name,
            node_sequence=sequence,
            input_keys=[],
            output_keys=[],
            llm_called=False, # Placeholder
            duration_ms=duration,
            executed_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)
        )

    def complete_session(self, total_cost: float):
        from src.models.events import AgentSessionCompleted
        return AgentSessionCompleted(
            session_id=self.session_id,
            agent_type=self.agent_id,
            application_id="unknown", # We'd need to load this
            total_nodes_executed=0, # We'd need to count this
            total_llm_calls=0,
            total_tokens_used=0,
            total_cost_usd=total_cost,
            total_duration_ms=0,
            completed_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)
        )
    
    @classmethod
    async def load(cls, store: EventStore, agent_id: str, session_id: str) -> "AgentSessionAggregate":
        """Reconstruct agent session by replaying its stream."""
        stream_id = f"agent-{agent_id}-{session_id}"
        events: List[StoredEvent] = await store.load_stream(stream_id)
        agg = cls(agent_id, session_id)
        for event in events:
            agg._apply(event)
        return agg

    def _apply(self, event: "StoredEvent | BaseEvent") -> None:
    # Get the event type string, whether it's a StoredEvent or a typed model
        event_type = event.event_type if hasattr(event, 'event_type') else event.__class__.__name__
        
        handler = getattr(self, f"_on_{event_type}", None)
        if handler:
            handler(event)
            
        # --- THIS IS THE FIX ---
        # Only update the version if we are replaying a StoredEvent from the DB
        if hasattr(event, 'stream_position'):
            self.version = event.stream_position
        else:
            # If it's a new event, we just increment the in-memory version
            self.version += 1
        # --- END OF FIX ---

    def _on_AgentSessionStarted(self, event: "StoredEvent | AgentSessionStarted"):
        self.context_loaded = True
        
        # --- THIS IS THE FIX ---
        # Check if the event is a StoredEvent (from DB) or a typed model (from code)
        if hasattr(event, 'payload'):
            # It's a StoredEvent from the database
            self.model_version = event.payload.get("model_version")
        else:
            # It's a new, typed Pydantic model
            self.model_version = event.model_version
        # --- END OF FIX ---

    def assert_context_loaded(self) -> None:
        if not self.context_loaded:
            raise ValueError(f"AgentSession {self.session_id} has no context loaded (Gas Town violation)")

    def assert_model_version_current(self, provided_version: str) -> None:
        if self.model_version != provided_version:
            raise ValueError(f"Model version mismatch: stored {self.model_version}, provided {provided_version}")