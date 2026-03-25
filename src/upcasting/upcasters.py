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