# scripts/run_compliance_agent.py

# --- START: EXPLICIT PATH MODIFICATION ---
# This block MUST be at the very top of the file
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
# --- END: EXPLICIT PATH MODIFICATION ---


# Now all other imports will work correctly
import asyncio
from dotenv import load_dotenv

from src.event_store import EventStore
from ledger_agents.compliance_agent import ComplianceAgent, ComplianceAgentState

# --- Configuration ---
TEST_APP_PASS = "APEX-0025" # A company from California
TEST_APP_FAIL = "APEX-0075" # A company from Montana (as per the datagen)

async def main():
    """
    This script invokes the ComplianceAgent for two test cases.
    """
    # 1. Setup connection
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")

    event_store = EventStore(db_url)
    await event_store.connect()

    agent = ComplianceAgent(event_store)

    print("="*60)
    print(f"🚀 Running Compliance Agent")
    print("="*60)

    # --- TEST CASE 1: Allowed Jurisdiction ---
    print(f"\n--- TEST CASE 1: Allowed Jurisdiction (CA) for {TEST_APP_PASS} ---")
    
    agent_input_pass: ComplianceAgentState = {
        "application_id": TEST_APP_PASS,
        "applicant_jurisdiction": "CA",
        "passed_rules": [],
        "failed_rules": [],
        "is_blocked": False
    }

    final_state_pass = {}
    async for event in agent.workflow.astream(agent_input_pass):
        final_state_pass.update(event)
    
    print("\n✅ Agent workflow finished for PASS case.")
    print(f"  -> Is Blocked: {final_state_pass.get('check_jurisdiction_rule', {}).get('is_blocked')}")
    print("----------------------------------------")


    # --- TEST CASE 2: Blocked Jurisdiction ---
    print(f"\n--- TEST CASE 2: Blocked Jurisdiction (MT) for {TEST_APP_FAIL} ---")

    agent_input_fail: ComplianceAgentState = {
        "application_id": TEST_APP_FAIL,
        "applicant_jurisdiction": "MT", # Montana is on the block list
        "passed_rules": [],
        "failed_rules": [],
        "is_blocked": False
    }

    final_state_fail = {}
    async for event in agent.workflow.astream(agent_input_fail):
        final_state_fail.update(event)

    print("\n✅ Agent workflow finished for FAIL case.")
    print(f"  -> Is Blocked: {final_state_fail.get('check_jurisdiction_rule', {}).get('is_blocked')}")
    print("========================================")

    print("\n🔎 To verify, check the 'events' table for new events in the 'compliance-APEX-0025' and 'compliance-APEX-0075' streams.")


if __name__ == "__main__":
    # We need to import init_db *after* the path has been modified
    from scripts.init_db import main as init_db

    print("Initializing clean database...")
    asyncio.run(init_db())
    
    print("\nRunning agent tests...")
    asyncio.run(main())
