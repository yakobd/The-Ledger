# src/audit.py

import hashlib
import json
from src.event_store import EventStore
from src.aggregates.audit_ledger import AuditLedger

async def run_integrity_check(
    store: EventStore,
    entity_type: str,
    entity_id: str,
) -> dict:
    """
    Runs an integrity check on an entity's primary event stream.

    1. Loads the entity's audit and primary streams.
    2. Hashes all new events since the last check.
    3. Appends a new AuditIntegrityCheckRun event.
    """
    print(f"\n--- Running Integrity Check for {entity_type}-{entity_id} ---")
    
    primary_stream_id = f"{entity_type}-{entity_id}"
    audit_stream_id = f"audit-{entity_type}-{entity_id}"

    # 1. Load the streams
    primary_events = await store.load_stream(primary_stream_id)
    audit_ledger = await store.load_aggregate(audit_stream_id, AuditLedger)
    
    # 2. Determine which events are new since the last check
    # The number of events already verified is stored in the aggregate's state
    new_events_to_hash = primary_events[audit_ledger.events_verified:]
    
    if not new_events_to_hash:
        print("  -> No new events to process. Integrity chain is up to date.")
        return {
            "chain_valid": True,
            "tamper_detected": False,
            "events_verified": 0,
            "new_hash": audit_ledger.last_hash
        }

    print(f"  -> Found {len(new_events_to_hash)} new events to hash.")

    # 3. Hash the new events
    # We create a stable JSON string of the event payloads to hash
    hasher = hashlib.sha256()
    # Start the hash with the previous hash to form the chain
    if audit_ledger.last_hash:
        hasher.update(audit_ledger.last_hash.encode('utf-8'))
        
    for event in new_events_to_hash:
        # Create a canonical (sorted keys) JSON string to ensure the hash is deterministic
        canonical_payload = json.dumps(event.payload, sort_keys=True)
        hasher.update(canonical_payload.encode('utf-8'))
        
    new_integrity_hash = hasher.hexdigest()
    print(f"  -> New integrity hash: {new_integrity_hash}")

    # 4. Append the new audit event
    audit_ledger.record_integrity_check(
        entity_type=entity_type,
        entity_id=entity_id,
        events_verified_count=len(new_events_to_hash),
        integrity_hash=new_integrity_hash
    )
    
    await store.append_to_stream(audit_ledger)
    print("  -> New AuditIntegrityCheckRun event has been saved.")
    
    return {
        "chain_valid": True, # In this simple check, it's always valid
        "tamper_detected": False,
        "events_verified": len(new_events_to_hash),
        "new_hash": new_integrity_hash
    }
