# tests/test_projections.py

import pytest
import asyncio
import time
import uuid

from src.event_store import EventStore
from src.projections.daemon import ProjectionDaemon

# Import the datagen functions to create realistic events
from datagen.generate_all import generate_companies, SEED_SCENARIOS
from datagen.event_simulator import EventSimulator

pytestmark = pytest.mark.asyncio

# This test uses the shared event_store fixture from conftest.py

async def test_projection_rebuild_and_lag_slo(event_store: EventStore):
    """
    Tests two things:
    1. That the daemon can rebuild a projection from scratch.
    2. That the daemon meets its Service Level Objective (SLO) for lag under load.
    """
    print("🚀 Running Projection Rebuild and Lag Test")
    
    # --- 1. Initial Data Setup ---
    # We will manually generate and write events to avoid asyncio.run() conflicts
    print("\n[1/5] Generating initial data...")
    companies = generate_companies(20) # A smaller set is fine for this test
    all_events = []
    app_num = 1
    # We only need a few initial applications
    for target_state, count in [("APPROVED", 2), ("DECLINED", 1)]:
        for _ in range(count):
            company = companies[app_num % len(companies)]
            app_id = f"APEX-PROJ-TEST-{app_num:02d}"
            sim = EventSimulator(company=company, application_id=app_id, requested_amount=5000, loan_purpose="working_capital")
            events = sim.run(target_state)
            all_events.extend(events)
            app_num += 1

    # Manually append the events to the store
    for stream_id, event_dict, _ in all_events:
        # We need to know the current version of the stream to append
        try:
            version_record = await event_store._pool.fetchrow("SELECT current_version FROM event_streams WHERE stream_id = $1", stream_id)
            current_version = version_record['current_version'] if version_record else 0
        except Exception:
            current_version = 0 # If stream doesn't exist
            
        await event_store.append(stream_id, [event_dict], expected_version=current_version)
    print(f"✅ {len(all_events)} initial events generated.")

    # --- 2. First Run & Rebuild Test ---
    print("\n[2/5] Running daemon to build initial projections...")
    daemon = ProjectionDaemon(event_store)
    await daemon.register_projectors()
    async with event_store._pool.acquire() as conn:
        await daemon._process_batch(conn)
    
    async with event_store._pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM loan_summaries")
        assert count > 0, "FAIL: Initial run should have populated loan_summaries"
    print("✅ Projections built successfully.")

    print("\n[3/5] Testing 'rebuild_from_scratch'...")
    async with event_store._pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE loan_summaries")
        await conn.execute("UPDATE projection_checkpoints SET last_position = 0")
    print("  - `loan_summaries` table truncated and checkpoint reset.")
    
    async with event_store._pool.acquire() as conn:
        await daemon._process_batch(conn)
        
    async with event_store._pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM loan_summaries")
        assert count > 0, "FAIL: Daemon did not rebuild the truncated projection"
    print("✅ 'rebuild_from_scratch' test passed!")

    # --- 4. Load Test & Lag SLO ---
    print("\n[4/5] Simulating high concurrent load (50 commands)...")
    
    async def run_command(app_id: int):
        await event_store.append(
            stream_id=f"loan-lag-test-{app_id}",
            events=[{"event_type": "ApplicationSubmitted", "payload": {"contact_name": "Lag Test"}, "event_version": 1}],
            expected_version=0
        )

    start_time = time.monotonic()
    tasks = [run_command(i) for i in range(50)]
    await asyncio.gather(*tasks)
    load_duration = time.monotonic() - start_time
    print(f"  - Appended 50 new events in {load_duration:.2f} seconds.")

    # --- 5. Measure Projection Lag ---
    print("\n[5/5] Running daemon again and measuring lag...")
    async with event_store._pool.acquire() as conn:
        highest_pos = await conn.fetchval("SELECT MAX(global_position) FROM events")

    start_catchup_time = time.monotonic()
    async with event_store._pool.acquire() as conn:
        await daemon._process_batch(conn)
    end_catchup_time = time.monotonic()
    
    lag_duration_ms = (end_catchup_time - start_catchup_time) * 1000
    
    async with event_store._pool.acquire() as conn:
        final_checkpoint = await daemon._get_last_checkpoint(conn)
        
    print(f"  - Daemon caught up to position {final_checkpoint} in {lag_duration_ms:.0f} ms.")
    
    assert final_checkpoint >= highest_pos, "FAIL: Daemon did not process all new events"
    assert lag_duration_ms < 500, f"FAIL: Lag SLO not met! Lag was {lag_duration_ms:.0f} ms (SLO < 500 ms)"
    
    print(f"✅ Projection Lag SLO passed! ({lag_duration_ms:.0f} ms < 500 ms)")
    print("\n🎉 PROJECTION TESTS PASSED! 🎉")
