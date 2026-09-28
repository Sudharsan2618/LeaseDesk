"""Understand: natural-language leasing request -> structured ExtractedIntent (INFERRED)."""
from __future__ import annotations

from typing import Optional

from app.agent import llm
from app.agent.schemas import ExtractedIntent

_SYSTEM = (
    "You are an intake assistant for a German B2B leasing workbench. "
    "Extract the leasing request into the structured schema. Handle ANY phrasing. "
    "Put concrete asset attributes the user mentions (seats, fuel, body, transmission, power, colour) "
    "into `asset_filters` as string values. Put budgets or caps into `constraints` "
    "(kind='budget' or 'monthly_cap'), keeping the currency exactly as written and setting basis to "
    "'annual' for annual/per-year budgets, 'monthly' for per-month fleet budgets, "
    "'per_vehicle' for per-vehicle monthly budgets, 'total' for whole-contract budgets, "
    "'acquisition' for purchase-price caps, and 'unknown' only when the basis is not stated. "
    "Whenever something is unclear — the budget's currency or basis, which product/business line, an "
    "under-specified quantity — add an entry to `ambiguities` instead of guessing. "
    "Do NOT invent values you are not told; leave unknown fields null. "
    "You never price, score, approve, or pick a specific catalogue item — you only structure the request."
)


def understand(nl_text: str) -> Optional[ExtractedIntent]:
    """Return an ExtractedIntent, or None when no LLM is configured (caller then clarifies)."""
    if not llm.llm_available() or not nl_text.strip():
        return None
    return llm.extract_json(_SYSTEM, nl_text, ExtractedIntent)
