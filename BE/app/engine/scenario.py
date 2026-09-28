"""Scenario engine: price the exact customer-requested commercial terms.

Every scenario re-runs residual -> funding -> margin -> calculate. The requested term, mileage,
quantity, payment and service bundle are held fixed: alternative terms or add-ons are not silently
introduced as if they were part of the request.

Assumes run_pipeline has already assembled the customer context (credit/kyc/sanctions) and produced
a non-RED band. RED offers are blocked and get no scenarios.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.core.policy import Policy, load_policy
from app.core.types import RiskBand
from app.domain.entities import Offer, Scenario
from app.engine import eligibility
from app.engine.calculator import calculate
from app.engine.exceptions_registry import SpecialPaymentTooHigh
from app.engine.funding import compute_funding_rate
from app.engine.margin import compute_commercial_margin
from app.engine.residual import compute_residual
from app.engine.risk import score_b2b
from app.integration.base import AdapterRegistry


def _price_scenario(
    offer: Offer, policy: Policy, ref_rate, vat, *,
    term: int, maint: bool, tyres: bool, insurance: bool, label: str,
) -> Scenario | None:
    """Price ONE scenario for a (term, service-bundle) combination. Returns None if the term is not a
    valid alternative or cannot be priced. Vehicle / mileage / special payment / quantity are fixed to
    the offer (the customer's choices)."""
    mileage = offer.commercial.annual_mileage_km.value
    special = offer.commercial.special_payment_eur.value or Decimal("0")
    service_fee = offer.commercial.recurring_service_fee_eur.value or Decimal("0")
    financed_fees = offer.commercial.financed_fees_eur.value or Decimal("0")
    quantity = int(offer.commercial.quantity.value or 1)
    acq = offer.vehicle.acquisition_price_net.value
    list_price = offer.vehicle.list_price_net.value
    discount = offer.vehicle.discount_net.value or Decimal("0")
    is_used = offer.vehicle.is_used

    assessment = compute_residual(
        policy, list_price_net=list_price, term_months=term, annual_mileage_km=mileage,
        is_used=is_used, vehicle_age_years=0, data_complete=True)
    rv_conf = assessment.value.residual_confidence
    if eligibility.check_term(policy, term_months=term, is_used=is_used,
                              annual_mileage_km=mileage, rv_confidence=rv_conf) is not None:
        return None

    scoring = offer.scoring                      # band is constant for term/service variation
    band = scoring.value.band
    funding = compute_funding_rate(policy, reference_rate_pct=ref_rate, term_months=term,
                                   residual_confidence=rv_conf)
    margin = compute_commercial_margin(policy, band=band, price_eur=acq)
    if not margin.priced:
        return None
    try:
        calc = calculate(
            policy, reference_rate_pct=ref_rate, funding_rate_pct=funding,
            commercial_margin_pct=margin.margin_pct, assessment=assessment.value,
            acquisition_price_net=acq, list_price_net=list_price,
            financed_fees_eur=financed_fees, discount_net_eur=discount,
            special_payment_eur=special, recurring_service_fee_eur=service_fee, vat_pct=vat,
            term_months=term, annual_mileage_km=mileage, quantity=quantity,
            service_maintenance=maint, service_tyres=tyres, insurance=insurance)
    except SpecialPaymentTooHigh:
        return None

    return Scenario(
        label=label, term_months=term, annual_mileage_km=mileage, special_payment_eur=special,
        service_maintenance=maint, service_tyres=tyres, insurance=insurance,
        calculation=calc, assessment=assessment, scoring=scoring)


def generate_scenarios(
    offer: Offer,
    registry: AdapterRegistry,
    policy: Policy | None = None,
    *,
    term_options: Optional[list[int]] = None,
    max_scenarios: int = 4,
) -> list[Scenario]:
    """Price one scenario using the request as stated; edits trigger a new price run."""
    policy = policy or load_policy(offer.policy_version)

    # only meaningful for a priced (GREEN/YELLOW) offer
    if offer.scoring is None or offer.scoring.value.band is RiskBand.RED:
        offer.scenarios = []
        return []

    ref_rate = registry.get("REFERENCE_RATE").fetch({}).value
    vat = registry.get("VAT").fetch({}).value

    base_term = int(offer.commercial.term_months.value
                    or (policy.term_preferred[0] if policy.term_preferred else 36))
    maint0 = bool(offer.commercial.service_maintenance.value)
    tyres0 = bool(offer.commercial.service_tyres.value)
    ins0 = bool(offer.commercial.insurance.value)
    scenario = _price_scenario(offer, policy, ref_rate, vat, term=base_term,
                               maint=maint0, tyres=tyres0, insurance=ins0,
                               label=f"{base_term} mo")
    offer.scenarios = [scenario] if scenario else []
    # A fresh scenario set has new ids — a selection from a previous pass (e.g. before an Adjust) now
    # dangles and would violate fk_selected_scenario on persist. Drop it so the user re-selects.
    if offer.selected_scenario_id not in {s.id for s in offer.scenarios}:
        offer.selected_scenario_id = None
    return offer.scenarios


def compare(scenarios: list[Scenario]) -> list[dict]:
    """Flat comparison rows for the UI/agent (numbers come from each scenario's calc)."""
    rows = []
    for s in scenarios:
        c = s.calculation.value
        rows.append({
            "id": str(s.id),
            "scenario": s.label,
            "term_months": s.term_months,
            "annual_mileage_km": s.annual_mileage_km,
            "monthly_net_eur": c.monthly_net_eur,
            "monthly_gross_eur": c.monthly_gross_eur,
            "quantity": c.quantity,
            "total_monthly_gross_eur": c.total_monthly_gross_eur,
            "residual_pct": s.assessment.value.residual_value_pct,
            "customer_finance_rate_pct": c.customer_finance_rate_pct,
            "band": s.scoring.value.band.value,
            "service_maintenance": s.service_maintenance,
            "service_tyres": s.service_tyres,
            "insurance": s.insurance,
            "fits_budget": s.fits_budget,
            "budget_headroom_eur": s.budget_headroom_eur,
        })
    return rows


def select_scenario(offer: Offer, scenario_id) -> Offer:
    """Promote a scenario's results to the offer level (docs/06 §5)."""
    from app.domain.entities import WorkflowStatus

    chosen = next((s for s in offer.scenarios if s.id == scenario_id), None)
    if chosen is None:
        raise KeyError(f"scenario {scenario_id} not in offer {offer.reference}")
    offer.selected_scenario_id = chosen.id
    offer.calculation = chosen.calculation
    offer.assessment = chosen.assessment
    offer.scoring = chosen.scoring
    offer.commercial.term_months.value = chosen.term_months
    # promote the scenario's service bundle so the generated offer reflects exactly what was chosen
    offer.commercial.service_maintenance.value = chosen.service_maintenance
    offer.commercial.service_tyres.value = chosen.service_tyres
    offer.commercial.insurance.value = chosen.insurance
    offer.workflow_status = WorkflowStatus.SCENARIO_SELECTED
    return offer
