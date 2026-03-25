# src/models/__init__.py

# 1. First, import the registry object itself and all the event classes.
#    This ensures the registry instance exists and all @event_registry.register decorators run.
from .events import event_registry, BaseEvent, StoredEvent, DomainError, OptimisticConcurrencyError
from .events import (
    # Copy ALL your event class names here from events.py
    ApplicationSubmitted, ApplicationApproved, ApplicationDeclined,
    PackageCreated, DocumentAdded, ExtractionCompleted, ExtractionFailed, PackageReadyForAnalysis,
    AgentSessionStarted, AgentSessionCompleted, DecisionGenerated,
    CreditAnalysisCompleted, FraudScreeningCompleted, ComplianceCheckCompleted,
    # Add any other event classes you have...
)


# 2. Second, explicitly import the module that contains the upcaster function.
#    This will run the @event_registry.register_upcaster decorator.
#    We can import it under a different name to avoid circular dependencies if needed.
from . import events as _upcasters_module

# 3. Now, export the fully populated registry for the rest of the app to use.
__all__ = [
    "event_registry",
    "BaseEvent",
    "StoredEvent",
    # ... include other core classes you want to be easily accessible
]
