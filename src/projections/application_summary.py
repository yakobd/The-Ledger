# src/projections/loan_summary_projector.py

import asyncpg
from typing import Type
from .base import BaseProjector
from src.models.events import BaseEvent, ApplicationSubmitted, ApplicationApproved, ApplicationDeclined

class LoanSummaryProjector(BaseProjector):
    def __init__(self, conn: asyncpg.Connection | None):
        super().__init__(conn)
        self.summaries: dict[str, dict] = {}

    @property
    def event_types(self) -> list[Type[BaseEvent]]:
        return [ApplicationSubmitted, ApplicationApproved, ApplicationDeclined]

    async def handle(self, event: BaseEvent) -> None:
        if self.conn:
            if isinstance(event, ApplicationSubmitted): await self._on_submitted_db(event)
            elif isinstance(event, ApplicationApproved): await self._on_approved_db(event)
            elif isinstance(event, ApplicationDeclined): await self._on_declined_db(event)
        else:
            if isinstance(event, ApplicationSubmitted): self._on_submitted_mem(event)
            elif isinstance(event, ApplicationApproved): self._on_approved_mem(event)
            elif isinstance(event, ApplicationDeclined): self._on_declined_mem(event)

    # --- In-Memory State Handlers ---
    def _on_submitted_mem(self, event: ApplicationSubmitted):
        self.summaries[event.application_id] = {"status": "SUBMITTED", "applicant_name": event.contact_name}
    def _on_approved_mem(self, event: ApplicationApproved):
        if event.application_id in self.summaries: self.summaries[event.application_id]["status"] = "APPROVED"
    def _on_declined_mem(self, event: ApplicationDeclined):
        if event.application_id in self.summaries: self.summaries[event.application_id]["status"] = "DECLINED"
    
    # --- DB Write Handlers (NOW WITH CORRECT SQL) ---
    async def _on_submitted_db(self, event: ApplicationSubmitted):
        await self.conn.execute(
            """
            INSERT INTO loan_summaries (application_id, applicant_name, status, last_updated_at)
            VALUES ($1, $2, 'SUBMITTED', NOW())
            ON CONFLICT (application_id) DO UPDATE SET
                applicant_name = EXCLUDED.applicant_name,
                status = EXCLUDED.status,
                last_updated_at = NOW()
            """,
            event.application_id,
            event.contact_name
        )

    async def _on_approved_db(self, event: ApplicationApproved):
        await self.conn.execute(
            """
            UPDATE loan_summaries SET status = 'APPROVED', decision_reason = $1, last_updated_at = NOW()
            WHERE application_id = $2
            """,
            ", ".join(event.conditions) if event.conditions else "Approved",
            event.application_id
        )

    async def _on_declined_db(self, event: ApplicationDeclined):
        await self.conn.execute(
            """
            UPDATE loan_summaries SET status = 'DECLINED', decision_reason = $1, last_updated_at = NOW()
            WHERE application_id = $2
            """,
            ", ".join(event.decline_reasons),
            event.application_id
        )

    def get_summary(self, application_id: str) -> dict | None:
        return self.summaries.get(application_id)
