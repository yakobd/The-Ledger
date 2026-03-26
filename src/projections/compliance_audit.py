# src/projections/compliance_audit_projector.py

import json
from typing import Type
import asyncpg
from datetime import datetime, timezone

from .base import BaseProjector
from src.models.events import BaseEvent, ComplianceCheckCompleted

class ComplianceAuditProjector(BaseProjector):
    @property
    def event_types(self) -> list[Type[BaseEvent]]:
        return [ComplianceCheckCompleted]

    async def handle(self, event: BaseEvent) -> None:
        if isinstance(event, ComplianceCheckCompleted):
            # This is the typed Pydantic model
            app_id = event.application_id
            print(f"DEBUG: ComplianceProjector handling event for app: {app_id}")
            await self._on_compliance_check_completed(event)
        
    async def _on_compliance_check_completed(self, event: ComplianceCheckCompleted):
        app_id = event.application_id
        if not app_id:
            print("  -> ERROR: Event has no application_id. Skipping.")
            return

        try:
            # 1. Get the current latest version for this application
            latest_version_record = await self.conn.fetchrow(
                "SELECT MAX(version) as max_version FROM compliance_audit_view WHERE application_id = $1",
                app_id
            )
            
            # --- THIS IS THE FIX ---
            # Safely get max_version. If the record is None, max_version is None.
            max_version = latest_version_record['max_version'] if latest_version_record else 0
            new_version = (max_version or 0) + 1
            # --- END OF FIX ---
            
            print(f"  -> Determined new version for {app_id}: {new_version}")

            failed_rules_details = []
            if event.rules_failed > 0:
                failed_rules_details.append({
                    "reason": "One or more rules failed.",
                    "is_hard_block": event.has_hard_block
                })

            updated_at_ts = event.completed_at or datetime.now(timezone.utc)

            # 3. Insert the new versioned snapshot.
            result = await self.conn.execute(
                """
                INSERT INTO compliance_audit_view (
                    application_id, version, overall_verdict, has_hard_block,
                    rules_passed, rules_failed, failed_rules_details, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (application_id, version) DO NOTHING
                """,
                app_id, new_version, event.overall_verdict, event.has_hard_block,
                event.rules_passed, event.rules_failed, json.dumps(failed_rules_details),
                updated_at_ts
            )
            print(f"  -> DB Write Result for {app_id}: {result}. Row(s) should be affected.")
        
        except Exception as e:
            print(f"  -> CRITICAL ERROR in ComplianceProjector for {app_id}: {e}")

async def get_compliance_at(
    conn: asyncpg.Connection, 
    application_id: str, 
    timestamp: datetime
) -> dict | None:
    """
    Performs a temporal query to get the state of the compliance record
    as it existed at a specific point in time.
    """
    print(f"--- Performing temporal query for {application_id} at {timestamp.isoformat()} ---")
    
    # This query finds the latest version of the record *before* the given timestamp
    row = await conn.fetchrow(
        """
        SELECT * FROM compliance_audit_view
        WHERE application_id = $1 AND updated_at <= $2
        ORDER BY version DESC
        LIMIT 1
        """,
        application_id,
        timestamp
    )
    
    return dict(row) if row else None