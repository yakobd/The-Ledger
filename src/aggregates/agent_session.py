#Phase-2 Step-2: Implement AgentSessionAggregate (Gas Town Memory)

from typing import List
from src.event_store import EventStore
from src.models.events import StoredEvent

class AgentSessionAggregate:
    def __init__(self, agent_id: str, session_id: str):
        self.agent_id = agent_id
        self.session_id = session_id
        self.context_loaded = False
        self.model_version = None
        self.version = -1

    @classmethod
    async def load(cls, store: EventStore, agent_id: str, session_id: str) -> "AgentSessionAggregate":
        """Reconstruct agent session by replaying its stream."""
        stream_id = f"agent-{agent_id}-{session_id}"
        events: List[StoredEvent] = await store.load_stream(stream_id)
        agg = cls(agent_id, session_id)
        for event in events:
            agg._apply(event)
        return agg

    def _apply(self, event: StoredEvent) -> None:
        handler = getattr(self, f"_on_{event.event_type}", None)
        if handler:
            handler(event)
        self.version = event.stream_position

    def _on_AgentSessionStarted(self, event: StoredEvent) -> None:
        self.context_loaded = True
        self.model_version = event.payload["model_version"]

    def assert_context_loaded(self) -> None:
        if not self.context_loaded:
            raise ValueError(f"AgentSession {self.session_id} has no context loaded (Gas Town violation)")

    def assert_model_version_current(self, provided_version: str) -> None:
        if self.model_version != provided_version:
            raise ValueError(f"Model version mismatch: stored {self.model_version}, provided {provided_version}")