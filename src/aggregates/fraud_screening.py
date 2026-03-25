# src/aggregates/fraud_screening.py

from .base import BaseAggregate
from src.models.events import (
    FraudScreeningInitiated,
    FraudAnomalyDetected,
    FraudScreeningCompleted,
    BaseEvent
)

class FraudScreening(BaseAggregate):
    def __init__(self):
        super().__init__()
        self.anomalies_found = 0
        self.risk_level = "UNKNOWN"

    # --- State-Changing Methods ---
    
    def _apply_FraudScreeningInitiated(self, event: BaseEvent):
        pass # Not much state to set on initiation

    def _apply_FraudAnomalyDetected(self, event: BaseEvent):
        # This method is now bilingual
        self.anomalies_found += 1
    
    def _apply_FraudScreeningCompleted(self, event: BaseEvent):
        # This method is now bilingual
        if hasattr(event, 'payload'):
            self.risk_level = event.payload.get("risk_level")
        else:
            self.risk_level = event.risk_level

    # --- Command Methods (Unchanged) ---
    def initiate_screening(self, session_id: str, model_version: str):
        self.record(
            FraudScreeningInitiated(
                application_id=self.stream_id.replace("fraud-", ""),
                session_id=session_id,
                screening_model_version=model_version,
                initiated_at=self._now()
            )
        )
        return self
    
    def record_anomaly(self, anomaly_type: str, description: str, severity: str):
        self.record(
            FraudAnomalyDetected(
                application_id=self.stream_id.replace("fraud-", ""),
                session_id="dummy_session", # Placeholder
                anomaly={
                    "anomaly_type": anomaly_type,
                    "description": description,
                    "severity": severity,
                    "evidence": "Rule-based detection on financial facts.",
                    "affected_fields": [] # Could be improved to list fields
                },
                detected_at=self._now()
            )
        )
        return self

    def complete_screening(self, session_id: str, fraud_score: float, recommendation: str):
        risk_level = "HIGH" if fraud_score > 0.75 else "MEDIUM" if fraud_score > 0.4 else "LOW"
        
        self.record(
            FraudScreeningCompleted(
                application_id=self.stream_id.replace("fraud-", ""),
                session_id=session_id,
                fraud_score=fraud_score,
                risk_level=risk_level,
                anomalies_found=self.anomalies_found,
                recommendation=recommendation,
                screening_model_version="rule_based_v1", # Placeholder
                input_data_hash="dummy_hash", # Placeholder
                completed_at=self._now()
            )
        )
        return self
