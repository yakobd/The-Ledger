# src/projections/loan_summary_projector.py

from typing import Type
import asyncpg

from src.projections.base import BaseProjector
from src.models.events import (
    BaseEvent,
    ApplicationSubmitted,
    ApplicationApproved,      # <-- CORRECT FINAL NAME
    ApplicationDeclined       # <-- CORRECT FINAL NAME
)

class LoanSummaryProjector(BaseProjector):
    """
    Creates and maintains the `loan_summaries` read model table.
    """
    
    @property
    def event_types(self) -> list[Type[BaseEvent]]:
        return [ApplicationSubmitted, ApplicationApproved, ApplicationDeclined]

    async def handle(self, event: BaseEvent) -> None:
        if isinstance(event, ApplicationSubmitted):
            await self._on_submitted(event)
        elif isinstance(event, ApplicationApproved):
            await self._on_approved(event)
        elif isinstance(event, ApplicationDeclined):
            await self._on_declined(event)
        else:
            return

    async def _on_submitted(self, event: ApplicationSubmitted):
        await self.conn.execute(
            """
            INSERT INTO loan_summaries (application_id, applicant_name, status, last_updated_at)
            VALUES ($1, $2, 'SUBMITTED', NOW())
            ON CONFLICT (application_id) DO UPDATE
            SET applicant_name = EXCLUDED.applicant_name, status = EXCLUDED.status, last_updated_at = NOW()
            """,
            event.application_id, event.contact_name, # Using contact_name as applicant_name
        )

    async def _on_approved(self, event: ApplicationApproved):
        await self.conn.execute(
            """
            UPDATE loan_summaries SET status = 'APPROVED', decision_reason = $1, last_updated_at = NOW()
            WHERE application_id = $2
            """,
            ", ".join(event.conditions) or "Approved", event.application_id,
        )

    async def _on_declined(self, event: ApplicationDeclined):
        await self.conn.execute(
            """
            UPDATE loan_summaries SET status = 'DECLINED', decision_reason = $1, last_updated_at = NOW()
            WHERE application_id = $2
            """,
            ", ".join(event.decline_reasons), event.application_id,
        )
