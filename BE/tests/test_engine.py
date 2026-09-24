"""Phase-1 engine tests = the docs/04 §10 validation checklist + the persona flows (docs/03 §5).

No AI, no UI. Everything here is deterministic and must be repeatable.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.policy import load_policy
from app.core.types import RedKind, ResidualConfidence, RiskBand
from app.domain.entities import FinalOutcome, Readiness, WorkflowStatus
from app.engine import eligibility
from app.engine.calculator import calculate
from app.engine.exceptions_registry import SpecialPaymentTooHigh
from app.engine.margin import compute_commercial_margin
from app.engine.orchestrator import compute_final_outcome, run_pipeline
from app.engine.residual import compute_residual
from app.integration.base import AdapterMode, build_default_registry
from app.service.offer_factory import build_b2b_offer

POLICY = load_policy("DE_PKW_V1")


@pytest.fixture()
def registry():
    return build_default_registry(AdapterMode.MOCK)


def _offer(registry, **kw):
    defaults = dict(vehicle_key="bmw-x1-sdrive18i", register_number="HRB-1001",
                    term_months=36, annual_mileage_km=20000)
    defaults.update(kw)
    return build_b2b_offer(registry, **defaults)


# ── happy path ────────────────────────────────────────────────────────────────
def test_green_b2b_happy_path(registry):
    offer = run_pipeline(_offer(registry), registry, POLICY)
    assert offer.scoring.value.band is RiskBand.GREEN
    assert offer.calculation is not None
    cr = offer.calculation.value
    assert cr.monthly_gross_eur > 0
    assert cr.monthly_gross_eur > cr.monthly_net_eur  # VAT applied
    assert offer.workflow_status is WorkflowStatus.CALCULATED
    assert compute_final_outcome(offer) is FinalOutcome.READY
    assert offer.readiness is Readiness.COMPLETE


# ── determinism ─────────────────────────────────────────────────────────────────
def test_determinism(registry):
    a = run_pipeline(_offer(registry), registry, POLICY)
    b = run_pipeline(_offer(registry), registry, POLICY)
    assert a.calculation.value.monthly_gross_eur == b.calculation.value.monthly_gross_eur
    assert a.calculation.inputs_digest == b.calculation.inputs_digest
    assert a.scoring.value.mvp_risk_score == b.scoring.value.mvp_risk_score


# ── r == 0 branch (no divide-by-zero) ──────────────────────────────────────────
def test_zero_rate_branch():
    assessment = compute_residual(POLICY, list_price_net=Decimal("30000"), term_months=36,
                                  annual_mileage_km=15000).value
    env = calculate(POLICY, reference_rate_pct=Decimal("0"), funding_rate_pct=Decimal("0"),
                    commercial_margin_pct=Decimal("0"), assessment=assessment,
                    acquisition_price_net=Decimal("30000"), list_price_net=Decimal("30000"), financed_fees_eur=Decimal("0"),
                    discount_net_eur=Decimal("0"), special_payment_eur=Decimal("0"),
                    recurring_service_fee_eur=Decimal("0"), vat_pct=Decimal("19"),
                    term_months=36, annual_mileage_km=15000)
    cr = env.value
    expected = (cr.netcap_eur - cr.residual_value_amount_eur) / Decimal("36")
    assert abs(cr.base_lease_eur - expected) < Decimal("0.01")


# ── NetCap <= PV(residual) -> SpecialPaymentTooHigh (never negative rental) ──────
def test_special_payment_too_high_raises():
    assessment = compute_residual(POLICY, list_price_net=Decimal("30000"), term_months=36,
                                  annual_mileage_km=15000).value
    with pytest.raises(SpecialPaymentTooHigh):
        calculate(POLICY, reference_rate_pct=Decimal("3"), funding_rate_pct=Decimal("3.5"),
                  commercial_margin_pct=Decimal("1.75"), assessment=assessment,
                  acquisition_price_net=Decimal("30000"), list_price_net=Decimal("30000"), financed_fees_eur=Decimal("0"),
                  discount_net_eur=Decimal("0"), special_payment_eur=Decimal("25000"),
                  recurring_service_fee_eur=Decimal("0"), vat_pct=Decimal("19"),
                  term_months=36, annual_mileage_km=15000)


# ── term / mileage / special payment gates ──────────────────────────────────────
def test_term_out_of_range_blocks_pricing(registry):
    offer = run_pipeline(_offer(registry, term_months=72), registry, POLICY)
    assert any(e.code == "TERM_OUT_OF_RANGE" for e in offer.exceptions)
    assert offer.calculation is None


def test_mileage_out_of_range_blocks_pricing(registry):
    offer = run_pipeline(_offer(registry, annual_mileage_km=45000), registry, POLICY)
    assert any(e.code == "MILEAGE_OUT_OF_RANGE" for e in offer.exceptions)
    assert offer.calculation is None


def test_special_payment_over_30pct_blocks(registry):
    # 40% of 37800 = 15120
    offer = run_pipeline(_offer(registry, special_payment_eur=Decimal("15120")), registry, POLICY)
    assert any(e.code == "PRODUCT_INELIGIBLE" and e.detail.get("reason", "").startswith("special_payment")
               for e in offer.exceptions)
    assert compute_final_outcome(offer) is FinalOutcome.BLOCKED


def test_special_payment_20_to_30pct_is_yellow(registry):
    # 25% of 37800 = 9450
    offer = run_pipeline(_offer(registry, special_payment_eur=Decimal("9450")), registry, POLICY)
    assert any(e.code == "SPECIAL_PAYMENT_HIGH" for e in offer.exceptions)
    assert offer.calculation is not None  # soft -> still priced


# ── residual clamps + confidence ────────────────────────────────────────────────
def test_residual_clamped_and_confidence():
    env = compute_residual(POLICY, list_price_net=Decimal("40000"), term_months=60,
                           annual_mileage_km=40000)
    rv = env.value
    assert Decimal("20") <= rv.residual_value_pct <= Decimal("80")
    assert rv.residual_confidence is ResidualConfidence.LOW  # >35k km/yr


def test_max_allowed_term_context_caps():
    assert eligibility.max_allowed_term(POLICY, is_used=True, annual_mileage_km=15000,
                                        rv_confidence=ResidualConfidence.HIGH) == 48
    assert eligibility.max_allowed_term(POLICY, is_used=False, annual_mileage_km=35000,
                                        rv_confidence=ResidualConfidence.HIGH) == 48
    assert eligibility.max_allowed_term(POLICY, is_used=False, annual_mileage_km=15000,
                                        rv_confidence=ResidualConfidence.LOW) == 48
    assert eligibility.max_allowed_term(POLICY, is_used=False, annual_mileage_km=15000,
                                        rv_confidence=ResidualConfidence.HIGH) == 60


# ── margin bounds + RED not priced ──────────────────────────────────────────────
def test_margin_within_bounds_and_red_not_priced():
    for band in (RiskBand.GREEN, RiskBand.YELLOW):
        m = compute_commercial_margin(POLICY, band=band, price_eur=Decimal("40000"))
        assert m.priced
        assert POLICY.margin_floor_pp <= m.margin_pct <= POLICY.margin_cap_pp
    red = compute_commercial_margin(POLICY, band=RiskBand.RED, price_eur=Decimal("40000"))
    assert not red.priced


def test_high_value_over_100k_reviews_not_blocks(registry):
    offer = run_pipeline(_offer(registry, vehicle_key="porsche-taycan", register_number="HRB-1001"),
                         registry, POLICY)
    assert any(e.detail.get("reason") == "high_value_over_100k" for e in offer.exceptions)
    assert offer.calculation is not None  # priced (review, not block)
    assert compute_final_outcome(offer) is FinalOutcome.REQUIRES_ACTION


# ── scoring bands via personas ──────────────────────────────────────────────────
def test_yellow_new_company(registry):
    offer = run_pipeline(_offer(registry, register_number="HRB-2002"), registry, POLICY)
    assert offer.scoring.value.band is RiskBand.YELLOW
    assert any(e.code == "RISK_YELLOW" for e in offer.exceptions)
    assert offer.calculation is not None


def test_red_economic_overexposed(registry):
    offer = run_pipeline(_offer(registry, register_number="HRB-3003"), registry, POLICY)
    assert offer.scoring.value.band is RiskBand.RED
    assert offer.scoring.value.red_kind is RedKind.ECONOMIC
    assert offer.calculation is None
    assert compute_final_outcome(offer) is FinalOutcome.BLOCKED


def test_red_compliance_sanctions_blocks(registry):
    offer = run_pipeline(_offer(registry, register_number="HRB-4004"), registry, POLICY)
    assert offer.scoring.value.band is RiskBand.RED
    assert offer.scoring.value.red_kind is RedKind.COMPLIANCE
    assert "SANCTIONS_MATCH" in offer.scoring.value.hard_blocks
    assert offer.calculation is None
    assert compute_final_outcome(offer) is FinalOutcome.BLOCKED


def test_red_compliance_kyc_fail_blocks(registry):
    offer = run_pipeline(_offer(registry, register_number="HRB-5005"), registry, POLICY)
    assert "KYC_FAILED" in offer.scoring.value.hard_blocks
    assert compute_final_outcome(offer) is FinalOutcome.BLOCKED


# ── completeness gate ────────────────────────────────────────────────────────────
def test_missing_material_field_goes_context_required(registry):
    from app.core.types import ProvenanceValue
    offer = _offer(registry)
    offer.commercial.term_months = ProvenanceValue.missing()
    offer = run_pipeline(offer, registry, POLICY)
    assert offer.workflow_status is WorkflowStatus.CONTEXT_REQUIRED
    assert offer.readiness is Readiness.MISSING
    assert any(i.field == "commercial.term_months" for i in offer.issues)


# ── provenance present on every result ───────────────────────────────────────────
def test_results_carry_policy_provenance(registry):
    offer = run_pipeline(_offer(registry), registry, POLICY)
    assert offer.calculation.engine == "MVP_LEASE_CALC_V1"
    assert offer.calculation.policies["funding_policy"] == "DE_PKW_FUNDING_V1"
    assert offer.calculation.inputs_digest.startswith("sha256:")
    assert offer.assessment.engine == "DE_PKW_RV_V1"
    assert offer.scoring.engine == "DE_PKW_RISK_V1"
