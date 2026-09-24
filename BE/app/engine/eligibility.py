"""Eligibility & pre-calculation validation (docs/04 §8.1). Produces typed Exception_ objects.

Separated from scoring/calculation so it can run before pricing (term/mileage/special-payment/
vehicle gates) and again at final validation.
"""
from __future__ import annotations

from decimal import Decimal

from app.core.policy import Policy
from app.core.types import ResidualConfidence
from app.domain.entities import Exception_
from app.engine import exceptions_registry as ex


def max_allowed_term(policy: Policy, *, is_used: bool, annual_mileage_km: int,
                     rv_confidence: ResidualConfidence) -> int:
    """Context-aware cap on the term (docs/04 §8.1 / policy.term_context_caps)."""
    cap = policy.term_max
    caps = policy.term_context_caps
    if is_used:
        cap = min(cap, caps["used_vehicle_max_months"])
    if annual_mileage_km > 30000:
        cap = min(cap, caps["high_mileage_over_30k_max_months"])
    if rv_confidence is ResidualConfidence.LOW:
        cap = min(cap, caps["low_rv_confidence_max_months"])
    return cap


def check_term(policy: Policy, *, term_months: int, is_used: bool, annual_mileage_km: int,
               rv_confidence: ResidualConfidence) -> Exception_ | None:
    if term_months < policy.term_min or term_months > policy.term_max:
        return ex.term_out_of_range(term_months, "outside_absolute_range")
    cap = max_allowed_term(policy, is_used=is_used, annual_mileage_km=annual_mileage_km,
                           rv_confidence=rv_confidence)
    if term_months > cap:
        return ex.term_out_of_range(term_months, f"exceeds_context_cap_{cap}")
    return None


def check_quantity(policy: Policy, *, quantity: int) -> Exception_ | None:
    if quantity < policy.quantity_min or quantity > policy.quantity_max:
        return ex.product_ineligible(
            f"quantity_{quantity}_outside_{policy.quantity_min}-{policy.quantity_max}", blocking=True)
    return None


def check_mileage(policy: Policy, *, annual_mileage_km: int) -> Exception_ | None:
    if annual_mileage_km > policy.mileage_max:
        return ex.mileage_out_of_range(annual_mileage_km)
    if annual_mileage_km < policy.mileage_min:
        return ex.mileage_manual_review(annual_mileage_km)
    return None


def check_special_payment(policy: Policy, *, special_payment_eur: Decimal,
                          acquisition_price_net: Decimal) -> Exception_ | None:
    if acquisition_price_net <= 0:
        return None
    pct = (special_payment_eur / acquisition_price_net * Decimal("100"))
    if pct > policy.sp_review_max_pct:
        return ex.special_payment_block(str(pct.quantize(Decimal("0.1"))))
    if pct > policy.sp_standard_max_pct:
        return ex.special_payment_high(str(pct.quantize(Decimal("0.1"))))
    return None


def check_vehicle(policy: Policy, *, category: str, price_eur: Decimal,
                  vehicle_age_years: int, term_months: int) -> list[Exception_]:
    out: list[Exception_] = []
    v = policy.eligibility_vehicle
    if category != v["category"]:
        out.append(ex.product_ineligible(f"category_{category}_not_{v['category']}", blocking=True))
    if price_eur < Decimal(str(v["price_min_eur"])):
        out.append(ex.product_ineligible("price_below_min", blocking=True))
    if price_eur > Decimal(str(v["price_max_eur"])):
        out.append(ex.product_ineligible("price_above_absolute_max", blocking=True))
    elif price_eur > policy.high_value_review_threshold_eur:
        out.append(ex.high_value_review(str(price_eur)))  # >100k = review, not block
    age_at_end = vehicle_age_years + term_months / 12
    if age_at_end > v["age_at_end_max_years"]:
        out.append(ex.product_ineligible(f"age_at_end_{age_at_end:.1f}y_over_{v['age_at_end_max_years']}",
                                         blocking=True))
    return out
