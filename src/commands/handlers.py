# src/commands/handlers.py

# --- Import from our new models file ---
from .models import (
    CreditAnalysisCompletedCommand, 
    DecisionGeneratedCommand,
    StartAgentSession,
    RecordFraudScreening
)
from src.event_store import EventStore
from src.aggregates.loan_application import LoanApplicationAggregate
from src.aggregates.agent_session import AgentSessionAggregate
from src.aggregates.fraud_screening import FraudScreening
from src.models.events import CreditAnalysisCompleted, DecisionGenerated # Keep these

# --- YOUR EXISTING HANDLERS (UNCHANGED) ---

async def handle_credit_analysis_completed(cmd: CreditAnalysisCompletedCommand, store: EventStore):
    app = await LoanApplicationAggregate.load(store, cmd.application_id)
    agent = await AgentSessionAggregate.load(store, cmd.agent_id, cmd.session_id)
    app.assert_awaiting_credit_analysis()
    agent.assert_context_loaded()
    agent.assert_model_version_current(cmd.model_version)
    new_event = CreditAnalysisCompleted(...) # Your logic here
    await store.append(stream_id=f"loan-{cmd.application_id}", events=[new_event.to_store_dict()], expected_version=app.version, correlation_id=cmd.correlation_id, causation_id=cmd.causation_id)

async def handle_decision_generated(cmd: DecisionGeneratedCommand, store: EventStore):
    app = await LoanApplicationAggregate.load(store, cmd.application_id)
    app.assert_awaiting_decision()
    new_event = DecisionGenerated(...) # Your logic here
    await store.append(stream_id=f"loan-{cmd.application_id}", events=[new_event.to_store_dict()], expected_version=app.version, correlation_id=cmd.correlation_id, causation_id=cmd.causation_id)


# --- ADD THESE NEW HANDLERS ---

async def handle_start_agent_session(cmd: StartAgentSession, store: EventStore):
    print(f"COMMAND HANDLER: Handling StartAgentSession for session {cmd.session_id[:8]}...")
    stream_id = f"agent-{cmd.agent_type}-{cmd.session_id}"
    agent_session = AgentSessionAggregate(agent_id=cmd.agent_type, session_id=cmd.session_id)
    start_event = agent_session.start_session(application_id=cmd.application_id, model_version=cmd.model_version)
    agent_session._apply(start_event)
    await store.append(stream_id=stream_id, events=[start_event.to_store_dict()], expected_version=0, correlation_id=cmd.correlation_id, causation_id=cmd.causation_id)
    print(f"  -> Successfully started agent session {cmd.session_id[:8]}.")

async def handle_record_fraud_screening(cmd: RecordFraudScreening, store: EventStore):
    print(f"COMMAND HANDLER: Handling RecordFraudScreening for app {cmd.application_id}...")
    stream_id = f"fraud-{cmd.application_id}"
    screening = FraudScreening()
    screening.stream_id = stream_id
    screening.initiate_screening(session_id=cmd.session_id, model_version="rule_based_v1")
    for anomaly in cmd.anomalies:
        screening.record_anomaly(anomaly_type=anomaly["anomaly_type"], description=anomaly["description"], severity=anomaly["severity"])
    screening.complete_screening(session_id=cmd.session_id, fraud_score=cmd.fraud_score, recommendation=cmd.recommendation)
    await store.append_to_stream(screening)
    print(f"  -> Fraud screening results recorded.")

