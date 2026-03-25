# src/aggregates/__init__.py
from .base import BaseAggregate
from .document_package import DocumentPackage
from .fraud_screening import FraudScreening
from .compliance_record import ComplianceRecord
from .loan_application import LoanApplicationAggregate
from .audit_ledger import AuditLedger

# It's good practice to also import your other aggregates here.
# For example:
# from .loan_application import LoanApplication

__all__ = [
    "BaseAggregate",
    "DocumentPackage",
    "FraudScreening",
    "ComplianceRecord",
    "LoanApplicationAggregate",
    "AuditLedger",
    
]