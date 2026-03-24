# src/aggregates/base.py
from datetime import datetime, timezone
from src.models.events import BaseEvent

class BaseAggregate:
    def __init__(self):
        self.version: int = 0
        self.new_events: list[BaseEvent] = []
        self.stream_id: str | None = None

    def apply_events(self, events: list[BaseEvent]):
        for event in events:
            self._apply(event)
            self.version += 1
        self.new_events = []

    def record(self, event: BaseEvent):
        self._apply(event)
        self.new_events.append(event)
        self.version += 1
    
    def _apply(self, event: BaseEvent):
        # --- THIS IS THE FIX ---
        # We need to dispatch based on the event_type STRING, not the class name.
        method_name = f"_apply_{event.event_type}"
        method = getattr(self, method_name, lambda e: None)
        method(event)
        
    def has_new_events(self) -> bool:
            return len(self.new_events) > 0

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
