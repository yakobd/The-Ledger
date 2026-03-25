# scripts/run_full_pipeline.py
import json
import sys, os, asyncio, uuid
from dotenv import load_dotenv
from decimal import Decimal
from datetime import datetime, timezone

# --- Path Setup ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.event_store import EventStore
from src.aggregates.document_package import DocumentPackage
from src.aggregates.loan_application import LoanApplicationAggregate as LoanApplication
from src.models.events import ApplicationSubmitted

# Import Agents and the new Regulatory Package function
from ledger_agents.document_processing_agent import DocumentProcessingAgent, DocumentProcessingAgentState
from ledger_agents.fraud_detection_agent import FraudDetectionAgent, FraudDetectionAgentState
from ledger_agents.compliance_agent import ComplianceAgent, ComplianceAgentState
from ledger_agents.decision_orchestrator_agent import DecisionOrchestratorAgent, DecisionOrchestratorState
from src.regulatory.package import generate_regulatory_package

# --- Test Config ---
TEST_APPLICATION_ID = "APEX-FINAL-TEST"

async def main():
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url: raise ValueError("DATABASE_URL not set")
    
    event_store = EventStore(db_url)
    await event_store.connect()

    print("="*60)
    print(f"🚀 EXECUTING FULL E2E PIPELINE & REGULATORY TEST FOR: {TEST_APPLICATION_ID}")
    print("="*60)

    # --- 1. SETUP ---
    # (Setup logic is the same as before, creating a self-contained test case)
    print("\n[1/6] Setting up initial application state...")
    loan_app_stream_id = f"loan-{TEST_APPLICATION_ID}"
    submit_event = ApplicationSubmitted(application_id=TEST_APPLICATION_ID, applicant_id="COMP-FINAL", requested_amount_usd=50000, loan_purpose="expansion", loan_term_months=36, submission_channel="PARTNER", contact_email="final@test.com", contact_name="Final Test", submitted_at=datetime.now(timezone.utc), application_reference="ref-final")
    await event_store.append(stream_id=loan_app_stream_id, events=[submit_event.to_store_dict()], expected_version=0)
    doc_pkg_stream_id = f"docpkg-{TEST_APPLICATION_ID}"; doc_package = DocumentPackage(); doc_package.stream_id = doc_pkg_stream_id; doc_package.create_package(package_id=doc_pkg_stream_id, application_id=TEST_APPLICATION_ID, required_docs=[]); doc_package.add_document(document_id=str(uuid.uuid4()), document_type="income_statement", document_format="pdf", file_hash="dummy"); await event_store.append_to_stream(doc_package)
    print("✅ Initial events created successfully.")
    
    # --- 2. DOCUMENT PROCESSING ---
    print("\n[2/6] Running Document Processing Agent...")
    # ... (code for this step is unchanged) ...
    doc_agent=DocumentProcessingAgent(event_store); doc_input:DocumentProcessingAgentState={"application_id":TEST_APPLICATION_ID,"documents_to_process":[{"doc_id":list(doc_package.documents.keys())[0],"file_path":"./placeholder.pdf","doc_type":"income_statement"}],"results":[]}; doc_state={};
    async for e in doc_agent.workflow.astream_events(doc_input,version="v1"):
        if e["event"]=="on_end":doc_state=e["data"]["output"]
    print("✅ Document Processing Complete.")
    financial_facts={};
    for r in doc_state.get('extract_document_data',{}).get('results',[]):
        if r['status']=='success':financial_facts.update(r['facts'].model_dump())

    # --- 3. CREDIT, FRAUD, COMPLIANCE (Simplified) ---
    print("\n[3/6] Running Specialist Agents...")
    credit_stream_id=f"credit-{TEST_APPLICATION_ID}";await event_store.append(stream_id=credit_stream_id,events=[{"event_type":"CreditAnalysisCompleted","payload":{"decision":{"risk_tier":"LOW"}},"event_version":1}],expected_version=0)
    fraud_agent=FraudDetectionAgent(event_store);fraud_input:FraudDetectionAgentState={"application_id":TEST_APPLICATION_ID,"financial_facts":financial_facts,"anomalies":[],"final_score":0.0};await fraud_agent.workflow.ainvoke(fraud_input)
    compliance_agent=ComplianceAgent(event_store);compliance_input:ComplianceAgentState={"application_id":TEST_APPLICATION_ID,"applicant_jurisdiction":"DE","passed_rules":[],"failed_rules":[],"is_blocked":False};await compliance_agent.workflow.ainvoke(compliance_input)
    print("✅ Specialist Agents Complete.")

    # --- 4. DECISION ORCHESTRATOR ---
    print("\n[4/6] Running Decision Orchestrator Agent...")
    orch_agent=DecisionOrchestratorAgent(event_store);orch_input:DecisionOrchestratorState={"application_id":TEST_APPLICATION_ID,"credit_analysis_output":{},"fraud_screening_output":{},"compliance_check_output":{},"decision":{}};await orch_agent.workflow.ainvoke(orch_input)
    print("✅ Decision Orchestration Complete.")

    # --- 5. GENERATE REGULATORY PACKAGE ---
    print("\n[5/6] Generating Regulatory Package...")
    package_json = await generate_regulatory_package(store=event_store, application_id=TEST_APPLICATION_ID, examination_date=datetime.now(timezone.utc))
    print("✅ Package Generated.")

    # --- 6. VERIFY PACKAGE ---
    print("\n[6/6] Verifying Package Content...")
    package_data = json.loads(package_json)
    assert package_data["applicationId"] == TEST_APPLICATION_ID
    assert len(package_data["fullEventStream"]) > 0, "Event stream should not be empty"
    assert package_data["finalIntegrityCheck"]["events_verified"] > 0, "Integrity check should have verified events"
    print("✅ Package content verified successfully.")

    print("\n🎉 ALL DELIVERABLES STRUCTURALLY COMPLETE AND VERIFIED! 🎉")

if __name__ == "__main__":
    from scripts.init_db import main as init_db
    print("Initializing clean database...")
    asyncio.run(init_db())
    asyncio.run(main())
