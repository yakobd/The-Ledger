# src/mcp/resources.py

from fastapi import Depends, HTTPException
import asyncpg

from src.mcp.server import app, get_event_store # Import app and dependency from our server file
from src.event_store import EventStore
from src.projections.daemon import ProjectionDaemon

# This file defines the "Query" side of the MCP API

@app.get("/resources/applications/{application_id}/summary", tags=["MCP Resources"])
async def resource_get_application_summary(
    application_id: str,
    # We use Depends to get a connection from the pool
    store: EventStore = Depends(get_event_store)
):
    """
    MCP Resource to retrieve the current state summary of a loan application.
    Reads from the `loan_summaries` projection.
    """
    # We acquire a raw connection from the store's pool to query the projection
    async with store._pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM loan_summaries WHERE application_id = $1",
            application_id
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Application summary for {application_id} not found.")
    return dict(row)

@app.get("/resources/agents/performance", tags=["MCP Resources"])
async def resource_get_agent_performance(
    store: EventStore = Depends(get_event_store)
):
    """
    MCP Resource to retrieve the performance ledger for all agents.
    Reads from the `agent_performance_ledger` projection.
    """
    async with store._pool.acquire() as conn:
        rows = await raw_conn.fetch("SELECT * FROM agent_performance_ledger ORDER BY agent_id")
    return [dict(row) for row in rows]

@app.get("/resources/ledger/health", tags=["MCP Resources"])
async def resource_get_ledger_health(store: EventStore = Depends(get_event_store)):
    """
    MCP Resource to check the health and status of the projection daemon,
    including the lag for each projection.
    """
    # In a real system, the daemon would be a long-running singleton.
    # For this test, we will create a temporary instance to access its methods.
    daemon = ProjectionDaemon(store)
    # We haven't implemented the live lag calculation yet, so we return placeholders.
    # The get_lag() method we added earlier would be used here.
    return {
        "status": "healthy",
        "projection_lags_ms": {
            "LoanSummaryProjector": daemon.get_lag("LoanSummaryProjector") or "not_calculated",
            "AgentPerformanceLedgerProjector": daemon.get_lag("AgentPerformanceLedgerProjector") or "not_calculated",
            "ComplianceAuditProjector": daemon.get_lag("ComplianceAuditProjector") or "not_calculated",
        }
    }