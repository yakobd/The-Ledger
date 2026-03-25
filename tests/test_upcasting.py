# tests/test_upcasting.py

import pytest
import asyncio
import json
from dotenv import load_dotenv

# --- Path Setup ---
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
# ---

# We import the EventStore to use in our fixture type hint
from src.event_store import EventStore

# Import the fixture from our concurrency test file

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

# --- Test Data (Unchanged) ---
TEST_APPLICATION_ID = "APEX-V1-TEST"
TEST_STREAM_ID = f"credit-{TEST_APPLICATION_ID}"
V1_PAYLOAD = {
    "application_id": TEST_APPLICATION_ID,
    "session_id": "session-v1",
    "decision": {"risk_tier": "MEDIUM", "recommended_limit_usd": 75000, "rationale": "Legacy analysis."},
    "analysis_duration_ms": 150, "input_data_hash": "hash_v1", "event_version": 1
}


# --- The Test Function ---
async def test_upcasting_and_immutability(event_store: EventStore):
    """
    This function now acts as our pytest test.
    It accepts the `event_store` fixture, which provides a clean,
    connected event store for every test run.
    """
    print("🚀 Running Upcasting Verification Test")
    
    # --- 1. Manually insert a V1 event ---
    print("\n[1/4] Injecting a V1 'CreditAnalysisCompleted' event...")
    async with event_store._pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (stream_id, stream_position, event_type, event_version, payload, recorded_at)
            VALUES ($1, 1, 'CreditAnalysisCompleted', 1, $2, NOW())
            """,
            TEST_STREAM_ID, json.dumps(V1_PAYLOAD)
        )
        await conn.execute(
            "INSERT INTO event_streams (stream_id, aggregate_type, current_version) VALUES ($1, 'credit', 1)",
            TEST_STREAM_ID
        )
    print("✅ V1 event inserted.")

    # --- 2. Load the stream via the EventStore ---
    print("\n[2/4] Loading stream to trigger upcasting...")
    loaded_events = await event_store.load_stream(TEST_STREAM_ID)
    
    # --- 3. Verify the upcasting logic ---
    print("\n[3/4] Verifying the loaded event...")
    assert len(loaded_events) == 1
    upcasted_event = loaded_events[0]
    
    assert upcasted_event.event_version == 2, f"FAIL: Event version should be 2, but got {upcasted_event.event_version}"
    print("  - ✅ Event version correctly upcasted to 2.")
    
    assert 'model_version' in upcasted_event.payload
    print("  - ✅ `model_version` field was added.")
    
    print("✅ Upcasting verification successful!")

    # --- 4. Verify Immutability ---
    print("\n[4/4] Verifying raw stored event was NOT changed...")
    async with event_store._pool.acquire() as conn:
        raw_row = await conn.fetchrow("SELECT event_version, payload FROM events WHERE stream_id = $1", TEST_STREAM_ID)
        
        assert raw_row['event_version'] == 1, "FAIL: Raw event version in DB should still be 1!"
        print("  - ✅ Raw `event_version` in DB is still 1.")
        
        raw_payload_dict = json.loads(raw_row['payload'])
        assert 'model_version' not in raw_payload_dict, "FAIL: Raw payload in DB should NOT have the new fields!"
        print("  - ✅ Raw `payload` in DB does not contain upcasted fields.")

    print("✅ Immutability test successful!")
    print("\n🎉 PHASE 4A (UPCASTING) TEST PASSED! 🎉")

