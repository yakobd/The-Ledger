from typing import List
from ledger.event_store import EventStore
from ledger.schema.events import StoredEvent
from enum import Enum

class ApplicationState(Enum):
    SUBMITTED = "SUBMITTED"
    AWAITING_ANALYSIS = "AWAITING_ANALYSIS"
    ANALYSIS_COMPLETE = "ANALYSIS_COMPLETE"
    COMPLIANCE_REVIEW = "COMPLIANCE_REVIEW"
    PENDING_DECISION = "PENDING_DECISION"
    APPROVED_PENDING_HUMAN = "APPROVED_PENDING_HUMAN"
    DECLINED_PENDING_HUMAN = "DECLINED_PENDING_HUMAN"
    FINAL_APPROVED = "FINAL_APPROVED"
    FINAL_DECLINED = "FINAL_DECLINED"

class LoanApplicationAggregate:
    def __init__(self, application_id: str):
        self.application_id = application_id
        self.state = ApplicationState.SUBMITTED
        self.version = -1
        self.applicant_id = None
        self.requested_amount = None
        self.approved_amount = None

    @classmethod
    async def load(cls, store: EventStore, application_id: str) -> "LoanApplicationAggregate":
        events: List[StoredEvent] = await store.load_stream(f"loan-{application_id}")
        agg = cls(application_id)
        for event in events:
            agg._apply(event)
        return agg

    def _apply(self, event: StoredEvent) -> None:
        handler = getattr(self, f"_on_{event.event_type}", None)
        if handler:
            handler(event)
        self.version = event.stream_position

    def _on_ApplicationSubmitted(self, event: StoredEvent) -> None:
        self.state = ApplicationState.SUBMITTED
        self.applicant_id = event.payload["applicant_id"]
        self.requested_amount = event.payload["requested_amount_usd"]

    def _on_CreditAnalysisCompleted(self, event: StoredEvent) -> None:
        self.state = ApplicationState.ANALYSIS_COMPLETE

    def _on_ApplicationApproved(self, event: StoredEvent) -> None:
        self.state = ApplicationState.FINAL_APPROVED
        self.approved_amount = event.payload["approved_amount_usd"]
    
    def _on_PackageReadyForAnalysis(self, event: StoredEvent) -> None:
        self.state = ApplicationState.AWAITING_ANALYSIS

    def assert_awaiting_credit_analysis(self) -> None:
        if self.state != ApplicationState.AWAITING_ANALYSIS:
            raise ValueError(f"Application {self.application_id} is not awaiting credit analysis (current state: {self.state})")