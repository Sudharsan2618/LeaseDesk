"""Deterministic B2B pipeline (docs/04 §1, docs/06). NO AI, NO UI.

Order (B2B has no scoring<->margin cycle because B2B scoring does not use the monthly payment):
  assemble adapters -> completeness -> residual -> eligibility gates -> scoring
  -> (GREEN/YELLOW) funding -> margin -> calculate ; (RED) no pricing
  -> readiness + provisional final outcome.

Human review/approval is a separate gate (later phase); this module computes everything up to and
including the data/calc validation, and a provisional final outcome ignoring the review gate.
"""
from __future__ import annotations

from decimal import Decimal

from app.core.policy import Policy, load_policy
from app.core.types import AssetAssessmentStatus, CustomerType, RiskBand, ScoringPattern
from app.domain.entities import (
    Exception_,
    FinalOutcome,
    Offer,
    Readiness,
    ValidationIssue,
    WorkflowStatus,
)
from app.engine import eligibility, exceptions_registry as ex
from app.engine.asset_assessment import run_asset_assessment
from app.engine.calculator import calculate
from app.engine.funding import compute_funding_rate
from app.engine.margin import compute_commercial_margin
from app.engine.residual import compute_residual
from app.engine.risk import score_b2b
from app.integration.base import AdapterRegistry, ExternalServiceUnavailable


# --------------------------------------------------------------------------- #
# Completeness                                                                 #
# --------------------------------------------------------------------------- #
def _completeness_issues(offer: Offer) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    c = offer.commercial
    v = offer.vehicle

    def need(pv, field: str):
        if not pv.is_consumable:
            issues.append(ValidationIssue(field=field, type=pv.status.value if pv.value is None else "REQUIRES_CONFIRMATION",
                                          blocking=True, why="material field not established/confirmed",
                                          what_must_happen="provide/confirm value", who_acts="SALES"))

    need(c.term_months, "commercial.term_months")
    need(c.annual_mileage_km, "commercial.annual_mileage_km")
    need(v.acquisition_price_net, "vehicle.acquisition_price_net")
    need(v.list_price_net, "vehicle.list_price_net")
    need(v.vehicle_category, "vehicle.vehicle_category")
    return issues


# --------------------------------------------------------------------------- #
# Adapter assembly (customer context)                                          #
# --------------------------------------------------------------------------- #
def assemble_customer(offer: Offer, registry: AdapterRegistry, *, register_number: str,
                      requested_exposure_eur: Decimal) -> list[Exception_]:
    exceptions: list[Exception_] = []
    try:
        offer.customer.sanctions = registry.get("SANCTIONS").fetch(
            {"register_number": register_number, "names": []})
        offer.customer.kyc = registry.get("KYC").fetch({"register_number": register_number})
        offer.customer.credit = registry.get("CREDIT").fetch(
            {"register_number": register_number, "requested_exposure_eur": requested_exposure_eur})
    except ExternalServiceUnavailable as e:
        exceptions.append(ex.external_unavailable(str(e)))
    return exceptions


# --------------------------------------------------------------------------- #
# Pipeline                                                                     #
# --------------------------------------------------------------------------- #
def run_pipeline(offer: Offer, registry: AdapterRegistry, policy: Policy | None = None) -> Offer:
    policy = policy or load_policy(offer.policy_version)
    offer.issues = []
    offer.exceptions = []

    # 1) completeness
    offer.issues = _completeness_issues(offer)
    if any(i.blocking for i in offer.issues):
        offer.readiness = Readiness.MISSING
        offer.workflow_status = WorkflowStatus.CONTEXT_REQUIRED
        return offer

    term = offer.commercial.term_months.value
    mileage = offer.commercial.annual_mileage_km.value
    quantity = int(offer.commercial.quantity.value or 1)
    svc_maint = bool(offer.commercial.service_maintenance.value)
    svc_tyres = bool(offer.commercial.service_tyres.value)
    insurance = bool(offer.commercial.insurance.value)
    special_payment = (offer.commercial.special_payment_eur.value or Decimal("0"))
    service_fee = (offer.commercial.recurring_service_fee_eur.value or Decimal("0"))
    financed_fees = (offer.commercial.financed_fees_eur.value or Decimal("0"))
    acq = offer.vehicle.acquisition_price_net.value
    list_price = offer.vehicle.list_price_net.value
    discount = (offer.vehicle.discount_net.value or Decimal("0"))
    category = offer.vehicle.vehicle_category.value
    is_used = offer.vehicle.is_used
    age_years = _vehicle_age_years(offer)

    # 1b) assemble customer context (sanctions/kyc/credit) if not already present
    if offer.customer.credit is None or offer.customer.kyc is None or offer.customer.sanctions is None:
        reg = offer.customer.register_number.value
        exposure_hint = max(Decimal("0"), (acq or Decimal("0")) - special_payment)
        offer.exceptions.extend(
            assemble_customer(offer, registry, register_number=reg,
                              requested_exposure_eur=exposure_hint))

    # 2) residual (needed for funding spread + term cap + confidence)
    assessment = compute_residual(
        policy, list_price_net=list_price, term_months=term, annual_mileage_km=mileage,
        is_used=is_used, vehicle_age_years=age_years, data_complete=True,
    )
    offer.assessment = assessment
    rv_conf = assessment.value.residual_confidence
    if rv_conf.value == "LOW":
        offer.exceptions.append(ex.residual_low_confidence())

    # 3) eligibility gates
    for chk in (
        eligibility.check_term(policy, term_months=term, is_used=is_used,
                               annual_mileage_km=mileage, rv_confidence=rv_conf),
        eligibility.check_mileage(policy, annual_mileage_km=mileage),
        eligibility.check_quantity(policy, quantity=quantity),
        eligibility.check_special_payment(policy, special_payment_eur=special_payment,
                                          acquisition_price_net=acq),
    ):
        if chk is not None:
            offer.exceptions.append(chk)
    offer.exceptions.extend(eligibility.check_vehicle(
        policy, category=category, price_eur=acq, vehicle_age_years=age_years, term_months=term))

    # 3b) asset assessment (§3.7) — a DISTINCT outcome; an unavailable required dependency blocks.
    assessment_outcome = run_asset_assessment(
        policy, registry, asset_category_key=offer.asset_category_key.value)
    offer.asset_assessment = assessment_outcome
    if assessment_outcome.value.status is AssetAssessmentStatus.UNAVAILABLE:
        offer.exceptions.append(ex.assessment_unavailable(
            assessment_outcome.value.service or "ASSET_ASSESSMENT",
            assessment_outcome.value.asset_category))

    # 4) scoring (B2B) — exposure scales with fleet size
    exposure = max(Decimal("0"), acq - special_payment) * Decimal(quantity)
    if offer.customer.credit is None or offer.customer.kyc is None or offer.customer.sanctions is None:
        offer.exceptions.append(ex.calculation_failed("customer_context_unavailable"))
        offer.scoring = None
        _finalise(offer)
        return offer

    scoring = score_b2b(
        policy, credit=offer.customer.credit, sanctions=offer.customer.sanctions,
        kyc=offer.customer.kyc, exposure_eur=exposure,
        quantity=quantity, acquisition_price_eur=acq,
    )
    offer.scoring = scoring
    band = scoring.value.band
    if band is RiskBand.YELLOW:
        offer.exceptions.append(ex.risk_yellow())
    elif band is RiskBand.RED:
        offer.exceptions.append(ex.risk_red(scoring.value.red_kind.value))
    # Manual scoring pattern (§3.11): parameters outside the automatic envelope -> human review.
    if scoring.value.pattern is ScoringPattern.MANUAL:
        offer.exceptions.append(ex.scoring_manual_review(scoring.value.manual_reasons))

    # 5) pricing (only GREEN/YELLOW, and only when nothing blocking is open; RED is not priced).
    #    Soft advisories (RISK_YELLOW, high-value review, RESIDUAL_LOW_CONFIDENCE) still price.
    if band is not RiskBand.RED and not any(e.blocking for e in offer.exceptions):
        try:
            ref_rate = registry.get("REFERENCE_RATE").fetch({}).value
            vat = registry.get("VAT").fetch({}).value
            funding_rate = compute_funding_rate(
                policy, reference_rate_pct=ref_rate, term_months=term, residual_confidence=rv_conf)
            margin = compute_commercial_margin(policy, band=band, price_eur=acq)
            if not margin.priced:
                offer.exceptions.append(ex.risk_red("ECONOMIC"))
            else:
                offer.calculation = calculate(
                    policy, reference_rate_pct=ref_rate, funding_rate_pct=funding_rate,
                    commercial_margin_pct=margin.margin_pct, assessment=assessment.value,
                    acquisition_price_net=acq, list_price_net=list_price,
                    financed_fees_eur=financed_fees, discount_net_eur=discount,
                    special_payment_eur=special_payment, recurring_service_fee_eur=service_fee,
                    vat_pct=vat, term_months=term, annual_mileage_km=mileage,
                    quantity=quantity, service_maintenance=svc_maint,
                    service_tyres=svc_tyres, insurance=insurance,
                )
        except ex.SpecialPaymentTooHigh as e:
            offer.exceptions.append(Exception_(code="SPECIAL_PAYMENT_TOO_HIGH", severity="RED",
                                               blocking=True, override_allowed=False,
                                               next_action="reduce_special_payment", detail={"msg": str(e)}))
        except ExternalServiceUnavailable as e:
            offer.exceptions.append(ex.external_unavailable(str(e)))

    _finalise(offer)
    return offer


# --------------------------------------------------------------------------- #
# Finalisation                                                                 #
# --------------------------------------------------------------------------- #
def _finalise(offer: Offer) -> None:
    outcome = compute_final_outcome(offer)
    offer.readiness = _readiness_from(offer, outcome)
    if outcome is FinalOutcome.BLOCKED:
        offer.workflow_status = WorkflowStatus.FINAL_VALIDATION
    elif offer.calculation is not None:
        offer.workflow_status = WorkflowStatus.CALCULATED
    else:
        offer.workflow_status = WorkflowStatus.VALIDATION_REQUIRED


def compute_final_outcome(offer: Offer) -> FinalOutcome:
    """Provisional final outcome from data/calc/scoring (ignores the human-review gate).
    A generated offer is READY by definition (a human already accepted any soft issues)."""
    if offer.workflow_status is WorkflowStatus.OFFER_GENERATED:
        return FinalOutcome.READY
    if _has_blocking_hard(offer.exceptions):
        return FinalOutcome.BLOCKED
    soft = [e for e in offer.exceptions if not e.blocking or e.override_allowed]
    if soft or any(i.blocking for i in offer.issues) or offer.calculation is None:
        return FinalOutcome.REQUIRES_ACTION
    return FinalOutcome.READY


def _has_blocking_hard(exceptions: list[Exception_]) -> bool:
    return any(e.blocking and not e.override_allowed for e in exceptions)


def _readiness_from(offer: Offer, outcome: FinalOutcome) -> Readiness:
    if any(i.type == "INVALID" for i in offer.issues):
        return Readiness.INVALID
    if any(i.type == "INCONSISTENT" for i in offer.issues):
        return Readiness.INCONSISTENT
    if any(i.type == "MISSING" for i in offer.issues):
        return Readiness.MISSING
    if outcome is FinalOutcome.READY:
        return Readiness.COMPLETE
    return Readiness.REQUIRES_CONFIRMATION


def _vehicle_age_years(offer: Offer) -> int:
    if not offer.vehicle.is_used or offer.vehicle.registration_date is None:
        return 0
    from datetime import date
    today = date.today()
    return max(0, (today - offer.vehicle.registration_date).days // 365)
