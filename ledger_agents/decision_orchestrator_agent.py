# ledger_agents/decision_orchestrator_agent.py

from typing import TypedDict
from langgraph.graph import StateGraph, END
import os
import json
import httpx
import certifi

# --- THIS IS THE CHANGE ---
# Use the stable and standard OpenAI library
from openai import AsyncOpenAI
from decimal import Decimal
from datetime import date, datetime
from src.event_store import EventStore
from src.aggregates.loan_application import LoanApplicationAggregate as LoanApplication

def json_serializer(obj):
    """Custom JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj) # Convert Decimal to a simple string
    raise TypeError(f"Type {type(obj)} not serializable")

# (State class is unchanged)
class DecisionOrchestratorState(TypedDict):
    application_id: str; credit_analysis_output: dict; fraud_screening_output: dict; compliance_check_output: dict; decision: dict 

class DecisionOrchestratorAgent:
    def __init__(self, event_store: EventStore):
        api_key = os.environ.get("OPENROUTER_API_KEY")
        base_url = os.environ.get("OPENROUTER_API_BASE")
        if not api_key or not base_url:
            raise ValueError("OPENROUTER_API_KEY and OPENROUTER_API_BASE must be set in .env file.")
        
        self.event_store = event_store
        
        # --- THIS IS THE FIX ---
        # We are explicitly creating an httpx client and telling it where to find
        # the SSL certificates, ignoring the broken environment variable.
        
        # Create an SSL context that points to the certifi bundle
        ssl_context = httpx.create_ssl_context(
            verify=certifi.where()
        )

        # Initialize the OpenAI client with our custom httpx client
        self.llm_client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=httpx.AsyncClient(verify=ssl_context)
        )
        # --- END OF FIX ---
        
        self.workflow = self._build_graph()

    def _build_graph(self):
        # ... (This is unchanged)
        workflow = StateGraph(DecisionOrchestratorState); workflow.add_node("gather_inputs", self._node_gather_inputs); workflow.add_node("synthesize_and_decide", self._node_synthesize_and_decide); workflow.add_node("execute_decision", self._node_execute_decision); workflow.set_entry_point("gather_inputs"); workflow.add_edge("gather_inputs", "synthesize_and_decide"); workflow.add_edge("synthesize_and_decide", "execute_decision"); workflow.add_edge("execute_decision", END)
        return workflow.compile()

    async def _node_gather_inputs(self, state: DecisionOrchestratorState):
        # ... (This is unchanged)
        app_id = state["application_id"]; print(f"AGENT: Orchestrator starting for application {app_id}"); print("  -> Gathering inputs..."); credit_stream_id = f"credit-{app_id}"; credit_events = await self.event_store.load_stream(credit_stream_id); credit_output = {}; 
        for event in reversed(credit_events):
            if event.event_type == "CreditAnalysisCompleted": credit_output = event.payload.get("decision", {}); break
        fraud_stream_id = f"fraud-{app_id}"; fraud_events = await self.event_store.load_stream(fraud_stream_id); fraud_output = {}; 
        for event in reversed(fraud_events):
            if event.event_type == "FraudScreeningCompleted": fraud_output = event.payload; break
        compliance_stream_id = f"compliance-{app_id}"; compliance_events = await self.event_store.load_stream(compliance_stream_id); compliance_output = {}; 
        for event in reversed(compliance_events):
            if event.event_type == "ComplianceCheckCompleted": compliance_output = event.payload; break
        print(f"    - Credit: {credit_output}"); print(f"    - Fraud: {fraud_output}"); print(f"    - Compliance: {compliance_output}"); 
        if not all([credit_output, fraud_output, compliance_output]): raise ValueError(f"Could not gather all inputs for {app_id}.")
        return {"credit_analysis_output": credit_output, "fraud_screening_output": fraud_output, "compliance_check_output": compliance_output}

    # --- THIS METHOD IS UPDATED FOR OPENAI/OPENROUTER ---
    async def _node_synthesize_and_decide(self, state: DecisionOrchestratorState):
        print("  -> Synthesizing inputs with an LLM via OpenRouter...")
        prompt = f"""You are a loan underwriter AI... (prompt is the same as before) ... Respond only with the requested JSON object.
        DATA:
        <CreditAnalysis>{json.dumps(state['credit_analysis_output'], default=json_serializer)}</CreditAnalysis>
        <FraudScreening>{json.dumps(state['fraud_screening_output'], default=json_serializer)}</FraudScreening>
        <ComplianceCheck>{json.dumps(state['compliance_check_output'], default=json_serializer)}</ComplianceCheck>
        """
        try:
            response = await self.llm_client.chat.completions.create(
                model="anthropic/claude-3.5-sonnet",  # We can still use Gemini, but via OpenRouter's stable API
                response_format={"type": "json_object"}, # Ask for JSON directly
                messages=[{"role": "user", "content": prompt}]
            )
            decision_text = response.choices[0].message.content
            print(f"    - Raw LLM Response: {decision_text}")
            decision_json = json.loads(decision_text)
            decision_json["amount"] = Decimal(decision_json.get("amount", 0))
            print(f"    - Parsed LLM Decision: {decision_json}")
            return {"decision": decision_json}
        except Exception as e:
            print(f"  -> CRITICAL ERROR: LLM call failed: {e}")
            decision = {"verdict": "REVIEW", "amount": Decimal("0"), "reasons": ["LLM synthesis failed."]}
            return {"decision": decision}

    async def _node_execute_decision(self, state: DecisionOrchestratorState):
        app_id = state["application_id"]
        decision = state["decision"]
        # Get the compliance output gathered in the first node
        compliance_output = state["compliance_check_output"]
        
        # --- THIS IS THE ONLY PART YOU NEED TO ADD/REPLACE ---
        # Robustly determine the final verdict from the LLM's response
        verdict = "UNKNOWN"
        if "decision" in decision and decision["decision"] in ["APPROVE", "DECLINE", "REVIEW"]:
            verdict = decision["decision"]
        elif decision.get("approved") is True:
            verdict = "APPROVE"
        elif decision.get("approved") is False:
            verdict = "DECLINE"
        elif "verdict" in decision:
            verdict = decision["verdict"]
        else:
            verdict = "REVIEW" # Safe fallback
        # --- END OF THE ADDITION ---

        print(f"  -> Executing final decision for {app_id}: {verdict}")
        stream_id = f"loan-{app_id}"
        
        try:
            from src.aggregates.loan_application import LoanApplicationAggregate
            loan_app = await LoanApplicationAggregate.load(self.event_store, app_id)
            
            new_event = None
            if verdict == "APPROVE":
                # This part of your code is already correct
                new_event = loan_app.approve_application(
                    compliance_verdict=compliance_output.get("overall_verdict", "UNKNOWN"),
                    approved_amount=Decimal(decision.get("limit_usd", 0) or decision.get("max_loan_amount", 0)),
                    interest_rate=float(decision.get("interest_rate", 5.5)),
                    term=36,
                    approved_by="DecisionOrchestratorAgent v1.0"
                )
            elif verdict == "DECLINE":
                # This part of your code is also correct
                reasons = decision.get("reasons") or [decision.get("reason_code", "Declined by LLM analysis.")]
                new_event = loan_app.decline_application(
                    reasons=reasons,
                    declined_by="DecisionOrchestratorAgent v1.0"
                )
            
            if new_event:
                await self.event_store.append(
                    stream_id=stream_id,
                    events=[new_event.to_store_dict()],
                    expected_version=loan_app.version
                )
                print(f"    - 1 final decision event recorded to stream '{stream_id}'")
                
        except Exception as e:
            print(f"  -> CRITICAL ERROR: Could not execute final decision for {app_id}: {e}")
            
        return {}
