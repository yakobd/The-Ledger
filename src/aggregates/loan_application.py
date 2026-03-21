from enum import Enum
from src.models.events import StoredEvent, DomainError
from src.event_store import EventStore


class ApplicationState(Enum):
    SUBMITTED = "SUBMITTED"
    DOCUMENTS_UPLOADED = "DOCUMENTS_UPLOADED"
    DOCUMENTS_PROCESSED = "DOCUMENTS_PROCESSED"
    AWAITING_CREDIT_ANALYSIS = "AWAITING_CREDIT_ANALYSIS"
    CREDIT_COMPLETED = "CREDIT_COMPLETED"
    FRAUD_COMPLETED = "FRAUD_COMPLETED"
    COMPLIANCE_COMPLETED = "COMPLIANCE_COMPLETED"
    DECISION_PENDING = "DECISION_PENDING"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    REFERRED = "REFERRED"


class LoanApplicationAggregate:
    def __init__(self, application_id: str):
        self.application_id = application_id
        self.state = ApplicationState.SUBMITTED
        self.version = -1
        self.applicant_id = None
        self.requested_amount = 0
        self.approved_amount = None

    @classmethod
    async def load(cls, store: EventStore, application_id: str) -> "LoanApplicationAggregate":
        events = await store.load_stream(f"loan-{application_id}")
        agg = cls(application_id)
        for event in events:
            agg._apply(event)
        return agg

    def _apply(self, event: StoredEvent) -> None:
        handler = getattr(self, f"_on_{event.event_type}", None)
        if handler:
            handler(event)
        self.version = event.stream_position

    # ==================== Centralized Guard Methods (raise DomainError) ====================

    def assert_awaiting_credit_analysis(self):
        if self.state != ApplicationState.AWAITING_CREDIT_ANALYSIS:
            raise DomainError(
                f"Invalid transition: Application {self.application_id} "
                f"is not in AWAITING_CREDIT_ANALYSIS (current: {self.state.value})"
            )

    def assert_awaiting_decision(self):
        if self.state not in (ApplicationState.CREDIT_COMPLETED, 
                              ApplicationState.FRAUD_COMPLETED, 
                              ApplicationState.COMPLIANCE_COMPLETED):
            raise DomainError(
                f"Invalid transition: Application {self.application_id} "
                f"is not ready for decision (current: {self.state.value})"
            )

    def assert_can_be_approved(self):
        if self.state != ApplicationState.DECISION_PENDING:
            raise DomainError(
                f"Invalid transition: Application {self.application_id} "
                f"cannot be approved (current: {self.state.value})"
            )

    # ==================== Event Handlers ====================

    def _on_ApplicationSubmitted(self, event: StoredEvent):
        self.state = ApplicationState.SUBMITTED
        self.applicant_id = event.payload.get("applicant_id")
        self.requested_amount = event.payload.get("requested_amount_usd", 0)

    def _on_PackageReadyForAnalysis(self, event: StoredEvent):
        self.state = ApplicationState.AWAITING_CREDIT_ANALYSIS

    def _on_CreditAnalysisCompleted(self, event: StoredEvent):
        self.state = ApplicationState.CREDIT_COMPLETED

    def _on_FraudScreeningCompleted(self, event: StoredEvent):
        self.state = ApplicationState.FRAUD_COMPLETED

    def _on_ComplianceCheckCompleted(self, event: StoredEvent):
        self.state = ApplicationState.COMPLIANCE_COMPLETED

    def _on_DecisionGenerated(self, event: StoredEvent):
        self.state = ApplicationState.DECISION_PENDING

    def _on_ApplicationApproved(self, event: StoredEvent):
        self.state = ApplicationState.APPROVED
        self.approved_amount = event.payload.get("approved_amount_usd")

    def _on_ApplicationDeclined(self, event: StoredEvent):
        self.state = ApplicationState.DECLINED