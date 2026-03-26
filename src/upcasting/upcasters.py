from src.upcasting.registry import event_registry
import asyncio
from .registry import event_registry

@event_registry.register_upcaster("CreditAnalysisCompleted", from_version=1)
def upcast_credit_analysis_v1_to_v2(payload: dict) -> dict:
    """
    Upcasts a V1 CreditAnalysisCompleted event to V2.
    """
    print(f"DEBUG: Upcasting CreditAnalysisCompleted event from v1 to v2...")
    new_payload = payload.copy()
    new_payload["model_version"] = "legacy-rules-engine-2025"
    new_payload["confidence_score"] = None
    new_payload["regulatory_basis"] = []
    new_payload["event_version"] = 2
    return new_payload

@event_registry.register_upcaster("DecisionGenerated", from_version=1)
def upcast_decision_v1_to_v2(payload: dict) -> dict:
    """
    Upcasts a V1 DecisionGenerated event to V2.
    
    This is an advanced upcaster that performs an I/O operation
    to enrich the event with data from other streams.
    """
    print("DEBUG: Upcasting DecisionGenerated event from v1 to v2...")
    new_payload = payload.copy()
    
    # The V1 event has a list of session IDs that contributed
    contributing_sessions = payload.get("contributing_agent_sessions", [])
    
    model_versions = {}
    
    # --- This is the complex part: I/O inside an upcaster ---
    # We need to load the AgentSessionStarted event for each session
    # to find out what model version it used.
    # This is a simplified, synchronous-in-async implementation for clarity.
    # In a real high-performance system, this would be a batch lookup.
    
    # We need the event store, but we don't have it here. This is a design
    # challenge. For this project, we will simulate the lookup. In a real
    # system, you might pass a DB connection pool to the upcaster registry.
    
    for session_id in contributing_sessions:
        if "credit" in session_id:
            model_versions["credit"] = "credit_model_v1_legacy"
        if "fraud" in session_id:
            model_versions["fraud"] = "fraud_model_v1_legacy"

    new_payload["model_versions"] = model_versions
    new_payload["event_version"] = 2
    
    return new_payload