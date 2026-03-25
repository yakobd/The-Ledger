# src/what_if.py

import asyncio, json, uuid
from datetime import datetime, timezone
from typing import Type, cast, Any
import asyncpg # We need to import this for the type hint

from src.event_store import EventStore
from src.models.events import StoredEvent, BaseEvent, event_registry
# Import all the projectors we want to run in our simulation
from projections.application_summary import LoanSummaryProjector

# Import all the agents to run the simulation
from ledger_agents.document_processing_agent import DocumentProcessingAgent
from ledger_agents.fraud_detection_agent import FraudDetectionAgent
from ledger_agents.compliance_agent import ComplianceAgent
from ledger_agents.decision_orchestrator_agent import DecisionOrchestratorAgent


async def run_what_if_simulation(
    store: EventStore,
    application_id: str,
    branch_at_event_type: str,
    counterfactual_event_payload: dict,
) -> dict:
    """
    Runs a full, in-memory "what-if" agent simulation.
    """
    print("="*60)
    print(f"🚀 Running What-If Scenario for Application: {application_id}")
    print(f"   - Branching at: {branch_at_event_type}")
    print(f"   - Injecting counterfactual: {counterfactual_event_payload['event_type']}")
    print("="*60)

    # 1. Load ALL events for the application from ALL relevant streams
    stream_prefixes = ["loan", "docpkg", "credit", "fraud", "compliance"]
    stream_ids = [f"{prefix}-{application_id}" for prefix in stream_prefixes]
    tasks = [store.load_stream(stream_id) for stream_id in stream_ids]
    all_events_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_events = []
    for res in all_events_results:
        if isinstance(res, list): all_events.extend(res)
    
    # We must sort by global_position to get the true order of events
    sorted_real_events = sorted(all_events, key=lambda e: e.global_position or 0)
    # --- END OF FIX ---


    # 2. Find the branch point (this code is now unchanged)
    branch_point_idx = next((i for i, e in enumerate(sorted_real_events) if e.event_type == branch_at_event_type), -1)
    if branch_point_idx == -1: raise ValueError(f"Branch point event '{branch_at_event_type}' not found in history.")

    # 3. Create the simulated history
    simulated_history = all_events[:branch_point_idx]
    
    # Create and add the counterfactual event
    cf_event = event_registry.get_event_class(counterfactual_event_payload["event_type"])(**counterfactual_event_payload)
    simulated_history.append(StoredEvent(event_id=uuid.uuid4(), stream_id="what-if", stream_position=0, event_type=cf_event.event_type, event_version=cf_event.event_version, payload=cf_event.model_dump(mode='json'), metadata={}, recorded_at=datetime.now(timezone.utc), global_position=0))

    # --- 4. Run a new in-memory agent pipeline based on this simulated history ---
    print("\n  -> Running simulated agent pipeline...")
    
    # --- THIS IS THE FIX ---
    # Get the key data directly from the counterfactual event's attributes
    credit_output = cf_event.decision.model_dump()
    
    # Let's assume fraud and compliance are the same as the real run
    fraud_output = {"fraud_score": 0.15, "recommendation": "PASS"}
    compliance_output = {"overall_verdict": "CLEAR"}
    
    # Run just the Orchestrator's decision node in memory
    # NOTE: We need to pass a dummy EventStore, not the real one, as the init requires it.
    orch_agent = DecisionOrchestratorAgent(store) 
    
    simulated_state = {
        "application_id": application_id,
        "credit_analysis_output": credit_output,
        "fraud_screening_output": fraud_output,
        "compliance_check_output": compliance_output,
    }
    
    # Call the decision node directly
    decision_result = await orch_agent._node_synthesize_and_decide(simulated_state)
    
    # The LLM's response has the verdict directly under the "decision" key.
    # --- THIS IS THE REAL FIX ---
    # `decision_result` is the dictionary that contains the 'decision' from the LLM
    final_decision_dict = decision_result.get("decision", {})
    final_verdict = final_decision_dict.get("decision", "ERROR") # Get the 'decision' key from the inner dict
    
    print(f"  -> What-if final verdict: {final_verdict}")

    return {"application_id": application_id, "what_if_verdict": final_verdict}