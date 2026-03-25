# scripts/test_upcasting.py

import sys, os, asyncio, uuid, json
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


from dotenv import load_dotenv
from src.event_store import EventStore


# --- Path Setup ---


from src.event_store import EventStore

# --- Test Config ---
TEST_APPLICATION_ID = "APEX-V1-TEST"
TEST_STREAM_ID = f"credit-{TEST_APPLICATION_ID}"

# This is a raw V1 payload, as it would have been stored in 2025.
# It is MISSING model_version, confidence_score, and regulatory_basis.
V1_PAYLOAD = {
    "application_id": TEST_APPLICATION_ID,
    "session_id": "session-v1",
    "decision": {
        "risk_tier": "MEDIUM",
        "recommended_limit_usd": 75000,
        "rationale": "Legacy analysis."
    },
    "analysis_duration_ms": 150,
    "input_data_hash": "hash_v1",
    # Crucially, it has an explicit event_version of 1
    "event_version": 1
}

async def main():
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url: raise ValueError("DATABASE_URL not set")
    
    event_store = EventStore(db_url)
    await event_store.connect()

    print("="*60)
    print("🚀 Running Upcasting Verification Test")
    print("="*60)

    try:
        # --- 1. Manually insert a V1 event ---
        print("\n[1/4] Injecting a V1 'CreditAnalysisCompleted' event into the database...")
        async with event_store._pool.acquire() as conn:
            # We bypass the EventStore's `append` to manually set the version
            await conn.execute(
                """
                INSERT INTO events (stream_id, stream_position, event_type, event_version, payload, recorded_at)
                VALUES ($1, 1, 'CreditAnalysisCompleted', 1, $2, NOW())
                """,
                TEST_STREAM_ID,
                json.dumps(V1_PAYLOAD) # Store it as a JSON string
            )
            await conn.execute(
                "INSERT INTO event_streams (stream_id, aggregate_type, current_version) VALUES ($1, 'credit', 1)",
                TEST_STREAM_ID
            )
        print("✅ V1 event inserted successfully.")

        # --- 2. Load the stream via the EventStore ---
        print("\n[2/4] Loading stream through EventStore to trigger upcasting...")
        loaded_events = await event_store.load_stream(TEST_STREAM_ID)
        
        # --- 3. Verify the upcasting logic ---
        print("\n[3/4] Verifying the loaded event in Python code...")
        assert len(loaded_events) == 1, "Should have loaded exactly one event"
        
        upcasted_event = loaded_events[0]
        
        # Check that the version in the object is now 2
        assert upcasted_event.event_version == 2, f"Event version should be 2, but got {upcasted_event.event_version}"
        print("  - ✅ Event version correctly upcasted to 2.")
        
        # Check that the new fields were added by the upcaster
        assert upcasted_event.payload['model_version'] == "legacy-rules-engine-2025", "model_version is incorrect"
        print("  - ✅ `model_version` field was correctly added.")
        assert upcasted_event.payload['confidence_score'] is None, "confidence_score should be None"
        print("  - ✅ `confidence_score` field was correctly added as None.")
        assert upcasted_event.payload['regulatory_basis'] == [], "regulatory_basis should be an empty list"
        print("  - ✅ `regulatory_basis` field was correctly added.")
        
        print("✅ Upcasting verification successful!")


        # --- 4. Verify Immutability ---
        print("\n[4/4] Verifying the raw stored event in the DB was NOT changed...")
        async with event_store._pool.acquire() as conn:
            raw_row = await conn.fetchrow(
                "SELECT event_version, payload FROM events WHERE stream_id = $1",
                TEST_STREAM_ID
            )
            
            assert raw_row['event_version'] == 1, "Raw event version in DB should still be 1!"
            print("  - ✅ Raw `event_version` in DB is still 1.")

            # --- THIS IS THE FIX ---
            # Parse the JSON string from the database into a Python dictionary
            raw_payload_dict = json.loads(raw_row['payload'])
            
            # Now, check that the new key is NOT in the original, raw payload
            assert 'model_version' not in raw_payload_dict, "Raw payload in DB should NOT have the new fields!"
            print("  - ✅ Raw `payload` in DB does not contain the upcasted fields.")

    finally:
        await event_store.close()

    print("\n🎉 PHASE 4A (UPCASTING) COMPLETE AND VERIFIED! 🎉")


if __name__ == "__main__":
    from scripts.init_db import main as init_db
    print("Initializing clean database...")
    asyncio.run(init_db())
    
    asyncio.run(main())
