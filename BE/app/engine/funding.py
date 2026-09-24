"""Funding-rate engine (DE_PKW_FUNDING_V1, docs/04 §2).

funding_rate = reference_rate + term_spread + asset_uncertainty_spread   (all in percentage points)
Returns a percentage (e.g. Decimal("3.50") meaning 3.50%).
"""
from __future__ import annotations

from decimal import Decimal

from app.core.policy import Policy
from app.core.types import ResidualConfidence


def compute_funding_rate(
    policy: Policy,
    *,
    reference_rate_pct: Decimal,
    term_months: int,
    residual_confidence: ResidualConfidence,
) -> Decimal:
    term_spread = policy.term_spread_pp(term_months)
    asset_spread = policy.asset_uncertainty_spread_pp(residual_confidence.value)
    return reference_rate_pct + term_spread + asset_spread
