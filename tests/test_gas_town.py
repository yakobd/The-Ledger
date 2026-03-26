# tests/test_gas_town.py

import pytest, asyncio, uuid
from src.event_store import EventStore
from src.integrity.gas_town import reconstruct_agent_context
from src.aggregates.agent_session import AgentSessionAggregate
from src.models.events import AgentSessionStarted, AgentNodeExecuted, AgentToolCalled # Import new event

pytestmark = pytest.mark.asyncio

async def test_gas_town_crash_recovery_with_pending_work(event_store: EventStore):
    """
    Simulates a crash after 5 events and verifies the reconstructed context
    correctly identifies the pending work.
    """
    print("🚀 Running Gas Town Test with Pending Work")
    TEST_AGENT_ID = "fraud_detection"
    TEST_SESSION_ID = str(uuid.uuid4())
    TEST_APP_ID = "APEX-GAS-TOWN-2"
    stream_id = f"agent-{TEST_AGENT_ID}-{TEST_SESSION_ID}"
    
    # 1. Simulate a richer, 5-event partial session
    print(f"\n[1/3] Simulating a 5-event session for: {TEST_SESSION_ID[:8]}...")
    agent_session = AgentSessionAggregate(agent_id=TEST_AGENT_ID, session_id=TEST_SESSION_ID)
    
    # Create and apply events in memory
    events_to_save = [
        agent_session.start_session(application_id=TEST_APP_ID, model_version="rule_based_v1.1"),
        agent_session.record_node_execution(node_name="start_screening", sequence=1, duration=10),
        agent_session.record_node_execution(node_name="check_profitability", sequence=2, duration=50),
        # Let's add a tool call event
        AgentToolCalled(session_id=TEST_SESSION_ID, agent_type=TEST_AGENT_ID, tool_name="query_registry", tool_input_summary="ein=...", tool_output_summary="found=true", tool_duration_ms=120),
        agent_session.record_node_execution(node_name="check_balance_sheet", sequence=3, duration=30)
    ]
    for e in events_to_save: agent_session._apply(e)
    
    # Save all 5 events
    await event_store.append(
        stream_id=stream_id,
        events=[e.to_store_dict() for e in events_to_save],
        expected_version=0
    )
    print("✅ 5 events saved, simulating a crash after the 'check_balance_sheet' node.")

    # 2. Run the reconstruction
    reconstructed_context = await reconstruct_agent_context(
        store=event_store,
        agent_id=TEST_AGENT_ID,
        session_id=TEST_SESSION_ID
    )

    # 3. Verify the richer context
    print("\n[3/3] Verifying reconstructed context...")
    assert reconstructed_context.last_event_position == 5
    print("  - ✅ Correct last event position (5).")
    assert reconstructed_context.session_health_status == "NEEDS_RECONCILIATION"
    print("  - ✅ Session correctly flagged as needing reconciliation.")
    
    # --- THIS IS THE NEW ASSERTION ---
    assert len(reconstructed_context.pending_work) > 0, "Pending work should have been identified"
    assert reconstructed_context.pending_work[0] == "EXECUTE_NODE_AFTER:check_balance_sheet"
    print(f"  - ✅ Correct pending work identified: {reconstructed_context.pending_work}")
    
    print("\n🎉 PHASE 4C (GAS TOWN) TEST PASSED! 🎉")
