# scripts/test_audit_chain.py

import sys, os, asyncio, json
from dotenv import load_dotenv

# --- Path Setup ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.event_store import EventStore
from src.integrity.audit_chain import run_integrity_check
from src.models.events import ApplicationSubmitted, ApplicationApproved

# --- Test Config ---
TEST_APPLICATION_ID = "APEX-AUDIT-TEST"
TEST_ENTITY_TYPE = "loan"

async def main():
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url: raise ValueError("DATABASE_URL not set")
    
    event_store = EventStore(db_url)
    await event_store.connect()

    print("="*60)
    print("🚀 Running Cryptographic Audit Chain Test")
    print("="*60)

    try:
        # --- 1. Create Initial State ---
        print("\n[1/5] Creating initial loan application events...")
        stream_id = f"{TEST_ENTITY_TYPE}-{TEST_APPLICATION_ID}"
        
        event1 = ApplicationSubmitted(application_id=TEST_APPLICATION_ID, applicant_id="AUDIT-COMP", requested_amount_usd=1000, loan_purpose="working_capital", loan_term_months=12, submission_channel="API", contact_email="audit@test.com", contact_name="Audit User", submitted_at=__import__('datetime').datetime.now(), application_reference="ref-audit")
        event2 = ApplicationApproved(application_id=TEST_APPLICATION_ID, approved_amount_usd=1000, interest_rate_pct=5.0, term_months=12, approved_by="auto", effective_date="2026-03-25", approved_at=__import__('datetime').datetime.now())

        await event_store.append(
            stream_id=stream_id,
            events=[event1.to_store_dict(), event2.to_store_dict()],
            expected_version=0
        )
        print("✅ 2 initial events created.")

        # --- 2. Run First Integrity Check ---
        result1 = await run_integrity_check(event_store, TEST_ENTITY_TYPE, TEST_APPLICATION_ID)
        assert result1["events_verified"] == 2
        first_hash = result1["new_hash"]
        print(f"✅ First integrity check successful. Hash: {first_hash[:10]}...")

        # --- 3. Add More Events ---
        print("\n[3/5] Adding a new event to the stream...")
        event3 = {"event_type": "LoanTermsAccepted", "payload": {"accepted_at": "2026-03-26"}, "event_version": 1}
        await event_store.append(stream_id=stream_id, events=[event3], expected_version=2)
        print("✅ 1 new event added.")

        # --- 4. Run Second Integrity Check ---
        print("\n[4/5] Running second integrity check...")
        result2 = await run_integrity_check(event_store, TEST_ENTITY_TYPE, TEST_APPLICATION_ID)
        assert result2["events_verified"] == 1
        second_hash = result2["new_hash"]
        print(f"✅ Second integrity check successful. Hash: {second_hash[:10]}...")
        assert second_hash != first_hash, "Second hash should be different from the first!"

        # --- 5. Verify the Chain ---
        print("\n[5/5] Verifying the hash chain...")
        audit_stream_id = f"audit-{TEST_ENTITY_TYPE}-{TEST_APPLICATION_ID}"
        audit_events = await event_store.load_stream(audit_stream_id)
        
        assert len(audit_events) == 2, "Should be two audit events in the stream"
        
        second_audit_event = audit_events[1] # Get the second check event
        
        # This is the crucial assertion:
        assert second_audit_event.payload['previous_hash'] == first_hash, "The second audit event must reference the first hash!"
        print("✅ Chain verified! The 'previous_hash' of the second check matches the hash of the first check.")

    finally:
        await event_store.close()

    print("\n🎉 PHASE 4B (AUDIT CHAIN) COMPLETE AND VERIFIED! 🎉")


if __name__ == "__main__":
    from scripts.init_db import main as init_db
    print("Initializing clean database...")
    asyncio.run(init_db())
    
    asyncio.run(main())
