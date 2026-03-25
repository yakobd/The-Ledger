# src/regulatory/package.py

import json
from datetime import datetime
from src.event_store import EventStore
from src.integrity.audit_chain import run_integrity_check

async def generate_regulatory_package(
    store: EventStore,
    application_id: str,
    examination_date: datetime
) -> str:
    """
    Generates a complete, self-contained examination package for a regulator.
    """
    print(f"--- Generating Regulatory Package for {application_id} as of {examination_date.isoformat()} ---")
    
    # 1. Get complete event stream for the main loan application
    # In a real system, we'd get all related streams, but this is a good representation.
    loan_events = await store.load_stream(f"loan-{application_id}")
    
    # 2. Get the final summary state from the projection
    summary = {}
    async with store._pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM loan_summaries WHERE application_id = $1", application_id)
        if row: summary = dict(row)
        
    # 3. Run a final integrity check on the primary stream
    integrity_result = await run_integrity_check(store, 'loan', application_id)
    
    # 4. Generate a simple, human-readable narrative
    narrative = f"Application submitted. A total of {len(loan_events)} actions were recorded in the main loan lifecycle. The final integrity check of the chain was valid: {integrity_result['chain_valid']}."
    
    # 5. Assemble the final package
    package = {
        "packageName": "Regulatory Examination Package",
        "applicationId": application_id,
        "examinationDate": examination_date.isoformat(),
        "applicationSummary": summary,
        "finalIntegrityCheck": integrity_result,
        "narrative": narrative,
        "fullEventStream": [e.model_dump(mode='json') for e in loan_events]
    }
    
    # Return the package as a formatted JSON string
    return json.dumps(package, indent=2, default=str) # Use default=str to handle any non-serializable types
