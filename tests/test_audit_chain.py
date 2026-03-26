# tests/test_audit_chain.py

import pytest
import asyncio
import uuid
import json

from src.event_store import EventStore
from src.integrity.audit_chain import run_integrity_check
from src.models.events import ApplicationSubmitted, ApplicationApproved

# Mark all tests in this file as asyncio and use the event_store fixture
pytestmark = pytest.mark.asyncio

async def test_audit_chain_linking(event_store: EventStore):
    """
    Tests that the cryptographic chain is correctly linked by verifying
    that the 'previous_hash' of a new audit event matches the hash of the last one.
    """
    print("🚀 Running Audit Chain Linking Test")
    TEST_APP_ID = "APEX-AUDIT-LINK"
    TEST_STREAM_ID = f"loan-{TEST_APP_ID}"
    
    # 1. Create initial state with all required fields
    event1 = ApplicationSubmitted(
        application_id=TEST_APP_ID, applicant_id="LINK-COMP", requested_amount_usd=1000, 
        loan_purpose="working_capital", loan_term_months=12, submission_channel="API",
        contact_email="link@test.com", contact_name="Link User", 
        submitted_at=__import__('datetime').datetime.now(), application_reference="ref-link"
    )
    await event_store.append(TEST_STREAM_ID, [event1.to_store_dict()], 0)
    
    # 2. Run first integrity check
    result1 = await run_integrity_check(event_store, "loan", TEST_APP_ID)
    first_hash = result1.get("new_hash")
    assert first_hash is not None
    print(f"✅ First check successful. Hash: {first_hash[:10]}...")

    # 3. Add more events with all required fields
    event2 = ApplicationApproved(
        application_id=TEST_APP_ID, approved_amount_usd=1000, interest_rate_pct=5.0, 
        term_months=12, approved_by="auto_test", conditions=[],
        effective_date="2026-03-25", approved_at=__import__('datetime').datetime.now()
    )
    await event_store.append(TEST_STREAM_ID, [event2.to_store_dict()], 1)

    # 4. Run second integrity check
    result2 = await run_integrity_check(event_store, "loan", TEST_APP_ID)
    second_hash = result2.get("new_hash")
    assert second_hash is not None and second_hash != first_hash
    print(f"✅ Second check successful. Hash: {second_hash[:10]}...")

    # 5. Verify the chain
    audit_events = await event_store.load_stream(f"audit-loan-{TEST_APP_ID}")
    assert len(audit_events) == 2
    second_audit_event = audit_events[1]
    assert second_audit_event.payload['previous_hash'] == first_hash, "Chain is broken!"
    print("✅ Chain verified!")
    print("\n🎉 AUDIT CHAIN LINKING TEST PASSED! 🎉")


async def test_tamper_detection(event_store: EventStore):
    """
    Tests that the audit chain can detect a direct modification
    of a past event in the database.
    """
    print("\n🚀 Running Tamper Detection Test")
    TEST_APP_ID = "APEX-TAMPER-TEST"
    TEST_STREAM_ID = f"loan-{TEST_APP_ID}"
    
    # 1. Create a known history and run a valid integrity check
# 1. Create a known history with all required fields
    event1 = ApplicationSubmitted(
        application_id=TEST_APP_ID, applicant_id="TAMPER", requested_amount_usd=5000, 
        loan_purpose="refinancing", loan_term_months=24, submission_channel="API",
        contact_email="tamper@test.com", contact_name="Tamper User",
        submitted_at=__import__('datetime').datetime.now(), application_reference="ref-tamper"
    )
    await event_store.append(TEST_STREAM_ID, [event1.to_store_dict()], 0)
    await run_integrity_check(event_store, "loan", TEST_APP_ID, write_new_check=True)
    print("  - ✅ Initial state and audit event created.")

    # 2. The "Attack": Manually tamper with the original event's payload
    print("  -> TAMPERING with database record...")
    async with event_store._pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE events
            SET payload = payload || '{"requested_amount_usd": 99999}'::jsonb
            WHERE stream_id = $1 AND stream_position = 1
            """,
            TEST_STREAM_ID
        )
    print("  -> Event payload secretly modified.")

    # 3. Run the verification again (without writing a new check)
    print("\n  -> Re-running verification on the tampered chain...")
    verification_result = await run_integrity_check(event_store, "loan", TEST_APP_ID, write_new_check=False)
    
    # 4. Assert that tampering was detected
    assert verification_result.get("tamper_detected") is True, "FAIL: Tampering was not detected!"
    print("✅ Tamper detection successful! The chain was correctly identified as invalid.")
    print("\n🎉 PHASE 4B (TAMPER TEST) PASSED! 🎉")

