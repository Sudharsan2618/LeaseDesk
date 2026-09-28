"""Budget-constraint fitting (Phase 6, doc 13 §3.2, spec §5 COMPARE).

A budget is a *constraint* the salesperson states ("budget is €300k"), never a priced field. The
pattern the spec/doc demand: the agent proposes candidates, the **deterministic engine prices each**,
and we rank by fit. Nothing here computes a price — it reads the engine's `CalculationResult` and
compares it to the budget. `AI assists · Rules decide.`

Basis handling (the ambiguity the agent flags at intake, resolved before we get here):
  - monthly       -> fleet monthly gross         (total_monthly_gross_eur)
  - annual        -> fleet annual gross          (total_monthly_gross_eur × 12)
  - per_vehicle   -> per-vehicle monthly gross    (monthly_gross_eur)
  - total/unknown -> whole-contract cost          (total_monthly_gross_eur × term_months)
  - acquisition   -> fleet capex                  (acquisition_price × quantity)
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.core.policy import Policy, load_policy
from app.domain.entities import CalculationResult, Offer, Scenario
from app.integration.base import AdapterRegistry


def extract_budget(offer: Offer) -> Optional[dict]:
    """The active budget/monthly-cap constraint from the agent's extraction, or None.

    A `monthly_cap` is treated as a monthly-basis budget. Returns {value, basis, currency}."""
    proposed = (offer.agent_context or {}).get("proposed") or {}
    for c in proposed.get("constraints") or []:
        kind = (c.get("kind") or "").lower()
        if kind in ("budget", "monthly_cap") and c.get("value") not in (None, ""):
            basis = (c.get("basis") or ("monthly" if kind == "monthly_cap" else "unknown")).lower()
            if basis == "unknown":
                transcript = (offer.agent_context or {}).get("messages") or []
                request_text = " ".join(m.get("content", "") for m in transcript
                                         if m.get("role") == "user").lower()
                if any(p in request_text for p in (
                    "per year", "a year", "annual", "annually", "yearly", "/year")):
                    basis = "annual"
                elif any(p in request_text for p in (
                    "per month", "a month", "monthly", "/month")):
                    basis = "monthly"
                elif "per vehicle" in request_text or "per car" in request_text:
                    basis = "per_vehicle"
                elif any(p in request_text for p in (
                    "whole contract", "total contract", "over the contract")):
                    basis = "total"
            try:
                value = Decimal(str(c["value"]))
            except (ValueError, ArithmeticError):
                continue
            return {"value": value, "basis": basis, "currency": c.get("currency")}
    return None


def fit_metric(calc: CalculationResult, term_months: int, basis: str,
               *, acquisition_fleet_eur: Optional[Decimal] = None) -> Decimal:
    """The figure to compare against the budget, per basis. Reads engine output only."""
    if basis == "monthly":
        return calc.total_monthly_gross_eur
    if basis == "annual":
        return calc.total_monthly_gross_eur * Decimal("12")
    if basis == "per_vehicle":
        return calc.monthly_gross_eur
    if basis == "acquisition" and acquisition_fleet_eur is not None:
        return acquisition_fleet_eur
    # total / unknown -> whole-contract cost
    return calc.total_monthly_gross_eur * Decimal(term_months)


def annotate_scenarios(offer: Offer) -> Optional[dict]:
    """Tag each scenario with budget fit and sort fitting ones first (closest fit leads).
    No-op (returns None) when the offer carries no budget. Returns the budget dict when applied."""
    budget = extract_budget(offer)
    if not budget or not offer.scenarios:
        return None
    b, basis = budget["value"], budget["basis"]
    for s in offer.scenarios:
        if s.calculation is None:
            continue
        metric = fit_metric(s.calculation.value, s.term_months, basis)
        s.budget_metric_eur = metric
        s.budget_headroom_eur = b - metric
        s.fits_budget = metric <= b
    # fitting first; within each group, closest to budget (largest headroom that is still ≥0, then
    # least overage) — simplest stable key: (not fits, abs headroom)
    offer.scenarios.sort(key=lambda s: (not bool(s.fits_budget),
                                        abs(s.budget_headroom_eur or Decimal("0"))))
    return budget


def catalogue_budget_fit(
    offer: Offer,
    registry: AdapterRegistry,
    policy: Policy | None = None,
    *,
    candidate_keys: list[str],
) -> list[dict]:
    """Price each candidate vehicle at the offer's current commercial terms via the REAL engine
    (build_b2b_offer -> run_pipeline) and rank by budget fit. This answers "which asset fits the
    budget?" — the agent enumerates candidates, the engine prices them, we rank. Fitting first."""
    from app.engine.orchestrator import run_pipeline           # local import avoids a cycle
    from app.service.offer_factory import build_b2b_offer

    policy = policy or load_policy(offer.policy_version)
    budget = extract_budget(offer)
    c = offer.commercial
    reg_no = offer.customer.register_number.value
    term = int(c.term_months.value or 0)
    mileage = int(c.annual_mileage_km.value or 0)
    quantity = int(c.quantity.value or 1)
    if not (reg_no and term and mileage):
        return []

    rows: list[dict] = []
    for key in candidate_keys:
        try:
            cand = build_b2b_offer(
                registry, vehicle_key=key, register_number=reg_no, term_months=term,
                annual_mileage_km=mileage, quantity=quantity,
                special_payment_eur=c.special_payment_eur.value or Decimal("0"),
                service_maintenance=bool(c.service_maintenance.value),
                service_tyres=bool(c.service_tyres.value),
                insurance=bool(c.insurance.value))
            run_pipeline(cand, registry, policy)
        except Exception:                                        # a candidate that can't be built/priced is skipped
            continue
        if cand.calculation is None:
            rows.append({"vehicle_key": key, "priced": False, "band": cand.scoring.value.band.value
                         if cand.scoring else None})
            continue
        calc = cand.calculation.value
        row = {
            "vehicle_key": key, "priced": True,
            "band": cand.scoring.value.band.value if cand.scoring else None,
            "monthly_gross_eur": calc.monthly_gross_eur,
            "total_monthly_gross_eur": calc.total_monthly_gross_eur,
            "contract_total_eur": calc.total_monthly_gross_eur * Decimal(term),
        }
        if budget:
            metric = fit_metric(calc, term, budget["basis"])
            row["budget_metric_eur"] = metric
            row["budget_headroom_eur"] = budget["value"] - metric
            row["fits_budget"] = metric <= budget["value"]
        rows.append(row)

    if budget:
        rows.sort(key=lambda r: (not r.get("priced", False), not r.get("fits_budget", False),
                                 abs(r.get("budget_headroom_eur") or Decimal("0"))))
    return rows
