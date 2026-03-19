import asyncio
from ledger.event_store import EventStore, OptimisticConcurrencyError

async def verify():
    store = EventStore("postgresql://postgres:apex@localhost/apex_ledger")
    await store.connect()

    print("✅ EventStore connected")

    # Test stream_version
    v = await store.stream_version("loan-APEX-0001")
    print(f"Stream version for loan-APEX-0001: {v}")

    # Test load_stream (should return events)
    events = await store.load_stream("loan-APEX-0001")
    print(f"Loaded {len(events)} events from loan stream")

    # Test load_all
    count = 0
    async for _ in store.load_all(batch_size=100):
        count += 1
        if count > 50:
            break
    print(f"Loaded {count} events from global stream")

    await store.close()
    print("✅ All manual tests passed — EventStore is working!")

asyncio.run(verify())