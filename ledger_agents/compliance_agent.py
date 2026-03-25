# ledger_agents/compliance_agent.py

from typing import TypedDict
from langgraph.graph import StateGraph, END
import asyncio
from datetime import datetime, timezone

from src.event_store import EventStore
from src.aggregates.compliance_record import ComplianceRecord

class ComplianceAgentState(TypedDict):
    application_id: str
    applicant_jurisdiction: str # e.g., "CA", "NY", "MT"
    # The agent's results
    passed_rules: list[str]
    failed_rules: list[dict]
    is_blocked: bool

class ComplianceAgent:
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
        self.workflow = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(ComplianceAgentState)
        workflow.add_node("start_check", self._node_start_check)
        workflow.add_node("check_jurisdiction_rule", self._node_check_jurisdiction_rule)
        workflow.add_node("finish_check", self._node_finish_check)

        workflow.set_entry_point("start_check")
        workflow.add_edge("start_check", "check_jurisdiction_rule")
        workflow.add_edge("check_jurisdiction_rule", "finish_check")
        workflow.add_edge("finish_check", END)
        
        return workflow.compile()

    # --- Agent Nodes ---

    def _node_start_check(self, state: ComplianceAgentState):
        print(f"AGENT: Starting compliance check for application {state['application_id']}")
        return {"passed_rules": [], "failed_rules": [], "is_blocked": False}

    def _node_check_jurisdiction_rule(self, state: ComplianceAgentState):
        """Rule: Check if the applicant's jurisdiction is on the blocked list."""
        print(f"  -> Checking jurisdiction rule for: {state['applicant_jurisdiction']}")
        
        # This is a hardcoded business rule from the support document.
        BLOCKED_JURISDICTIONS = {"MT"} # Montana
        
        rule_id = "JURIS_001"
        rule_name = "Blocked Jurisdiction Check"
        
        if state["applicant_jurisdiction"] in BLOCKED_JURISDICTIONS:
            print(f"    [FLAG] Applicant is from a blocked jurisdiction: {state['applicant_jurisdiction']}")
            failure = {
                "rule_id": rule_id,
                "rule_name": rule_name,
                "reason": f"Applicant jurisdiction '{state['applicant_jurisdiction']}' is on the block-list.",
                "is_hard_block": True
            }
            return {"failed_rules": [failure], "is_blocked": True}
        else:
            print("    [OK] Jurisdiction is allowed.")
            return {"passed_rules": [rule_id]}

    async def _node_finish_check(self, state: ComplianceAgentState):
        """Save the results to the event store."""
        app_id = state["application_id"]
        print(f"AGENT: Finishing compliance check for {app_id}")
        
        stream_id = f"compliance-{app_id}"
        session_id = "dummy_session_id"
        
        try:
            compliance_record = ComplianceRecord()
            compliance_record.stream_id = stream_id

            compliance_record.initiate_check(session_id=session_id, regulations=["JURIS_001"])

            for rule_id in state["passed_rules"]:
                compliance_record.record_rule_pass(session_id=session_id, rule_id=rule_id, rule_name="Blocked Jurisdiction Check")
            
            for failure in state["failed_rules"]:
                compliance_record.record_rule_fail(
                    session_id=session_id,
                    rule_id=failure["rule_id"],
                    rule_name=failure["rule_name"],
                    reason=failure["reason"],
                    is_hard_block=failure["is_hard_block"]
                )
            
            compliance_record.complete_check(session_id=session_id)

            if compliance_record.has_new_events():
                await self.event_store.append_to_stream(compliance_record)
                print(f"  -> {len(compliance_record.new_events)} compliance events recorded to stream '{stream_id}'")

        except Exception as e:
            print(f"  -> CRITICAL ERROR: Could not save compliance results for {app_id}: {e}")
        
        return {}
