# src/document_extraction.py

import random
from decimal import Decimal

def extract_financial_facts_from_file(file_path: str) -> dict:
    """
    This is a placeholder SHIM. It ignores the file path and returns
    realistic-looking fake data for testing the agent pipeline.
    """
    print(f"  [SHIM] Simulating extraction for: {file_path}")
    
    base_revenue = Decimal(random.randint(100000, 5000000))
    
    return {
        "total_revenue": base_revenue,
        "net_income": base_revenue * Decimal(random.uniform(0.1, 0.2)),
        "total_assets": base_revenue * Decimal(random.uniform(1.5, 3.0)),
        "total_liabilities": base_revenue * Decimal(random.uniform(0.5, 1.5)),
        "total_equity": base_revenue * Decimal(random.uniform(0.5, 1.5)),
        "currency": "USD",
        "fiscal_year_end": "2024-12-31"
    }
