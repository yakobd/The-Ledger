# src/commands/models.py

from pydantic import BaseModel
from decimal import Decimal

class SubmitApplication(BaseModel):
    application_id: str
    applicant_id: str


class CreditAnalysisCompletedCommand(BaseModel):
    application_id: str
    agent_id: str
    session_id: str
    model_version: str
    confidence_score: float
    risk_tier: str
    recommended_limit_usd: int
    duration_ms: int
    correlation_id: str | None = None
    causation_id: str | None = None

class DecisionGeneratedCommand(BaseModel):
    application_id: str
    recommendation: str
    confidence_score: float
    correlation_id: str | None = None
    causation_id: str | None = None

# --- ADD THIS NEW CLASS ---
class StartAgentSession(BaseModel):
    session_id: str
    agent_type: str
    application_id: str
    model_version: str
    correlation_id: str | None = None
    causation_id: str | None = None

class RecordFraudScreening(BaseModel):
    application_id: str
    session_id: str
    fraud_score: float
    recommendation: str
    anomalies: list[dict]
    correlation_id: str | None = None
    causation_id: str | None = None

