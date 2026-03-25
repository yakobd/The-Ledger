# scripts/test_what_if.py

import sys, os, asyncio, uuid
from dotenv import load_dotenv

# --- Path Setup ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.event_store import EventStore
from src.what_if.projector import run_what_if_simulation
from src.models.events import CreditAnalysisCompleted

# --- Test Config ---
TEST_APPLICATION_ID = "APEX-WHAT-IF"

async def setup_base_scenario(store: EventStore):
    """Creates a realistic 'happy path' scenario that results in an approval."""
    print("--- Setting up base scenario for What-If test ---")
    
    # For this test, we just need to create the events the Orchestrator reads
    await store.append(stream_id=f"loan-{TEST_APPLICATION_ID}", events=[{"event_type": "ApplicationSubmitted", "payload": {}, "event_version": 1}], expected_version=0)
    
    # The REAL outcome was LOW risk
    real_credit_event = {
        "event_type": "CreditAnalysisCompleted", "event_version": 2,
        "payload": {
            "application_id": TEST_APPLICATION_ID, "session_id": "real_session",
            "decision": {"risk_tier": "LOW", "recommended_limit_usd": 200000}
        }
    }
    await store.append(stream_id=f"credit-{TEST_APPLICATION_ID}", events=[real_credit_event], expected_version=0)
    
    # Other agents passed
    await store.append(stream_id=f"fraud-{TEST_APPLICATION_ID}", events=[{"event_type": "FraudScreeningCompleted", "payload": {"recommendation": "PASS"}, "event_version": 1}], expected_version=0)
    await store.append(stream_id=f"compliance-{TEST_APPLICATION_ID}", events=[{"event_type": "ComplianceCheckCompleted", "payload": {"overall_verdict": "CLEAR"}, "event_version": 1}], expected_version=0)
    print("✅ Base scenario created.")


async def main():
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url: raise ValueError("DATABASE_URL not set")
    
    event_store = EventStore(db_url)
    await event_store.connect()

    # Create the data to test against
    await setup_base_scenario(event_store)

    # Define our counterfactual: what if credit risk had been HIGH?
    counterfactual_payload = {
        "event_type": "CreditAnalysisCompleted",
        "event_version": 2,
        "application_id": TEST_APPLICATION_ID,
        "session_id": "what_if_session",
        "decision": {
            "risk_tier": "HIGH",
            "recommended_limit_usd": 0,
            "confidence": 0.99, # <-- Added
            "rationale": "Counterfactual: High risk detected.",
            # Add placeholders for any other required fields in CreditDecision
            "key_concerns": [],
            "data_quality_caveats": [],
            "policy_overrides_applied": [],
        },
        # Add placeholders for the other required fields
        "model_version": "what_if_model_v1",         # <-- Added
        "model_deployment_id": "what_if_deployment", # <-- Added
        "input_data_hash": "what_if_hash",           # <-- Added
        "analysis_duration_ms": 1,                   # <-- Added
        "regulatory_basis": [],                      # <-- Added
        "completed_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc), #<-- Added
    }

    # Run the simulation
    what_if_result = await run_what_if_simulation(
        store=event_store,
        application_id=TEST_APPLICATION_ID,
        branch_at_event_type="CreditAnalysisCompleted",
        counterfactual_event_payload=counterfactual_payload
    )
    
    # Verify the outcome
    print("\n--- Verifying Result ---")
    final_verdict = what_if_result.get("what_if_verdict")
    assert final_verdict == "DECLINE", f"Expected 'DECLINE', but got '{final_verdict}'"
    print("✅ What-If scenario correctly resulted in a DECLINE verdict!")
    print("\n🎉 PHASE 6 (BONUS) COMPLETE AND VERIFIED! 🎉")


if __name__ == "__main__":
    from scripts.init_db import main as init_db
    print("Initializing clean database...")
    asyncio.run(init_db())
    
    asyncio.run(main())
