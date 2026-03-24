# agents/document_processing_agent.py

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

from src.event_store import EventStore
from src.aggregates.document_package import DocumentPackage
from src.models.events import FinancialFacts # Assuming FinancialFacts is in events.py

# --- TODO: Import your Week 3 document extraction logic ---
# from your_week_3_project.extraction import extract_financial_facts_from_pdf

class DocumentProcessingAgentState(TypedDict):
    application_id: str
    documents_to_process: list[dict] # e.g., [{"doc_id": "...", "file_path": "...", "doc_type": "..."}]
    results: Annotated[list[dict], operator.add]

class DocumentProcessingAgent:

    def __init__(self, event_store: EventStore):
        self.event_store = event_store
        self.workflow = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(DocumentProcessingAgentState)

        workflow.add_node("start_processing", self._node_start_processing)
        workflow.add_node("extract_document_data", self._node_extract_document_data)
        workflow.add_node("finish_processing", self._node_finish_processing)

        workflow.set_entry_point("start_processing")
        workflow.add_edge("start_processing", "extract_document_data")
        workflow.add_edge("extract_document_data", "finish_processing")
        workflow.add_edge("finish_processing", END)

        return workflow.compile()

    def _node_start_processing(self, state: DocumentProcessingAgentState):
        app_id = state["application_id"]
        print(f"AGENT: Starting document processing for application {app_id}")
        # In a real system, we would also record an AgentSessionStarted event here.
        # For this step, we focus on the core logic.
        return {"results": []}

    def _node_extract_document_data(self, state: DocumentProcessingAgentState):
        all_results = []
        for doc in state["documents_to_process"]:
            print(f"  -> Processing document: {doc['file_path']}")
            
            # --- TODO: THIS IS THE CORE OF YOUR TASK ---
            # You need to call your Week 3 code here.
            # It should take a file path and return a dictionary of financial facts.
            
            # Example:
            # financial_facts_dict = extract_financial_facts_from_pdf(doc['file_path'])
            # raw_text = "..." # Your Week 3 code might also give you this
            
            # For now, we will use placeholder data:
            financial_facts_dict = {"total_revenue": 500000, "net_income": 50000}
            raw_text_length = 1500
            
            result = {
                "document_id": doc["doc_id"],
                "document_type": doc["doc_type"],
                "facts": financial_facts_dict,
                "raw_text_length": raw_text_length
            }
            all_results.append(result)
            
        return {"results": all_results}

    def _node_finish_processing(self, state: DocumentProcessingAgentState):
        app_id = state["application_id"]
        print(f"AGENT: Finishing document processing for application {app_id}")

        # --- TODO: Record the results back to the Event Store ---
        # 1. Load the DocumentPackage aggregate for this application.
        #    The stream_id will be `docpkg-{app_id}`
        stream_id = f"docpkg-{app_id}"
        
        # 2. For each result, call the aggregate's command method.
        #    This will create the ExtractionCompleted events.
        
        # Example (you will need to implement the async logic):
        # for res in state["results"]:
        #     doc_package.record_extraction_results(
        #         document_id=res["document_id"],
        #         document_type=res["document_type"],
        #         facts=res["facts"],
        #         raw_text_length=res["raw_text_length"]
        #     )
        
        # 3. Append the new events to the stream.
        
        print("  -> Results recorded to event stream.")
        return {}

