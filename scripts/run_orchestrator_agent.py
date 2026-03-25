# scripts/run_orchestrator_agent.py

# --- START: EXPLICIT PATH MODIFICATION ---
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
# --- END: EXPLICIT PATH MODIFICATION ---

import asyncio
from dotenv import load_dotenv
from decimal import Decimal

from src.event_store import EventStore
from src.aggregates.loan_application import LoanApplicationAggregate as LoanApplication
from ledger_agents.decision_orchestrator_agent import DecisionOrchestratorAgent, DecisionOrchestratorState
from src.models.events import ApplicationSubmitted # Import the specific event class

# --- Configuration ---
TEST_APPLICATION_ID = "APEX-0100" 

async def setup_prerequisite_events(event_store: EventStore):
    """
    This function creates all the '...Completed' events from other agents
    that the orchestrator needs to read.
    """
    print("\n--- Setting up prerequisite events from other agents ---")

    # 1. Create a placeholder CreditAnalysisCompleted event
    credit_stream_id = f"credit-{TEST_APPLICATION_ID}"
    credit_event = {
        "event_type": "CreditAnalysisCompleted", "event_version": 2,
        "payload": {
            "application_id": TEST_APPLICATION_ID, "session_id": "dummy_credit_session",
            "decision": {
                "risk_tier": "LOW", "recommended_limit_usd": 150000,
                "confidence": 0.92, "rationale": "Strong revenue and low debt."
            }
        }
    }
    await event_store.append(stream_id=credit_stream_id, events=[credit_event], expected_version=0)
    print("✅ Placeholder CreditAnalysisCompleted event created.")

    # 2. Create a placeholder FraudScreeningCompleted event
    fraud_stream_id = f"fraud-{TEST_APPLICATION_ID}"
    fraud_event = {
        "event_type": "FraudScreeningCompleted", "event_version": 1,
        "payload": {
            "application_id": TEST_APPLICATION_ID, "session_id": "dummy_fraud_session",
            "fraud_score": 0.15, "risk_level": "LOW", "anomalies_found": 0, "recommendation": "PASS"
        }
    }
    await event_store.append(stream_id=fraud_stream_id, events=[fraud_event], expected_version=0)
    print("✅ Placeholder FraudScreeningCompleted event created.")

    # 3. Create a placeholder ComplianceCheckCompleted event
    compliance_stream_id = f"compliance-{TEST_APPLICATION_ID}"
    compliance_event = {
        "event_type": "ComplianceCheckCompleted", "event_version": 1,
        "payload": {
            "application_id": TEST_APPLICATION_ID, "session_id": "dummy_compliance_session",
            "overall_verdict": "CLEAR", "has_hard_block": False
        }
    }
    await event_store.append(stream_id=compliance_stream_id, events=[compliance_event], expected_version=0)
    print("✅ Placeholder ComplianceCheckCompleted event created.")
    print("----------------------------------------------------")


async def main():
    """
    This script runs the full end-to-end process before invoking the orchestrator.
    """
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    api_key = os.environ.get("GOOGLE_API_KEY") # Ensure this is in your .env file
    if not db_url or not api_key:
        raise ValueError("DATABASE_URL and GOOGLE_API_KEY must be set in .env file")

    event_store = EventStore(db_url)
    await event_store.connect()

    # --- THIS BLOCK IS NOW CORRECT ---
    # Create the initial ApplicationSubmitted event for our test application
    loan_app_stream_id = f"loan-{TEST_APPLICATION_ID}"
    print(f"\n-> Creating initial ApplicationSubmitted event for {loan_app_stream_id}")
    submit_event = ApplicationSubmitted(
        application_id=TEST_APPLICATION_ID, applicant_id="COMP-XYZ",
        requested_amount_usd=100000, loan_purpose="working_capital",
        loan_term_months=24, submission_channel="ONLINE",
        contact_email="test@test.com", contact_name="Test User",
        submitted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
        application_reference="ref-123"
    )
    await event_store.append(
        stream_id=loan_app_stream_id,
        events=[submit_event.to_store_dict()],
        expected_version=0
    )
    print(f"✅ Initial LoanApplication stream created for {TEST_APPLICATION_ID}")
    # --- END OF CORRECTION ---

    await setup_prerequisite_events(event_store)
    
    agent_input: DecisionOrchestratorState = {
        "application_id": TEST_APPLICATION_ID,
        "credit_analysis_output": {}, "fraud_screening_output": {},
        "compliance_check_output": {}, "decision": {}
    }

    print("\n🚀 Running Decision Orchestrator Agent")
    print("="*60)
    
    agent = DecisionOrchestratorAgent(event_store)
    
    final_state = {}
    async for event in agent.workflow.astream_events(agent_input, version="v1"):
        kind = event["event"]
        if kind == "on_end":
            final_state = event["data"]["output"]
        print(f"-> Agent Event: {kind}, Node: {event['name']}")
        print(f"   Payload: {event['data'].get('output') or event['data'].get('input')}\n")

    print("\n✅ Orchestrator workflow finished.")
    print("========================================")
    print(f"\n🔎 To verify, check the 'events' table for a final 'ApplicationApproved' or 'ApplicationDeclined' event in the '{loan_app_stream_id}' stream.")


if __name__ == "__main__":
    from scripts.init_db import main as init_db
    print("Initializing clean database...")
    asyncio.run(init_db())
    
    print("\nRunning full orchestration test...")
    asyncio.run(main())
