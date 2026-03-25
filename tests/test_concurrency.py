import asyncio
import pytest
from uuid import uuid4
from src.event_store import EventStore, OptimisticConcurrencyError

@pytest.mark.asyncio
async def test_concurrent_double_append_exactly_one_succeeds():
    store = EventStore("postgresql://postgres:apex@localhost/apex_ledger")
    await store.connect()

    # Use a unique stream ID every test run → no version drift
    stream_id = f"loan-test-{uuid4()}"
    
    # Create the stream with initial event
    await store.append(
        stream_id=stream_id,
        events=[{
            "event_type": "ApplicationSubmitted",
            "event_version": 0,
            "payload": {"application_id": "test-app"}
        }],
        expected_version=-1
    )
    
    current_version = await store.stream_version(stream_id)
    
    async def task(task_id: int):
        try:
            event = {
                "event_type": "CreditAnalysisCompleted",
                "event_version": 1,
                "payload": {"application_id": "test-app"}
            }
            positions = await store.append(
                stream_id=stream_id,
                events=[event],
                expected_version=current_version,
                correlation_id=f"task-{task_id}",
                causation_id="test-run"
            )
            print(f"✅ Task {task_id} SUCCEEDED → position {positions[0]}")
            return True
        except OptimisticConcurrencyError:
            print(f"❌ Task {task_id} FAILED with OptimisticConcurrencyError (as expected)")
            return False
        except Exception as e:
            print(f"❌ Task {task_id} unexpected error: {e}")
            return False

    t1 = asyncio.create_task(task(1))
    t2 = asyncio.create_task(task(2))
    
    results = await asyncio.gather(t1, t2)
    
    success_count = sum(results)
    assert success_count == 1, f"Exactly ONE task must succeed (got {success_count})"
    assert not all(results), "The other task must raise OptimisticConcurrencyError"
    
    await store.close()