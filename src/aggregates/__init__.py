# src/aggregates/__init__.py

from .document_package import DocumentPackage

# It's good practice to also import your other aggregates here.
# For example:
# from .loan_application import LoanApplication

__all__ = [
    "DocumentPackage",
    # "LoanApplication",
]
