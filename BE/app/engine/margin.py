"""Commercial-margin engine (DE_PKW_MARGIN_V1, docs/04 §3).

commercial_margin = base_margin + risk_adjustment(band) + deal_size_adjustment(price),
clamped to [floor, cap]. RED is NOT priced. Deals > 100k flag manual review (numeric deal
adjustment treated as 0 for the computation, review surfaced as an exception elsewhere).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.core.policy import Policy
from app.core.types import RiskBand


@dataclass
class MarginOutcome:
    priced: bool
    margin_pct: Decimal = Decimal("0")   # percentage points; only meaningful when priced
    manual_review: bool = False
    reasons: list[str] = field(default_factory=list)


def compute_commercial_margin(policy: Policy, *, band: RiskBand, price_eur: Decimal) -> MarginOutcome:
    risk_adj = policy.risk_adjustment_pp(band.value)
    if risk_adj is None:  # RED -> not priced
        return MarginOutcome(priced=False, reasons=["RED_NOT_PRICED"])

    deal_adj_raw = policy.deal_size_adjustment_pp(price_eur)
    manual_review = False
    if isinstance(deal_adj_raw, str):  # "MANUAL_REVIEW" for > 100k
        deal_adj = Decimal("0")
        manual_review = True
    else:
        deal_adj = deal_adj_raw

    raw = policy.margin_base_pp + risk_adj + deal_adj
    clamped = max(policy.margin_floor_pp, min(policy.margin_cap_pp, raw))
    reasons = []
    if clamped != raw:
        reasons.append("MARGIN_CLAMPED")
    if manual_review:
        reasons.append("HIGH_VALUE_MANUAL_REVIEW")
    return MarginOutcome(priced=True, margin_pct=clamped, manual_review=manual_review, reasons=reasons)
