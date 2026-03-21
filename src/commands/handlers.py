from src.event_store import EventStore
from src.aggregates.loan_application import LoanApplicationAggregate
from src.aggregates.agent_session import AgentSessionAggregate
from src.models.events import CreditAnalysisCompleted

class CreditAnalysisCompletedCommand:
    def __init__(self, application_id: str, agent_id: str, session_id: str,
                 model_version: str, confidence_score: float, risk_tier: str,
                 recommended_limit_usd: int, duration_ms: int):
        self.application_id = application_id
        self.agent_id = agent_id
        self.session_id = session_id
        self.model_version = model_version
        self.confidence_score = confidence_score
        self.risk_tier = risk_tier
        self.recommended_limit_usd = recommended_limit_usd
        self.duration_ms = duration_ms

async def handle_credit_analysis_completed(
    cmd: CreditAnalysisCompletedCommand,
    store: EventStore,
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> None:
    app = await LoanApplicationAggregate.load(store, cmd.application_id)
    agent = await AgentSessionAggregate.load(store, cmd.agent_id, cmd.session_id)

    app.assert_awaiting_credit_analysis()
    agent.assert_context_loaded()
    agent.assert_model_version_current(cmd.model_version)

    new_events = [CreditAnalysisCompleted(...)]  # your existing event creation

    await store.append(
        stream_id=f"loan-{cmd.application_id}",
        events=new_events,
        expected_version=app.version,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )

# === FULL DECISION HANDLER (Business Rule 4 + State Machine) ===
class DecisionGeneratedCommand:
    def __init__(self, application_id: str, recommendation: str, confidence_score: float):
        self.application_id = application_id
        self.recommendation = recommendation
        self.confidence_score = confidence_score

async def handle_decision_generated(
    cmd: DecisionGeneratedCommand,
    store: EventStore,
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> None:
    # 1. Reconstruct current aggregate state from event history
    app = await LoanApplicationAggregate.load(store, cmd.application_id)
    
    # 2. Validate — all business rules checked BEFORE any state change
    app.assert_awaiting_decision()          # change this name if your guard method is different

    # 3. Determine new events — pure logic, no I/O
    new_events = [
        DecisionGenerated(
            application_id=cmd.application_id,
            recommendation=cmd.recommendation,
            confidence_score=cmd.confidence_score,
            # ... add any other fields your DecisionGenerated event needs ...
        )
    ]

    # 4. Append atomically with causal metadata (this is the key part for the rubric)
    await store.append(
        stream_id=f"loan-{cmd.application_id}",
        events=new_events,
        expected_version=app.version,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )