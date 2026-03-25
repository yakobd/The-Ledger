# scripts/run_full_pipeline.py

import sys, os, asyncio, uuid
from dotenv import load_dotenv
from decimal import Decimal

# --- Path Setup ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.event_store import EventStore
# Import the aggregates we need to load
from src.aggregates.document_package import DocumentPackage
from src.aggregates.loan_application import LoanApplicationAggregate as LoanApplication

# Import the agents
from ledger_agents.document_processing_agent import DocumentProcessingAgent, DocumentProcessingAgentState
from ledger_agents.fraud_detection_agent import FraudDetectionAgent, FraudDetectionAgentState
from ledger_agents.compliance_agent import ComplianceAgent, ComplianceAgentState
from ledger_agents.decision_orchestrator_agent import DecisionOrchestratorAgent, DecisionOrchestratorState

# --- Test Config ---
TEST_APPLICATION_ID = "APEX-0008"

async def main():
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url: raise ValueError("DATABASE_URL not set")
    
    event_store = EventStore(db_url)
    await event_store.connect()

    print("="*60)
    print(f"🚀 EXECUTING FULL AGENT PIPELINE FOR: {TEST_APPLICATION_ID}")
    print("="*60)

    # --- THIS BLOCK IS NEW AND CORRECTED ---
    # Load the existing DocumentPackage aggregate that `datagen` created
    doc_package_stream_id = f"docpkg-{TEST_APPLICATION_ID}"
    doc_package = await event_store.load_aggregate(doc_package_stream_id, DocumentPackage)
    
    # Prepare the list of documents for the agent based on the loaded aggregate state
    documents_to_process = [
        {"doc_id": doc_id, "file_path": f"./documents/{TEST_APPLICATION_ID}/{doc_type}_2024.pdf", "doc_type": doc_type}
        for doc_id, doc_type in doc_package.documents.items() if "2024" in doc_type or "proposal" not in doc_type
    ]
    # --- END OF CORRECTION ---

    # --- 1. DOCUMENT PROCESSING ---
    print("\n[1/4] Running Document Processing Agent...")
    doc_agent = DocumentProcessingAgent(event_store)
    doc_input: DocumentProcessingAgentState = {
        "application_id": TEST_APPLICATION_ID,
        "documents_to_process": documents_to_process, # Use the list we just built
        "results": []
    }
    doc_state = {}
    # Use astream_events to get the full final state
    async for event in doc_agent.workflow.astream_events(doc_input, version="v1"):
        if event["event"] == "on_end":
            doc_state = event["data"]["output"]
            
    print("✅ Document Processing Complete.")
    
    # Extract the facts for the next agent, ensuring all keys exist
    financial_facts = {}
    # The results are now in a dictionary from the graph's state
    for result in doc_state.get('extract_document_data', {}).get('results', []):
        if result['status'] == 'success':
            # Merge facts from all successful documents
            financial_facts.update(result['facts'].model_dump())


    # --- 2. FRAUD DETECTION ---
    print("\n[2/4] Running Fraud Detection Agent...")
    fraud_agent = FraudDetectionAgent(event_store)
    fraud_input: FraudDetectionAgentState = {
        "application_id": TEST_APPLICATION_ID,
        "financial_facts": financial_facts, # Use the merged facts
        "anomalies": [], "final_score": 0.0
    }
    async for _ in fraud_agent.workflow.astream(fraud_input): pass
    print("✅ Fraud Detection Complete.")


    # --- 3. COMPLIANCE CHECK ---
    print("\n[3/4] Running Compliance Agent...")
    # For APEX-0007, the jurisdiction is 'CA'.
    compliance_agent = ComplianceAgent(event_store)
    compliance_input: ComplianceAgentState = {
        "application_id": TEST_APPLICATION_ID, "applicant_jurisdiction": "CA",
        "passed_rules": [], "failed_rules": [], "is_blocked": False
    }
    async for _ in compliance_agent.workflow.astream(compliance_input): pass
    print("✅ Compliance Check Complete.")

    # --- 4. DECISION ORCHESTRATOR ---
    print("\n[4/4] Running Decision Orchestrator Agent...")
    orch_agent = DecisionOrchestratorAgent(event_store)
    orch_input: DecisionOrchestratorState = {
        "application_id": TEST_APPLICATION_ID,
        "credit_analysis_output": {}, "fraud_screening_output": {},
        "compliance_check_output": {}, "decision": {}
    }
    # For this test, we need a placeholder credit event as our pipeline doesn't run it yet
    credit_stream_id = f"credit-{TEST_APPLICATION_ID}"
    await event_store.append(stream_id=credit_stream_id, events=[{"event_type": "CreditAnalysisCompleted", "payload": {"decision": {"risk_tier": "LOW"}}, "event_version": 1}], expected_version=0)

    async for _ in orch_agent.workflow.astream(orch_input): pass
    print("✅ Decision Orchestration Complete.")
    print("="*60)
    print("\n🎉 FULL PIPELINE FINISHED! 🎉")


if __name__ == "__main__":
    asyncio.run(main())
