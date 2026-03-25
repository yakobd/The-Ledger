# tests/test_gas_town.py

import pytest
import asyncio
import uuid
from dotenv import load_dotenv

# --- Path Setup ---
import sys, os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
# ---

from src.event_store import EventStore
from src.integrity.gas_town import reconstruct_agent_context
from src.aggregates.agent_session import AgentSessionAggregate

# Mark test as asyncio and import the shared fixture
pytestmark = pytest.mark.asyncio

async def test_gas_town_crash_recovery(event_store: EventStore):
    """
    Simulates a mid-session crash and verifies that the agent's context
    can be successfully reconstructed from its event stream.
    """
    print("🚀 Running Gas Town Crash Recovery Test")
    
    # --- Test Config ---
    TEST_AGENT_ID = "fraud_detection"
    TEST_SESSION_ID = str(uuid.uuid4())
    TEST_APP_ID = "APEX-GAS-TOWN"
    
    # --- 1. Simulate a partial agent session ---
    print(f"\n[1/3] Simulating a partial session for session: {TEST_SESSION_ID[:8]}...")
    stream_id = f"agent-{TEST_AGENT_ID}-{TEST_SESSION_ID}"
    
    agent_session = AgentSessionAggregate(agent_id=TEST_AGENT_ID, session_id=TEST_SESSION_ID)
    
    # Create and apply events to the in-memory aggregate
    start_event_obj = agent_session.start_session(application_id=TEST_APP_ID, model_version="rule_based_v1")
    agent_session._apply(start_event_obj)
    node1_event_obj = agent_session.record_node_execution(node_name="check_profitability", sequence=1, duration=50)
    agent_session._apply(node1_event_obj)
    node2_event_obj = agent_session.record_node_execution(node_name="check_balance_sheet", sequence=2, duration=30)
    agent_session._apply(node2_event_obj)

    # Save the generated events to the database
    await event_store.append(
        stream_id=stream_id,
        events=[e.to_store_dict() for e in [start_event_obj, node1_event_obj, node2_event_obj]],
        expected_version=0
    )
    print("✅ 3 events saved, simulating a crash before completion.")

    # --- 2. Run the reconstruction function ---
    # This simulates a new process starting up and trying to recover the lost context
    reconstructed_context = await reconstruct_agent_context(
        store=event_store,
        agent_id=TEST_AGENT_ID,
        session_id=TEST_SESSION_ID
    )

    # --- 3. Verify the results ---
    print("\n[3/3] Verifying reconstructed context...")
    assert reconstructed_context.last_event_position == 3, "Should have processed 3 events"
    print("  - ✅ Correct last event position.")
    assert reconstructed_context.session_health_status == "NEEDS_RECONCILIATION", "Session should be marked for reconciliation"
    print("  - ✅ Session correctly flagged as needing reconciliation.")
    assert "verbatim" in reconstructed_context.context_text, "Context should contain verbatim events"
    print("  - ✅ Context contains high-fidelity recent history.")
    print("\n🎉 PHASE 4C (GAS TOWN) TEST PASSED! 🎉")

