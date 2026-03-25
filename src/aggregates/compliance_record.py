# src/aggregates/compliance_record.py

from .base import BaseAggregate
from src.models.events import (
    ComplianceCheckInitiated,
    ComplianceRulePassed,
    ComplianceRuleFailed,
    ComplianceCheckCompleted,
    BaseEvent
)

class ComplianceRecord(BaseAggregate):
    def __init__(self):
        super().__init__()
        self.rules_passed = 0
        self.rules_failed = 0
        self.has_hard_block = False

    # --- State-Changing Methods ---
    
    def _apply_ComplianceCheckInitiated(self, event: BaseEvent):
        pass

    def _apply_ComplianceRulePassed(self, event: BaseEvent):
        self.rules_passed += 1
    
    def _apply_ComplianceRuleFailed(self, event: BaseEvent):
        # --- THIS IS THE FIX ---
        self.rules_failed += 1
        if hasattr(event, 'payload'):
            is_hard_block = event.payload.get("is_hard_block")
        else:
            is_hard_block = event.is_hard_block
            
        if is_hard_block:
            self.has_hard_block = True
            
    def _apply_ComplianceCheckCompleted(self, event: BaseEvent):
        pass

    # --- Command Methods (Unchanged) ---
    def initiate_check(self, session_id: str, regulations: list):
        self.record(
            ComplianceCheckInitiated(
                application_id=self.stream_id.replace("compliance-", ""),
                session_id=session_id,
                regulation_set_version="v1.0",
                rules_to_evaluate=regulations,
                initiated_at=self._now()
            )
        )
        return self

    def record_rule_pass(self, session_id: str, rule_id: str, rule_name: str):
        self.record(
            ComplianceRulePassed(
                application_id=self.stream_id.replace("compliance-", ""),
                session_id=session_id,
                rule_id=rule_id,
                rule_name=rule_name,
                rule_version="v1.0",
                evidence_hash="dummy_hash",
                evaluation_notes="Rule passed.",
                evaluated_at=self._now()
            )
        )
        return self

    def record_rule_fail(self, session_id: str, rule_id: str, rule_name: str, reason: str, is_hard_block: bool):
        self.record(
            ComplianceRuleFailed(
                application_id=self.stream_id.replace("compliance-", ""),
                session_id=session_id,
                rule_id=rule_id,
                rule_name=rule_name,
                rule_version="v1.0",
                failure_reason=reason,
                is_hard_block=is_hard_block,
                remediation_available=not is_hard_block,
                evidence_hash="dummy_hash",
                evaluated_at=self._now()
            )
        )
        return self

    def complete_check(self, session_id: str):
        verdict = "BLOCKED" if self.has_hard_block else "CLEAR"
        self.record(
            ComplianceCheckCompleted(
                application_id=self.stream_id.replace("compliance-", ""),
                session_id=session_id,
                rules_evaluated=self.rules_passed + self.rules_failed,
                rules_passed=self.rules_passed,
                rules_failed=self.rules_failed,
                rules_noted=0,
                has_hard_block=self.has_hard_block,
                overall_verdict=verdict,
                completed_at=self._now()
            )
        )
        return self
