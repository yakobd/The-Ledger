# tests/test_projections.py

import pytest
import asyncio
import time
from src.event_store import EventStore
from src.projections.daemon import ProjectionDaemon

pytestmark = pytest.mark.asyncio

async def test_projection_rebuild_and_lag(event_store: EventStore):
    """
    Tests that the daemon can rebuild a projection and that it runs efficiently.
    """
    print("🚀 Running Projection Rebuild and Lag Test")
    
    # --- 1. Initial Data Setup ---
    # Manually create a small number of events to test with
    print("\n[1/4] Generating initial data...")
    await event_store.append(stream_id="loan-proj-test-1", events=[{"event_type": "ApplicationSubmitted", "payload": {"contact_name": "Test 1"}, "event_version": 1}], expected_version=0)
    await event_store.append(stream_id="loan-proj-test-2", events=[{"event_type": "ApplicationSubmitted", "payload": {"contact_name": "Test 2"}, "event_version": 1}], expected_version=0)
    await event_store.append(stream_id="loan-proj-test-2", events=[{"event_type": "ApplicationApproved", "payload": {"conditions": []}, "event_version": 1}], expected_version=1)
    print("✅ Initial data generated.")

    # --- 2. First Run & Rebuild Test ---
    print("\n[2/4] Running daemon to build initial projections...")
    daemon = ProjectionDaemon(event_store)
    await daemon.register_projectors()
    async with event_store._pool.acquire() as conn:
        await daemon._process_batch(conn)
    
    # Verify that the loan_summaries table was populated
    async with event_store._pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM loan_summaries")
        assert count == 2, "FAIL: Initial projection run should have created 2 summaries"
    print("✅ Projections built successfully.")

    print("\n[3/4] Testing 'rebuild_from_scratch'...")
    async with event_store._pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE loan_summaries")
        await conn.execute("UPDATE projection_checkpoints SET last_position = 0")
    print("  - `loan_summaries` table truncated and checkpoint reset.")
    
    # Re-run the processing batch
    async with event_store._pool.acquire() as conn:
        await daemon._process_batch(conn)
        
    async with event_store._pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM loan_summaries")
        assert count == 2, "FAIL: Daemon did not rebuild the truncated projection"
    print("✅ 'rebuild_from_scratch' test passed!")

    # --- 4. Simple Lag Check ---
    print("\n[4/4] Performing simple lag check...")
    start_time = time.monotonic()
    async with event_store._pool.acquire() as conn:
        await daemon._process_batch(conn)
    lag_duration_ms = (time.monotonic() - start_time) * 1000
    
    print(f"  - Daemon caught up in {lag_duration_ms:.0f} ms.")
    assert lag_duration_ms < 500, f"FAIL: Lag SLO not met! Lag was {lag_duration_ms:.0f} ms"
    print("✅ Projection Lag check passed!")
    print("\n🎉 PROJECTION TESTS PASSED! 🎉")
