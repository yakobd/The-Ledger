# src/aggregates/document_package.py

from .base import BaseAggregate
from src.models.events import (
    PackageCreated,
    DocumentAdded,
    ExtractionCompleted,
    ExtractionFailed,
    PackageReadyForAnalysis,
    BaseEvent
)

class DocumentPackage(BaseAggregate):
    def __init__(self):
        super().__init__()
        self.application_id: str | None = None
        self.documents: dict[str, str] = {}
        self.extractions_completed: set[str] = set()

    # This method is here to solve the inheritance bug we saw earlier.
    def has_new_events(self) -> bool:
        return len(self.new_events) > 0

    # --- State-Changing Methods ---
    
    def _apply_PackageCreated(self, event: BaseEvent):
        # --- THIS IS THE FIX ---
        # Handle both live, typed events and replayed StoredEvents
        if hasattr(event, 'payload'):
            self.application_id = event.payload.get('application_id')
        else:
            self.application_id = event.application_id

    def _apply_DocumentAdded(self, event: BaseEvent):
        # Handle both live, typed events and replayed StoredEvents
        if hasattr(event, 'payload'):
            doc_id = event.payload.get('document_id')
            doc_type = event.payload.get('document_type')
        else:
            doc_id = event.document_id
            doc_type = event.document_type
            
        if doc_id and doc_type:
            self.documents[doc_id] = doc_type

    def _apply_ExtractionCompleted(self, event: BaseEvent):
        # Handle both live, typed events and replayed StoredEvents
        if hasattr(event, 'payload'):
            doc_id = event.payload.get('document_id')
        else:
            doc_id = event.document_id
            
        if doc_id:
            self.extractions_completed.add(doc_id)
        
    def _apply_ExtractionFailed(self, event: BaseEvent):
        pass
        
    def _apply_PackageReadyForAnalysis(self, event: BaseEvent):
        pass

    # --- Command Methods (Unchanged) ---
    # ... (The rest of your file from create_package downwards is correct and unchanged) ...
    def create_package(self, package_id: str, application_id: str, required_docs: list) -> 'DocumentPackage':
        if self.version > 0:
            raise ValueError("DocumentPackage already exists.")
        self.record(PackageCreated(package_id=package_id, application_id=application_id, required_documents=required_docs, created_at=self._now()))
        return self

    def add_document(self, document_id: str, document_type: str, document_format: str, file_hash: str) -> 'DocumentPackage':
        if document_id in self.documents:
            return
        self.record(DocumentAdded(package_id=self.stream_id, document_id=document_id, document_type=document_type, document_format=document_format, file_hash=file_hash, added_at=self._now()))
        return self

    def record_extraction_results(self, document_id: str, document_type: str, facts: dict, raw_text_length: int) -> 'DocumentPackage':
        if document_id not in self.documents:
            raise ValueError(f"Document {document_id} not found in this package. Current docs: {list(self.documents.keys())}")
            
        self.record(ExtractionCompleted(package_id=self.stream_id, document_id=document_id, document_type=document_type, facts=facts, raw_text_length=raw_text_length, tables_extracted=0, processing_ms=0, completed_at=self._now()))
        
        temp_completed = self.extractions_completed | {document_id}
        if temp_completed == set(self.documents.keys()):
            self.record(PackageReadyForAnalysis(package_id=self.stream_id, application_id=self.application_id, documents_processed=len(self.documents), has_quality_flags=False, quality_flag_count=0, ready_at=self._now()))
        return self

