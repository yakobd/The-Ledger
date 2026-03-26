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

    # In src/aggregates/loan_application.py

    # Add these two methods to the BOTTOM of your existing LoanApplicationAggregate class

    # --- Command Methods ---
    def approve_application(
    self,
    # Add the new parameter
    compliance_verdict: str, 
    approved_amount: "Decimal", 
    interest_rate: float, 
    term: int, 
    approved_by: str
    ):
        self.assert_is_pending_decision()
    # Business Rule #5: Compliance Dependency
        if compliance_verdict != "CLEAR":
            raise DomainError(f"Cannot approve application. Compliance check failed with verdict: {compliance_verdict}")
        print("  -> BUSINESS RULE: Compliance check is CLEAR. Proceeding with approval.")

        if self.state in ["APPROVED", "DECLINED"]:
            raise DomainError(f"Application is already in a terminal state: {self.state}")
            
        from src.models.events import ApplicationApproved
        
        return ApplicationApproved(
            application_id=self.application_id,
            approved_amount_usd=approved_amount,
            interest_rate_pct=interest_rate,
            term_months=term,
            conditions=[],
            approved_by=approved_by,
            effective_date=self._now().date().isoformat(),
            approved_at=self._now()
        )

    def decline_application(self, reasons: list[str], declined_by: str):
        # self.assert_can_be_approved() # Optional guard clause
        self.assert_is_pending_decision()
        from src.models.events import ApplicationDeclined
        if self.state in ["APPROVED", "DECLINED"]: ...
        return ApplicationDeclined(
            application_id=self.application_id,
            decline_reasons=reasons,
            declined_by=declined_by,
            adverse_action_notice_required=True,
            adverse_action_codes=[],
            declined_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)
        )

    def generate_decision(self, orchestrator_session_id: str, recommendation: str, confidence_score: float, model_versions: dict):
        """
        Applies the 'Confidence Floor' business rule before generating a decision.
        """
        # Business Rule #4: Confidence Floor
        final_recommendation = recommendation
        if confidence_score < 0.6:
            print("  -> BUSINESS RULE: Confidence score < 0.6. Overriding recommendation to REFER.")
            final_recommendation = "REFER"

        # We need to import the event class
        from src.models.events import DecisionGenerated
        
        # This aggregate doesn't use self.record(), so we create and return the event
        return DecisionGenerated(
            application_id=self.application_id,
            orchestrator_session_id=orchestrator_session_id,
            recommendation=final_recommendation,
            confidence=confidence_score,
            # Placeholders for other fields
            executive_summary="Decision generated based on agent synthesis.",
            key_risks=[],
            contributing_sessions=[],
            model_versions=model_versions,
            generated_at=self._now()
        )

    def assert_state_is(self, expected_state: ApplicationState):
        """Generic guard to check for a specific state."""
        if self.state != expected_state:
            raise DomainError(f"Invalid state: Expected {expected_state.value} but was {self.state.value}")

    def assert_is_pending_decision(self):
        """Checks if all analyses are complete."""
        # This is a more explicit version of your `assert_awaiting_decision`
        required_states = {
            ApplicationState.CREDIT_COMPLETED,
            ApplicationState.FRAUD_COMPLETED,
            ApplicationState.COMPLIANCE_COMPLETED,
        }
        # This logic is complex. For now, we will just check if we are in DECISION_PENDING
        if self.state != ApplicationState.DECISION_PENDING:
             raise DomainError(f"Not all analyses are complete. Current state: {self.state.value}")

    def assert_is_pending_decision(self):
        """
        Business Rule: A final decision can only be made after all specialist
        agents have completed their work.
        """
        # This is a simplified check. A more complex check would look at the
        # state of all required analyses. For now, we ensure the state was
        # explicitly moved to DECISION_PENDING by a previous event handler.
        if self.state != ApplicationState.DECISION_PENDING:
             raise DomainError(
                 f"Invalid state transition. Cannot make a final decision. "
                 f"Application is in state '{self.state.value}', but must be 'DECISION_PENDING'."
             )
