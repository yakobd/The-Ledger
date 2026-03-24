# src/document_extraction.py

import random
from decimal import Decimal

def extract_financial_facts_from_file(file_path: str) -> dict:
    """
    A placeholder shim for the Week 3 document extraction logic.
    
    This function simulates the output of a real PDF/Excel extraction pipeline.
    It returns a dictionary matching the structure of the FinancialFacts model.
    """
    print(f"  [SHIM] Simulating extraction from: {file_path}")
    
    base_revenue = Decimal(random.randint(100000, 5000000))
    
    facts_dict = {
        "total_revenue": base_revenue,
        "net_income": base_revenue * Decimal(random.uniform(0.1, 0.2)),
        "total_assets": base_revenue * Decimal(random.uniform(1.5, 3.0)),
        "total_liabilities": base_revenue * Decimal(random.uniform(0.5, 1.5)),
        "currency": "USD",
        "fiscal_year_end": "2024-12-31"
    }
    
    print(f"  [SHIM] Simulated Net Income: {facts_dict['net_income']:.2f} USD")
    
    return facts_dict
