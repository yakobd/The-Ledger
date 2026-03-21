import asyncio
from src.event_store import EventStore, OptimisticConcurrencyError

async def concurrent_append_task(task_id: int, store: EventStore, stream_id: str, expected_version: int):
    try:
        event = {
            "event_type": "CreditAnalysisCompleted",
            "event_version": 1,
            "payload": {
                "application_id": stream_id.replace("loan-", ""),
                "agent_id": "credit-analysis",
                "session_id": "demo-session",
                "model_version": "claude-3.5",
                "confidence_score": 0.85,
                "risk_tier": "MEDIUM",
                "recommended_limit_usd": 50000
            },
            "metadata": {"task_id": task_id, "demo": True}
        }
        positions = await store.append(
            stream_id=stream_id,
            events=[event],
            expected_version=expected_version
        )
        print(f"✅ Task {task_id} SUCCEEDED → new position: {positions[0]}")
        return True
    except OptimisticConcurrencyError:
        print(f"❌ Task {task_id} FAILED with OptimisticConcurrencyError (as expected)")
        return False
    except Exception as e:
        print(f"❌ Task {task_id} unexpected error: {e}")
        return False

async def run_double_decision_test():
    store = EventStore("postgresql://postgres:apex@localhost/apex_ledger")
    await store.connect()
    
    stream_id = "loan-TEST-APP-003"
    current_version = await store.stream_version(stream_id)
    print(f"Starting double-decision test on {stream_id} at version {current_version}")
    
    task1 = asyncio.create_task(concurrent_append_task(1, store, stream_id, current_version))
    task2 = asyncio.create_task(concurrent_append_task(2, store, stream_id, current_version))
    
    results = await asyncio.gather(task1, task2, return_exceptions=True)
    
    success_count = sum(1 for r in results if r is True)
    print(f"\n🎯 FINAL RESULT: {success_count}/2 tasks succeeded")
    print("   Exactly ONE should succeed → the other must raise OptimisticConcurrencyError")
    
    await store.close()

if __name__ == "__main__":
    asyncio.run(run_double_decision_test())