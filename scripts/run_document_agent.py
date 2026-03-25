# scripts/run_document_agent.py

# --- START: FINAL, CORRECT PATH MODIFICATION ---
import sys
import os

# # 1. Add the Week 5 project root to the path (This is correct)
# project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# sys.path.insert(0, project_root)

# # 2. Add the Week 3 project root to the path (This is the fix)
# week3_root_path = os.path.abspath("C:/Users/Yakob/Desktop/10 Academy/Week-3/doc-intelligence-refinery")
# sys.path.insert(0, week3_root_path)
# # --- END OF FIX ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)



# The rest of the file...
import asyncio
# ...

# Now, the rest of your imports will work
import asyncio
import uuid
from dotenv import load_dotenv

from ledger_agents.document_processing_agent import DocumentProcessingAgent, DocumentProcessingAgentState
# ... rest of the file is unchanged

from src.event_store import EventStore
from ledger_agents.document_processing_agent import DocumentProcessingAgent, DocumentProcessingAgentState
from src.aggregates.document_package import DocumentPackage


# --- Configuration ---
# We will test with application APEX-0007, as it's one of the first in the simulation.
TEST_APPLICATION_ID = "APEX-0008" 

async def main():
    """
    This script simulates the invocation of the DocumentProcessingAgent for a specific application.
    """
    # 1. Setup connection
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")

    event_store = EventStore(db_url)
    await event_store.connect()

    print("="*60)
    print(f"🚀 Running Document Processing Agent for Application: {TEST_APPLICATION_ID}")
    print("="*60)

    # 2. Prepare the Aggregate and Initial State
    # In a real system, another agent or process would have already created this package
    # and added the documents. We will simulate that here.
    package_stream_id = f"docpkg-{TEST_APPLICATION_ID}"
    doc_package = DocumentPackage()
    doc_package.stream_id = package_stream_id # Manually set stream for new aggregate
    
    doc_package.create_package(
        package_id=package_stream_id,
        application_id=TEST_APPLICATION_ID,
        required_docs=["income_statement", "balance_sheet"]
    )
    
    # Simulate finding uploaded documents in the filesystem
    doc_path_base = f"./documents/{TEST_APPLICATION_ID}"
    doc1_id = str(uuid.uuid4())
    doc2_id = str(uuid.uuid4())

    doc_package.add_document(
        document_id=doc1_id,
        document_type="income_statement",
        document_format="pdf",
        file_hash="dummy_hash_1" # In real life, this would be a hash of the file
    )
    doc_package.add_document(
        document_id=doc2_id,
        document_type="balance_sheet",
        document_format="pdf",
        file_hash="dummy_hash_2"
    )

    # Save these setup events to the store
    await event_store.append_to_stream(doc_package)
    print(f"✅ Initial DocumentPackage created for {TEST_APPLICATION_ID} with {len(doc_package.new_events)} events.")


    # 3. Prepare the agent's input state
    agent_input: DocumentProcessingAgentState = {
        "application_id": TEST_APPLICATION_ID,
        "documents_to_process": [
            {"doc_id": doc1_id, "file_path": f"{doc_path_base}/income_statement_2024.pdf", "doc_type": "income_statement"},
            {"doc_id": doc2_id, "file_path": f"{doc_path_base}/balance_sheet_2024.pdf", "doc_type": "balance_sheet"},
        ],
        "results": [] # Always start with empty results
    }

    # 4. Invoke the agent's workflow
    agent = DocumentProcessingAgent(event_store)
    
    # The `astream` method runs the graph and yields the final state.
    final_state = None
    async for event in agent.workflow.astream(agent_input):
        print(f"-> Agent State: {event}")
        final_state = event

    print("\n✅ Agent workflow finished.")
    print("----------------------------------------")
    print("Final State:")
    # The final state will contain the results from all nodes
    print(final_state)
    print("========================================")
    print("\n🔎 To verify, check the 'events' table in your database for new 'ExtractionCompleted' events in the 'docpkg-APEX-0007' stream.")


if __name__ == "__main__":
    # Import the init_db function
    from scripts.init_db import main as init_db

    # Run init_db first to guarantee a clean slate
    print("Initializing clean database...")
    asyncio.run(init_db())

    # Now run the main agent test
    asyncio.run(main())
