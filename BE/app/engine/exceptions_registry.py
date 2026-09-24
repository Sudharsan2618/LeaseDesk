"""Typed business-exception factories (docs/05 §4) + engine-level Python exceptions.

Business Exception_ objects are DATA attached to the Offer (they describe a condition and its
handling). Python exceptions here are CONTROL-FLOW signals raised by engine functions and caught
by the orchestrator, which then records the matching Exception_.
"""
from __future__ import annotations

from app.domain.entities import Exception_


# --- control-flow signals ---------------------------------------------------- #
class EngineSignal(Exception):
    code: str = "ENGINE_SIGNAL"


class SpecialPaymentTooHigh(EngineSignal):
    code = "SPECIAL_PAYMENT_TOO_HIGH"


class NotPriced(EngineSignal):
    """Raised when the band is RED (RED is not priced)."""
    code = "RISK_RED"


class CalculationFailed(EngineSignal):
    code = "CALCULATION_FAILED"


# --- business exception factories -------------------------------------------- #
def data_missing(field: str) -> Exception_:
    return Exception_(code="DATA_MISSING", severity="", blocking=True, override_allowed=False,
                      required_role="SALES", next_action="request_information", detail={"field": field})


def term_out_of_range(term: int, reason: str) -> Exception_:
    return Exception_(code="TERM_OUT_OF_RANGE", severity="YELLOW", blocking=True, override_allowed=True,
                      required_role="REVIEWER", next_action="correct", detail={"term": term, "reason": reason})


def mileage_out_of_range(km: int) -> Exception_:
    return Exception_(code="MILEAGE_OUT_OF_RANGE", severity="YELLOW", blocking=True, override_allowed=True,
                      required_role="REVIEWER", next_action="correct/review", detail={"annual_mileage_km": km})


def mileage_manual_review(km: int) -> Exception_:
    return Exception_(code="MILEAGE_OUT_OF_RANGE", severity="YELLOW", blocking=False, override_allowed=True,
                      required_role="REVIEWER", next_action="review", detail={"annual_mileage_km": km, "reason": "below_minimum"})


def special_payment_high(pct: str) -> Exception_:
    return Exception_(code="SPECIAL_PAYMENT_HIGH", severity="YELLOW", blocking=False, override_allowed=True,
                      required_role="REVIEWER", next_action="review", detail={"pct": pct})


def special_payment_block(pct: str) -> Exception_:
    return Exception_(code="PRODUCT_INELIGIBLE", severity="RED", blocking=True, override_allowed=False,
                      next_action="block", detail={"reason": "special_payment_over_30pct", "pct": pct})


def residual_low_confidence() -> Exception_:
    return Exception_(code="RESIDUAL_LOW_CONFIDENCE", severity="YELLOW", blocking=False, override_allowed=True,
                      required_role="REVIEWER", next_action="human_review")


def product_ineligible(reason: str, blocking: bool = True) -> Exception_:
    return Exception_(code="PRODUCT_INELIGIBLE", severity="RED" if blocking else "YELLOW",
                      blocking=blocking, override_allowed=not blocking,
                      required_role=None if blocking else "APPROVER",
                      next_action="block" if blocking else "review", detail={"reason": reason})


def high_value_review(price: str) -> Exception_:
    return Exception_(code="PRODUCT_INELIGIBLE", severity="YELLOW", blocking=False, override_allowed=True,
                      required_role="APPROVER", next_action="review",
                      detail={"reason": "high_value_over_100k", "price": price})


def risk_yellow() -> Exception_:
    return Exception_(code="RISK_YELLOW", severity="YELLOW", blocking=False, override_allowed=True,
                      required_role="APPROVER", next_action="human_review")


def scoring_manual_review(reasons: list[str] | None = None) -> Exception_:
    """Scoring pattern is MANUAL (spec §3.11): parameters fall outside the automatic envelope, so
    the outcome must be reviewed by a human (Requires Action) before it can proceed. Non-blocking
    advisory — it routes to the human-review gate, it does not hard-block."""
    return Exception_(code="SCORING_MANUAL_REVIEW", severity="YELLOW", blocking=False,
                      override_allowed=True, required_role="APPROVER", next_action="human_review",
                      detail={"reasons": reasons or []})


def assessment_unavailable(service: str, asset_category: str) -> Exception_:
    """A required §3.7 asset-assessment dependency is unavailable ⇒ progression is prevented
    (FR-22). Blocking and not override-allowed: the assessment must be obtained (retry) before the
    offer can be priced/validated."""
    return Exception_(code="ASSESSMENT_UNAVAILABLE", severity="RED", blocking=True,
                      override_allowed=False, next_action="retry/await_assessment",
                      detail={"service": service, "asset_category": asset_category})


def risk_red(kind: str) -> Exception_:
    # economic RED is reworkable (loop); compliance RED is a hard block
    if kind == "COMPLIANCE":
        return Exception_(code="RISK_RED", severity="RED", blocking=True, override_allowed=False,
                          next_action="block", detail={"kind": kind})
    return Exception_(code="RISK_RED", severity="RED", blocking=True, override_allowed=False,
                      next_action="suggest_alternatives", detail={"kind": kind})


def sanctions_match() -> Exception_:
    return Exception_(code="SANCTIONS_MATCH", severity="RED", blocking=True, override_allowed=False,
                      next_action="block")


def kyc_failed() -> Exception_:
    return Exception_(code="KYC_FAILED", severity="RED", blocking=True, override_allowed=False,
                      next_action="block")


def calculation_failed(reason: str) -> Exception_:
    return Exception_(code="CALCULATION_FAILED", severity="RED", blocking=True, override_allowed=False,
                      next_action="block/retry", detail={"reason": reason})


def external_unavailable(service: str) -> Exception_:
    return Exception_(code="EXTERNAL_SERVICE_UNAVAILABLE", severity="", blocking=True, override_allowed=False,
                      next_action="retry/mock-fallback", detail={"service": service})
