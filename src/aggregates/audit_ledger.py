# src/aggregates/audit_ledger.py

from .base import BaseAggregate
from src.models.events import AuditIntegrityCheckRun, BaseEvent

class AuditLedger(BaseAggregate):
    def __init__(self):
        super().__init__()
        self.last_hash: str | None = None
        self.events_verified: int = 0

    def _apply_AuditIntegrityCheckRun(self, event: BaseEvent):
        # When we replay history, we update our state with the last known hash
        if hasattr(event, 'payload'):
            self.last_hash = event.payload.get("integrity_hash")
            self.events_verified += event.payload.get("events_verified_count", 0)
        else:
            self.last_hash = event.integrity_hash
            self.events_verified += event.events_verified_count

    def record_integrity_check(self, entity_type: str, entity_id: str, events_verified_count: int, integrity_hash: str):
        """Records a new integrity check event."""
        self.record(
            AuditIntegrityCheckRun(
                entity_type=entity_type,
                entity_id=entity_id,
                check_timestamp=self._now(),
                events_verified_count=events_verified_count,
                integrity_hash=integrity_hash,
                previous_hash=self.last_hash,                
                chain_valid=True,# We assume the chain is valid when we record the check
                tamper_detected=False
 # Link the chain
            )
        )
        return self
