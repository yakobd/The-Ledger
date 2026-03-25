# ledger_agents/fraud_detection_agent.py

from typing import TypedDict, Annotated
import operator
import asyncio
import uuid
from datetime import datetime, timezone
from langgraph.graph import StateGraph, END
from decimal import Decimal

from src.event_store import EventStore
from src.aggregates.fraud_screening import FraudScreening
from src.aggregates.agent_session import AgentSessionAggregate
from src.commands.models import RecordFraudScreening, StartAgentSession
from src.commands.handlers import handle_record_fraud_screening, handle_start_agent_session

class FraudDetectionAgentState(TypedDict):
    application_id: str
    financial_facts: dict # The extracted facts from the previous agent
    # The agent's findings will be added here
    anomalies: Annotated[list[dict], operator.add] 
    final_score: float

class FraudDetectionAgent:
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
        self.workflow = self._build_graph()
        self.session_id = str(uuid.uuid4())

    def _build_graph(self):
        workflow = StateGraph(FraudDetectionAgentState)
        workflow.add_node("start_screening", self._node_start_screening)
        workflow.add_node("check_profitability_ratios", self._node_check_profitability_ratios)
        workflow.add_node("check_balance_sheet_ratios", self._node_check_balance_sheet_ratios)
        workflow.add_node("calculate_final_score", self._node_calculate_final_score)
        workflow.add_node("finish_screening", self._node_finish_screening)

        workflow.set_entry_point("start_screening")
        workflow.add_edge("start_screening", "check_profitability_ratios")
        workflow.add_edge("check_profitability_ratios", "check_balance_sheet_ratios")
        workflow.add_edge("check_balance_sheet_ratios", "calculate_final_score")
        workflow.add_edge("calculate_final_score", "finish_screening")
        workflow.add_edge("finish_screening", END)
        
        return workflow.compile()

    # --- Agent Nodes ---

    async def _node_start_screening(self, state: FraudDetectionAgentState):
        """
        This node now uses the Command Handler pattern to start its session.
        """
        app_id = state['application_id']
        print(f"AGENT: Starting fraud screening for application {app_id}")
        print(f"  -> Session ID: {self.session_id}")

        # 1. Create the Command object
        command = StartAgentSession(
            session_id=self.session_id,
            agent_type="fraud_detection",
            application_id=app_id,
            model_version="rule_based_v1"
        )

        # 2. Dispatch the command to the handler
        try:
            await handle_start_agent_session(command, self.event_store)
            print("  -> Gas Town: AgentSessionStarted event handled successfully.")
        except Exception as e:
            print(f"  -> ERROR could not start agent session: {e}")
            
        return {"anomalies": []}


    def _node_check_profitability_ratios(self, state: FraudDetectionAgentState):
        """Rule: Check if net margin is unusually high."""
        print("  -> Checking profitability ratios...")
        anomalies = []
        facts = state["financial_facts"]
        
        total_revenue = Decimal(facts.get("total_revenue", 0))
        net_income = Decimal(facts.get("net_income", 0))

        if total_revenue > 0:
            net_margin = net_income / total_revenue
            # A net margin over 40% is very unusual for most businesses and warrants a flag.
            if net_margin > Decimal("0.40"):
                anomaly = {
                    "anomaly_type": "revenue_discrepancy",
                    "description": f"Unusually high net margin of {net_margin:.2%}. Potential revenue inflation.",
                    "severity": "HIGH",
                    "score_impact": 0.5 # This will contribute to the final score
                }
                print(f"    [FLAG] {anomaly['description']}")
                anomalies.append(anomaly)

        return {"anomalies": anomalies}

    def _node_check_balance_sheet_ratios(self, state: FraudDetectionAgentState):
        """Rule: Check for the fundamental accounting equation: Assets = Liabilities + Equity."""
        print("  -> Checking balance sheet sanity (A == L + E)...")
        anomalies = []
        facts = state["financial_facts"]
        
        # Use .get() with a default of 0 to avoid errors if a field is missing
        total_assets = Decimal(facts.get("total_assets", 0))
        total_liabilities = Decimal(facts.get("total_liabilities", 0))
        total_equity = Decimal(facts.get("total_equity", 0))

        # Avoid flagging for all-zero balance sheets which might just be missing data
        if total_assets > 0 or total_liabilities > 0 or total_equity > 0:
            # Check if the equation balances, allowing for a small tolerance (e.g., $1)
            discrepancy = abs(total_assets - (total_liabilities + total_equity))
            
            if discrepancy > Decimal("1.00"):
                anomaly = {
                    "anomaly_type": "balance_sheet_inconsistency",
                    "description": f"Balance sheet does not balance. Assets != L+E by ${discrepancy:,.2f}",
                    "severity": "CRITICAL",
                    "score_impact": 0.8 
                }
                print(f"    [FLAG] {anomaly['description']}")
                anomalies.append(anomaly)
                
        return {"anomalies": anomalies}

    def _node_calculate_final_score(self, state: FraudDetectionAgentState):
        """Calculate a final score based on the anomalies found."""
        print("  -> Calculating final fraud score...")
        final_score = sum(anomaly.get("score_impact", 0) for anomaly in state["anomalies"])
        final_score = min(final_score, 1.0) # Cap the score at 1.0
        
        print(f"    Final fraud score: {final_score:.2f}")
        return {"final_score": final_score}

    async def _node_finish_screening(self, state: FraudDetectionAgentState):
        app_id = state["application_id"]
        print(f"AGENT: Finishing fraud screening for {app_id}")
        
        # 1. Create the Command object with the results of the agent's work.
        command = RecordFraudScreening(
            application_id=app_id,
            session_id=self.session_id, # Assumes session_id is stored on self
            fraud_score=state["final_score"],
            recommendation="REVIEW" if state["final_score"] > 0.4 else "PASS",
            anomalies=state["anomalies"]
        )
        
        # 2. Dispatch the command to the handler.
        try:
            # The agent's job is done. It just calls the handler and trusts it to do the work.
            await handle_record_fraud_screening(command, self.event_store)
            print(f"  -> Successfully dispatched RecordFraudScreening command.")
        except Exception as e:
            print(f"  -> CRITICAL ERROR: Command handler failed for {app_id}: {e}")
        
        return {}

