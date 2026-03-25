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
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url: raise ValueError("DATABASE_URL not set")

    event_store = EventStore(db_url)
    await event_store.connect()

    # --- TEST CASE 1: High Net Margin Anomaly ---
    print("\n--- TEST CASE 1: High Net Margin Anomaly ---")
    high_margin_facts = {
        "total_revenue": Decimal("1000000"), "net_income": Decimal("450000"),
        "total_assets": Decimal("2000000"), "total_liabilities": Decimal("500000"),
        "total_equity": Decimal("1500000")
    }
    agent_input_1: FraudDetectionAgentState = {
        "application_id": "APEX-0012", "financial_facts": high_margin_facts,
        "anomalies": [], "final_score": 0.0
    }
    agent_1 = FraudDetectionAgent(event_store)
    final_state_1 = {}
    async for event in agent_1.workflow.astream(agent_input_1):
        final_state_1.update(event)
    print("\n✅ Agent workflow finished for Test Case 1.")
    print(f"  -> Final Score: {final_state_1.get('calculate_final_score', {}).get('final_score', 0.0):.2f}")
    print("----------------------------------------")

    # --- TEST CASE 2: Imbalanced Balance Sheet ---
    print("\n--- TEST CASE 2: Imbalanced Balance Sheet Anomaly ---")
    imbalanced_facts = {
        "total_revenue": Decimal("1000000"), "net_income": Decimal("100000"),
        "total_assets": Decimal("2000000"), "total_liabilities": Decimal("500000"),
        "total_equity": Decimal("1499990")
    }
    agent_input_2: FraudDetectionAgentState = {
        "application_id": "APEX-0018", "financial_facts": imbalanced_facts,
        "anomalies": [], "final_score": 0.0
    }
    agent_2 = FraudDetectionAgent(event_store)
    final_state_2 = {}
    async for event in agent_2.workflow.astream(agent_input_2):
        final_state_2.update(event)
    print("\n✅ Agent workflow finished for Test Case 2.")
    print(f"  -> Final Score: {final_state_2.get('calculate_final_score', {}).get('final_score', 0.0):.2f}")
    print("========================================")

if __name__ == "__main__":
    # We always start with a clean slate for this test script
    import asyncio
    from scripts.init_db import main as init_db

    print("Initializing clean database...")
    asyncio.run(init_db())
    
    print("\nRunning agent tests...")
    asyncio.run(main())
