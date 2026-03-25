# src/upcasting/registry.py

from typing import Callable, Type, Any

# By using 'Any' here, we break the circular dependency.
# The class doesn't need to know the full structure of BaseEvent,
# just that it's a type.
BaseEvent = Type[Any]

class EventRegistry:
    """
    A central registry for event types and their upcasting functions.
    """
    def __init__(self):
        self._event_map: dict[str, BaseEvent] = {}
        self._upcasters: dict[tuple[str, int], Callable] = {}

    def register(self, event_class: BaseEvent, event_name: str = None):
        """Decorator to register an event class."""
        name = event_name or event_class.__name__
        self._event_map[name] = event_class
        return event_class

    def get_event_class(self, name: str) -> BaseEvent | None:
        return self._event_map.get(name)

    def register_upcaster(self, event_name: str, from_version: int):
        """Decorator for registering an upcaster function."""
        def decorator(func: Callable[[dict], dict]) -> Callable:
            if (event_name, from_version) in self._upcasters:
                raise ValueError(f"Upcaster for {event_name} v{from_version} is already registered.")
            self._upcasters[(event_name, from_version)] = func
            return func
        return decorator

    def upcast(self, event_type: str, event_payload: dict) -> dict:
        """Fully upcasts an event payload from its original version to the latest."""
        current_payload = event_payload.copy()
        version = current_payload.get("event_version", 1)
        
        while (event_type, version) in self._upcasters:
            upcaster_func = self._upcasters[(event_type, version)]
            current_payload = upcaster_func(current_payload)
            new_version = current_payload.get("event_version", version)
            if new_version == version:
                break
            version = new_version
            
        return current_payload

# Create a single, global instance that the whole application will use
event_registry = EventRegistry()
