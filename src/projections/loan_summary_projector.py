# src/projections/loan_summary_projector.py

import asyncpg
from typing import Type

from .base import BaseProjector
from src.models.events import BaseEvent, ApplicationSubmitted, ApplicationApproved, ApplicationDeclined

class LoanSummaryProjector(BaseProjector):
    def __init__(self, conn: asyncpg.Connection | None):
        super().__init__(conn)
        # --- THIS IS THE CHANGE ---
        # The projector now holds its state in a dictionary
        self.summaries: dict[str, dict] = {}

    @property
    def event_types(self) -> list[Type[BaseEvent]]:
        return [ApplicationSubmitted, ApplicationApproved, ApplicationDeclined]

    async def handle(self, event: BaseEvent) -> None:
        # The handle method now calls the correct in-memory or DB method
        if self.conn: # If we have a DB connection, write to it
            if isinstance(event, ApplicationSubmitted): await self._on_submitted_db(event)
            elif isinstance(event, ApplicationApproved): await self._on_approved_db(event)
            elif isinstance(event, ApplicationDeclined): await self._on_declined_db(event)
        else: # If no DB connection, update in-memory state
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
    
    # --- DB Write Handlers (Unchanged, but renamed) ---
    async def _on_submitted_db(self, event: ApplicationSubmitted):
        await self.conn.execute( "INSERT INTO loan_summaries ...", event.application_id, event.contact_name)
    async def _on_approved_db(self, event: ApplicationApproved):
        await self.conn.execute("UPDATE loan_summaries SET status = 'APPROVED' ...", event.application_id)
    async def _on_declined_db(self, event: ApplicationDeclined):
        await self.conn.execute("UPDATE loan_summaries SET status = 'DECLINED' ...", event.application_id)

    # --- New method for What-If scenario ---
    def get_summary(self, application_id: str) -> dict | None:
        return self.summaries.get(application_id)

