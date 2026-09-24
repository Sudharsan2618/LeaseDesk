"""Phase 3 — scenario engine tests (generate, compare, select). Deterministic, no AI/UI."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.policy import load_policy
from app.engine.orchestrator import run_pipeline
from app.engine.scenario import compare, generate_scenarios, select_scenario
from app.integration.base import AdapterMode, build_default_registry
from app.service.offer_factory import build_b2b_offer

POLICY = load_policy("DE_PKW_V1")


@pytest.fixture()
def registry():
    return build_default_registry(AdapterMode.MOCK)


def _priced_offer(registry, register="HRB-1001"):
    offer = build_b2b_offer(registry, vehicle_key="bmw-x1-sdrive18i", register_number=register,
                            term_months=36, annual_mileage_km=20000)
    return run_pipeline(offer, registry, POLICY)


def test_generate_scenarios_for_green(registry):
    offer = _priced_offer(registry)
    scenarios = generate_scenarios(offer, registry, POLICY)
    assert 2 <= len(scenarios) <= 4
    # each scenario is priced and labelled by term
    for s in scenarios:
        assert s.calculation is not None
        assert s.calculation.value.monthly_gross_eur > 0
        assert s.label.endswith("M")


def test_longer_term_lowers_monthly(registry):
    offer = _priced_offer(registry)
    scenarios = generate_scenarios(offer, registry, POLICY)
    by_term = {s.term_months: s.calculation.value.monthly_gross_eur for s in scenarios}
    # a longer term spreads cost over more months -> lower monthly (compare 24 vs 48 if present)
    if 24 in by_term and 48 in by_term:
        assert by_term[48] < by_term[24]


def test_compare_shape(registry):
    offer = _priced_offer(registry)
    scenarios = generate_scenarios(offer, registry, POLICY)
    rows = compare(scenarios)
    assert len(rows) == len(scenarios)
    assert {"scenario", "term_months", "monthly_gross_eur", "band"} <= set(rows[0])


def test_select_scenario_promotes_results(registry):
    offer = _priced_offer(registry)
    scenarios = generate_scenarios(offer, registry, POLICY)
    target = scenarios[-1]
    select_scenario(offer, target.id)
    assert offer.selected_scenario_id == target.id
    assert offer.calculation.value.monthly_gross_eur == target.calculation.value.monthly_gross_eur
    assert offer.commercial.term_months.value == target.term_months


def test_red_offer_gets_no_scenarios(registry):
    offer = _priced_offer(registry, register="HRB-3003")  # RED economic
    scenarios = generate_scenarios(offer, registry, POLICY)
    assert scenarios == []


def test_quantity_scales_total(registry):
    offer = build_b2b_offer(registry, vehicle_key="bmw-x1-sdrive18i", register_number="HRB-1001",
                            term_months=36, annual_mileage_km=20000, quantity=3)
    run_pipeline(offer, registry, POLICY)
    c = offer.calculation.value
    assert c.quantity == 3
    assert c.total_monthly_gross_eur == (c.monthly_gross_eur * 3)


def test_service_and_insurance_add_to_monthly(registry):
    base = build_b2b_offer(registry, vehicle_key="bmw-x1-sdrive18i", register_number="HRB-1001",
                           term_months=36, annual_mileage_km=20000)
    run_pipeline(base, registry, POLICY)
    full = build_b2b_offer(registry, vehicle_key="bmw-x1-sdrive18i", register_number="HRB-1001",
                           term_months=36, annual_mileage_km=20000,
                           service_maintenance=True, service_tyres=True, insurance=True)
    run_pipeline(full, registry, POLICY)
    cb, cf = base.calculation.value, full.calculation.value
    assert cf.service_maintenance_eur > 0 and cf.service_tyres_eur > 0 and cf.insurance_eur > 0
    assert cf.monthly_net_eur > cb.monthly_net_eur
    # add-ons equal exactly the delta
    delta = cf.service_maintenance_eur + cf.service_tyres_eur + cf.insurance_eur
    assert abs((cf.monthly_net_eur - cb.monthly_net_eur) - delta) < Decimal("0.01")


def test_scenarios_deterministic(registry):
    a = generate_scenarios(_priced_offer(registry), registry, POLICY)
    b = generate_scenarios(_priced_offer(registry), registry, POLICY)
    assert [s.calculation.value.monthly_gross_eur for s in a] == \
           [s.calculation.value.monthly_gross_eur for s in b]
