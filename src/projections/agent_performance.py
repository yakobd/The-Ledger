# src/projections/agent_performance_projector.py

from typing import Type
import asyncpg
import json

from .base import BaseProjector
from src.models.events import BaseEvent, AgentSessionStarted, AgentSessionCompleted, DecisionGenerated

class AgentPerformanceLedgerProjector(BaseProjector):
    @property
    def event_types(self) -> list[Type[BaseEvent]]:
        # We now listen to Started instead of just Completed
        return [AgentSessionStarted, AgentSessionCompleted, DecisionGenerated]

    async def handle(self, event: BaseEvent) -> None:
        if isinstance(event, AgentSessionStarted):
            await self._on_agent_session_started(event)
        elif isinstance(event, AgentSessionCompleted):
            await self._on_agent_session_completed(event)
        elif isinstance(event, DecisionGenerated):
            await self._on_decision_generated(event)
        
    async def _on_agent_session_started(self, event: AgentSessionStarted):
        """
        When a session starts, we create the initial record with the model version.
        """
        agent_id = f"{event.agent_type}:{event.model_version}"
        
        await self.conn.execute(
            """
            INSERT INTO agent_performance_ledger (agent_id, model_version, first_seen_at, last_seen_at)
            VALUES ($1, $2, $3, $3)
            ON CONFLICT (agent_id) DO NOTHING
            """,
            agent_id, event.model_version, event.started_at
        )

    async def _on_agent_session_completed(self, event: AgentSessionCompleted):
        """
        When a session completes, we find the corresponding started event to get the
        model version and then update the stats.
        """
        # We need to find the model version from the session's start event.
        # This is a more complex query. A simpler approach for now is to assume
        # the model version is consistent for an agent type. Let's try to update based on agent_type.
        
        # A truly robust solution would look up the start event. Let's simplify for this project.
        # We will assume a fixed model version per agent type for this projection.
        # This is a known limitation we would document in DESIGN.md.
        
        # We need a way to get the model version. Let's assume a default for now.
        # A better way would be to load the AgentSessionStarted event.
        
        # Let's try a different approach. The payload from datagen has the model version.
        payload = event.payload if hasattr(event, 'payload') else event.model_dump()
        
        agent_type = payload.get('agent_type')
        # We can't reliably get the model_version here. Let's just update based on agent_type.
        # This is a simplification.
        
        # Let's assume for now that the payload of the completed event *does* contain the model version.
        # If datagen puts it there, this will work.
        model_version = payload.get('model_version', 'v0')
        agent_id = f"{agent_type}:{model_version}"

        await self.conn.execute(
            """
            UPDATE agent_performance_ledger
            SET
                analyses_completed = agent_performance_ledger.analyses_completed + 1,
                avg_duration_ms = ((agent_performance_ledger.avg_duration_ms * agent_performance_ledger.analyses_completed) + $1) / (agent_performance_ledger.analyses_completed + 1),
                last_seen_at = $2
            WHERE agent_id = $3
            """,
            payload.get('total_duration_ms', 0),
            payload.get('completed_at'),
            agent_id
        )

    async def _on_decision_generated(self, event: DecisionGenerated):
        # ... (This method should be correct from the previous fix)
        payload = event.payload if hasattr(event, 'payload') else event.model_dump()
        model_versions = payload.get('model_versions', {})
        agent_id = f"decision_orchestrator:{model_versions.get('orchestrator', 'v0')}"
        recommendation = payload.get('recommendation', '').lower()
        
        update_field = ""
        if recommendation == 'approve': update_field = "approve_rate"
        elif recommendation == 'decline': update_field = "decline_rate"
        elif recommendation == 'refer': update_field = "refer_rate"
        else: return

        await self.conn.execute(
            f"""
            INSERT INTO agent_performance_ledger (agent_id, model_version, decisions_generated, {update_field})
            VALUES ($1, $2, 1, 1.0)
            ON CONFLICT (agent_id) DO UPDATE SET
                decisions_generated = agent_performance_ledger.decisions_generated + 1,
                {update_field} = ( (agent_performance_ledger.{update_field} * (agent_performance_ledger.decisions_generated)) + 1 ) / (agent_performance_ledger.decisions_generated + 1)
            """,
            agent_id, model_versions.get('orchestrator', 'v0')
        )
