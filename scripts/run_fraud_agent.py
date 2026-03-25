# scripts/run_fraud_agent.py
import sys
import os

# Add the project's root directory to the path to find sibling folders like 'src'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

import asyncio
import os
from dotenv import load_dotenv
from decimal import Decimal

from src.event_store import EventStore
from ledger_agents.fraud_detection_agent import FraudDetectionAgent, FraudDetectionAgentState

# --- Configuration ---
TEST_APPLICATION_ID = "APEX-0012" # A new application ID for this test

async def main():
    """
    This script invokes the FraudDetectionAgent with sample financial facts.
    """
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")

    event_store = EventStore(db_url)
    await event_store.connect()

    print("="*60)
    print(f"🚀 Running Fraud Detection Agent for Application: {TEST_APPLICATION_ID}")
    print("="*60)

    # --- TEST CASE 1: High Net Margin Anomaly ---
    print("--- TEST CASE 1: High Net Margin Anomaly ---")
    high_margin_facts = {
        "total_revenue": Decimal("1000000"), "net_income": Decimal("450000"),
        "total_assets": Decimal("2000000"), "total_liabilities": Decimal("500000"),
        "total_equity": Decimal("1500000")
    }
    agent_input: FraudDetectionAgentState = {
        "application_id": TEST_APPLICATION_ID, "financial_facts": high_margin_facts,
        "anomalies": [], "final_score": 0.0
    }
    agent = FraudDetectionAgent(event_store)
    
    final_state_1 = {}
    async for event in agent.workflow.astream(agent_input):
        final_state_1.update(event) # Accumulate all state changes

    print("\n✅ Agent workflow finished.")
    # --- THIS IS THE FIX ---
    # The final_score is under the key of the node that produced it.
    print(f"  -> Final Score: {final_state_1.get('calculate_final_score', {}).get('final_score', 0.0):.2f}")
    print("----------------------------------------")

    # --- TEST CASE 2: Imbalanced Balance Sheet ---
    print("\n--- TEST CASE 2: Imbalanced Balance Sheet Anomaly ---")
    TEST_APPLICATION_ID_2 = "APEX-0018"
    imbalanced_facts = {
        "total_revenue": Decimal("1000000"), "net_income": Decimal("100000"),
        "total_assets": Decimal("2000000"), "total_liabilities": Decimal("500000"),
        "total_equity": Decimal("1499990")
    }
    agent_input_2: FraudDetectionAgentState = {
        "application_id": TEST_APPLICATION_ID_2, "financial_facts": imbalanced_facts,
        "anomalies": [], "final_score": 0.0
    }

    final_state_2 = {}
    async for event in agent.workflow.astream(agent_input_2):
        final_state_2.update(event) # Accumulate all state changes
    
    print("\n✅ Agent workflow finished.")
    # --- THIS IS THE FIX ---
    print(f"  -> Final Score: {final_state_2.get('calculate_final_score', {}).get('final_score', 0.0):.2f}")
    print("========================================")
    print("\n🔎 To verify, check the 'events' table in your database...")

if __name__ == "__main__":
    # We always start with a clean slate for this test script
    import asyncio
    from scripts.init_db import main as init_db

    print("Initializing clean database...")
    asyncio.run(init_db())
    
    print("\nRunning agent tests...")
    asyncio.run(main())
