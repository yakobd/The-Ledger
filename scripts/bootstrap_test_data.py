import asyncio
from ledger.event_store import EventStore

async def bootstrap():
    store = EventStore('postgresql://postgres:apex@localhost/apex_ledger')
    await store.connect()

    app_id = "TEST-APP-003"          # new ID to avoid OCC collision
    agent_id = "credit-analysis"
    session_id = "session-1"

    # 1. Loan Application in AWAITING_ANALYSIS state
    loan_events = [
        {
            "event_type": "ApplicationSubmitted",
            "event_version": 1,
            "payload": {"applicant_id": "COMP-001", "requested_amount_usd": 75000}
        },
        {
            "event_type": "PackageReadyForAnalysis",
            "event_version": 1,
            "payload": {"application_id": app_id}
        }
    ]
    await store.append(stream_id=f"loan-{app_id}", events=loan_events, expected_version=-1)
    print(f"✅ Loan application {app_id} created in AWAITING_ANALYSIS state")

    # 2. Agent Session with context (Gas Town pattern)
    agent_events = [{
        "event_type": "AgentSessionStarted",
        "event_version": 1,
        "payload": {
            "agent_id": agent_id,
            "session_id": session_id,
            "model_version": "claude-3.5",
            "context_source": "seed-data"
        }
    }]
    await store.append(stream_id=f"agent-{agent_id}-{session_id}", events=agent_events, expected_version=-1)
    print(f"✅ AgentSession {session_id} created with context (Gas Town OK)")

    await store.close()

asyncio.run(bootstrap())