"""Phase 6 — budget-constraint scenario fitting (doc 13 §3.2, spec §5). Deterministic, no AI/DB.
Proves the budget is a *constraint* that only RANKS engine-priced options — the engine prices,
budget-fit never invents a number, and the budget never mutates a priced field."""
from decimal import Decimal

import pytest

from app.core.policy import load_policy
from app.engine.budget import annotate_scenarios, catalogue_budget_fit, extract_budget, fit_metric
from app.engine.orchestrator import run_pipeline
from app.engine.scenario import generate_scenarios
from app.integration.base import AdapterMode, build_default_registry
from app.service.offer_factory import build_b2b_offer

POLICY = load_policy("DE_PKW_V1")


@pytest.fixture()
def registry():
    return build_default_registry(AdapterMode.MOCK)


def _offer_with_budget(registry, value, basis="monthly", **kw):
    o = build_b2b_offer(registry, vehicle_key="bmw-x1-sdrive18i", register_number="HRB-1001",
                        term_months=36, annual_mileage_km=20000, **kw)
    o.agent_context = {"proposed": {"filters": {}, "constraints": [
        {"kind": "budget", "value": value, "basis": basis}]}}
    run_pipeline(o, registry, POLICY)
    return o


def test_extract_budget_reads_constraint(registry):
    o = _offer_with_budget(registry, 700)
    b = extract_budget(o)
    assert b and b["value"] == Decimal("700") and b["basis"] == "monthly"


def test_high_budget_all_fit_low_budget_none_fit(registry):
    hi = _offer_with_budget(registry, 10_000_000)
    generate_scenarios(hi, registry, POLICY); annotate_scenarios(hi)
    assert hi.scenarios and all(s.fits_budget for s in hi.scenarios)

    lo = _offer_with_budget(registry, 1)
    generate_scenarios(lo, registry, POLICY); annotate_scenarios(lo)
    assert lo.scenarios and not any(s.fits_budget for s in lo.scenarios)


def test_fit_metric_matches_engine_numbers_and_headroom(registry):
    o = _offer_with_budget(registry, 700, basis="monthly")
    generate_scenarios(o, registry, POLICY); annotate_scenarios(o)
    for s in o.scenarios:
        calc = s.calculation.value                       # the number came from the ENGINE
        assert s.budget_metric_eur == calc.total_monthly_gross_eur
        assert s.budget_headroom_eur == Decimal("700") - calc.total_monthly_gross_eur
        assert s.fits_budget == (calc.total_monthly_gross_eur <= Decimal("700"))


def test_scenarios_sorted_fitting_first(registry):
    o = _offer_with_budget(registry, 700)
    generate_scenarios(o, registry, POLICY); annotate_scenarios(o)
    fits = [bool(s.fits_budget) for s in o.scenarios]
    assert fits == sorted(fits, reverse=True)            # all True before any False


def test_fit_metric_basis_semantics():
    class _Calc:
        total_monthly_gross_eur = Decimal("600")
        monthly_gross_eur = Decimal("300")
    assert fit_metric(_Calc(), 36, "monthly") == Decimal("600")
    assert fit_metric(_Calc(), 36, "per_vehicle") == Decimal("300")
    assert fit_metric(_Calc(), 36, "total") == Decimal("600") * 36
    assert fit_metric(_Calc(), 36, "unknown") == Decimal("600") * 36


def test_catalogue_budget_fit_prices_via_engine_and_ranks(registry):
    o = _offer_with_budget(registry, 10_000_000)          # generous -> priced candidates fit
    rows = catalogue_budget_fit(o, registry, POLICY,
                                candidate_keys=["bmw-x1-sdrive18i", "vw-passat-variant-20tdi"])
    priced = [r for r in rows if r.get("priced")]
    assert priced and all("total_monthly_gross_eur" in r for r in priced)  # engine-priced
    assert all(r["fits_budget"] for r in priced)          # all fit the generous budget


def test_budget_does_not_mutate_priced_fields(registry):
    o = _offer_with_budget(registry, 500, basis="monthly")
    generate_scenarios(o, registry, POLICY); annotate_scenarios(o)
    # the budget must never become a special payment or alter the commercial inputs
    assert (o.commercial.special_payment_eur.value or Decimal("0")) == Decimal("0")
