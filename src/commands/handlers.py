from src.event_store import EventStore
from src.aggregates.loan_application import LoanApplicationAggregate
from src.aggregates.agent_session import AgentSessionAggregate

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

async def handle_credit_analysis_completed(cmd, store):
    app = await LoanApplicationAggregate.load(store, cmd.application_id)
    agent = await AgentSessionAggregate.load(store, cmd.agent_id, cmd.session_id)

    # Business rules (now safe to keep active)
    app.assert_awaiting_credit_analysis()
    agent.assert_context_loaded()
    agent.assert_model_version_current(cmd.model_version)

    new_events = [{
        "event_type": "CreditAnalysisCompleted",
        "event_version": 2,
        "payload": {
            "application_id": cmd.application_id,
            "agent_id": cmd.agent_id,
            "session_id": cmd.session_id,
            "model_version": cmd.model_version,
            "confidence_score": cmd.confidence_score,
            "risk_tier": cmd.risk_tier,
            "recommended_limit_usd": cmd.recommended_limit_usd,
            "analysis_duration_ms": cmd.duration_ms,
        }
    }]

    await store.append(
        stream_id=f"loan-{cmd.application_id}",
        events=new_events,
        expected_version=app.version,
    )
    print(f"✅ CreditAnalysisCompleted appended for {cmd.application_id}")


# === FULL DECISION HANDLER (Business Rule 4 + State Machine) ===
class DecisionGeneratedCommand:
    def __init__(self, application_id: str, recommendation: str, confidence_score: float):
        self.application_id = application_id
        self.recommendation = recommendation
        self.confidence_score = confidence_score

async def handle_decision_generated(cmd, store):
    app = await LoanApplicationAggregate.load(store, cmd.application_id)

    # Business Rule 4: Confidence floor (regulatory requirement)
    if cmd.confidence_score < 0.6:
        cmd.recommendation = "REFER"

    new_events = [{
        "event_type": "DecisionGenerated",
        "event_version": 1,
        "payload": {
            "application_id": cmd.application_id,
            "recommendation": cmd.recommendation,
            "confidence_score": cmd.confidence_score,
        }
    }]

    await store.append(
        stream_id=f"loan-{cmd.application_id}",
        events=new_events,
        expected_version=app.version,
    )
    print(f"✅ DecisionGenerated → {cmd.recommendation} for {cmd.application_id}")