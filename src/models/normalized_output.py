from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal, InvalidOperation

from typing import Any, List, Optional, Dict

from src.models.events import FinancialFacts

class BBox(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    page_number: int

class DocumentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str
    origin_type: str
    layout_complexity: str
    selected_strategy: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    estimated_cost: float
    estimated_chars: int = 0
    pages: int
    language: str = "en"
    domain_hint: str = "financial"
    is_form_fillable: bool = False
    domain_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

class PageIndexNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    summary: str = ""
    page_start: int
    page_end: int
    children: List["PageIndexNode"] = Field(default_factory=list)

class LDU(BaseModel):
    model_config = ConfigDict(extra="forbid")
    uid: str
    content: str
    chunk_type: str
    content_hash: str
    page_refs: List[int]
    bounding_box: List[float]
    parent_section: Optional[str] = None
    token_count: int = Field(default=0, ge=0)
    child_chunks: List[str] = Field(default_factory=list)
    chunk_relationships: List[Any] = Field(default_factory=list)
    chunks: List[Any] = Field(default_factory=list)

class NormalizedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str
    doc_id: str
    profile: DocumentProfile
    ldus: List[LDU]
    index: List[PageIndexNode]
    metadata: Dict[str, Any]


def adapt_normalized_output_to_financial_facts(normalized_output: NormalizedOutput) -> FinancialFacts:
    lbus_raw = getattr(normalized_output, "lbus", {})
    provenance_raw = getattr(normalized_output, "provenance", {})

    lbus: Dict[str, Any] = lbus_raw if isinstance(lbus_raw, dict) else {}
    provenance: Dict[str, Any]
    if isinstance(provenance_raw, dict):
        provenance = provenance_raw
    else:
        metadata_raw = getattr(normalized_output, "metadata", {})
        provenance = metadata_raw if isinstance(metadata_raw, dict) else {}

    def _first(keys: List[str], *sources: Dict[str, Any]) -> Any:
        for source in sources:
            for key in keys:
                value = source.get(key)
                if value is not None:
                    return value
        return None

    def _to_decimal(value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            cleaned = value.replace(",", "").replace("$", "").strip()
            if not cleaned:
                return None
            try:
                return Decimal(cleaned)
            except InvalidOperation:
                return None
        return None

    def _to_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _to_bool(value: Any, default: bool | None = None) -> bool | None:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
        return default

    def _to_dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _to_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v) for v in value]
        return [str(value)]

    return FinancialFacts(
        total_revenue=_to_decimal(_first(["total_revenue", "revenue"], lbus, provenance)),
        gross_profit=_to_decimal(_first(["gross_profit"], lbus, provenance)),
        operating_expenses=_to_decimal(_first(["operating_expenses", "opex"], lbus, provenance)),
        operating_income=_to_decimal(_first(["operating_income", "ebit"], lbus, provenance)),
        ebitda=_to_decimal(_first(["ebitda"], lbus, provenance)),
        depreciation_amortization=_to_decimal(_first(["depreciation_amortization", "depreciation_and_amortization"], lbus, provenance)),
        interest_expense=_to_decimal(_first(["interest_expense"], lbus, provenance)),
        income_before_tax=_to_decimal(_first(["income_before_tax", "pretax_income"], lbus, provenance)),
        tax_expense=_to_decimal(_first(["tax_expense", "income_tax_expense"], lbus, provenance)),
        net_income=_to_decimal(_first(["net_income"], lbus, provenance)),
        total_assets=_to_decimal(_first(["total_assets"], lbus, provenance)),
        current_assets=_to_decimal(_first(["current_assets"], lbus, provenance)),
        cash_and_equivalents=_to_decimal(_first(["cash_and_equivalents", "cash"], lbus, provenance)),
        accounts_receivable=_to_decimal(_first(["accounts_receivable", "receivables"], lbus, provenance)),
        inventory=_to_decimal(_first(["inventory"], lbus, provenance)),
        total_liabilities=_to_decimal(_first(["total_liabilities"], lbus, provenance)),
        current_liabilities=_to_decimal(_first(["current_liabilities"], lbus, provenance)),
        long_term_debt=_to_decimal(_first(["long_term_debt"], lbus, provenance)),
        total_equity=_to_decimal(_first(["total_equity", "shareholders_equity", "equity"], lbus, provenance)),
        operating_cash_flow=_to_decimal(_first(["operating_cash_flow"], lbus, provenance)),
        investing_cash_flow=_to_decimal(_first(["investing_cash_flow"], lbus, provenance)),
        financing_cash_flow=_to_decimal(_first(["financing_cash_flow"], lbus, provenance)),
        free_cash_flow=_to_decimal(_first(["free_cash_flow"], lbus, provenance)),
        debt_to_equity=_to_float(_first(["debt_to_equity"], lbus, provenance)),
        current_ratio=_to_float(_first(["current_ratio"], lbus, provenance)),
        debt_to_ebitda=_to_float(_first(["debt_to_ebitda"], lbus, provenance)),
        interest_coverage=_to_float(_first(["interest_coverage"], lbus, provenance)),
        gross_margin=_to_float(_first(["gross_margin"], lbus, provenance)),
        net_margin=_to_float(_first(["net_margin"], lbus, provenance)),
        fiscal_year_end=_first(["fiscal_year_end"], provenance, lbus),
        currency=_first(["currency"], provenance, lbus) or "USD",
        gaap_compliant=_to_bool(_first(["gaap_compliant"], provenance, lbus), default=True),
        field_confidence={k: float(v) for k, v in _to_dict(_first(["field_confidence"], provenance, lbus)).items()},
        page_references={k: str(v) for k, v in _to_dict(_first(["page_references"], provenance, lbus)).items()},
        extraction_notes=_to_list(_first(["extraction_notes", "notes"], provenance, lbus)),
        balance_sheet_balances=_to_bool(_first(["balance_sheet_balances"], provenance, lbus), default=None),
        balance_discrepancy_usd=_to_decimal(_first(["balance_discrepancy_usd"], provenance, lbus)),
    )