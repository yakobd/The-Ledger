# tests/test_concurrency.py

import pytest
import asyncio
import uuid
from src.event_store import EventStore, OptimisticConcurrencyError

pytestmark = pytest.mark.asyncio

async def test_double_decision_concurrency(event_store: EventStore):
    """
    The double-decision test as specified in the Phase 1 rubric.
    Two tasks attempt to append with expected_version=1. Exactly one must succeed.
    """
    stream_id = f"loan-double-decision-{uuid.uuid4()}"
    
    # Setup: Create a stream with one event, so its version is 1.
    await event_store.append(
        stream_id=stream_id,
        events=[{"event_type": "ApplicationSubmitted", "payload": {}, "event_version": 1}],
        expected_version=0
    )
    
    # Both tasks will read the stream at version 1.
    read_version = 1
    
    async def attempt_append(task_id: int):
        try:
            # Both tasks try to write, expecting the version to still be 1.
            await event_store.append(
                stream_id=stream_id,
                events=[{"event_type": "CreditAnalysisCompleted", "payload": {"task_id": task_id}, "event_version": 1}],
                expected_version=read_version
            )
            return "SUCCESS"
        except OptimisticConcurrencyError as e:
            # Assert that the error has the correct context
            assert e.expected_version == read_version
            assert e.actual_version > read_version
            return "OCC_FAILURE"

    # Run both tasks concurrently
    results = await asyncio.gather(attempt_append(1), attempt_append(2))
    
    # Assertions
    assert results.count("SUCCESS") == 1, "Exactly one task must succeed"
    assert results.count("OCC_FAILURE") == 1, "Exactly one task must fail with OCC"
    
    # Final check on the database state
    async with event_store._pool.acquire() as conn:
        # (a) Assert total events appended = 2 (not 3)
        final_count = await conn.fetchval("SELECT COUNT(*) FROM events WHERE stream_id = $1", stream_id)
        assert final_count == 2, "Stream should have exactly 2 events total"
        
        # (b) Assert the winning task's event has stream_position=2
        winning_event = await conn.fetchrow("SELECT stream_position FROM events WHERE stream_id = $1 AND stream_position = 2", stream_id)
        assert winning_event is not None, "The winning event should be at position 2"

