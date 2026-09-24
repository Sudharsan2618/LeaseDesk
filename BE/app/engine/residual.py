"""Residual value + confidence engine (DE_PKW_RV_V1, docs/04 §4).

RV% = base_term_RV + mileage_adjustment + vehicle_age_adjustment + market_asset_adjustment,
clamped to [minimum_pct, maximum_pct]. Residual amount = base_price * RV%, where the base price
is the SEEDED list_price_net (Q-CALC-1 resolved: residual applies to list price, net basis for B2B).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.core.policy import Policy
from app.core.types import ResidualConfidence, ResultEnvelope, inputs_digest
from app.domain.entities import AssessmentResult

_TWO = Decimal("0.01")


def _clamp(x: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    return max(lo, min(hi, x))


def compute_residual(
    policy: Policy,
    *,
    list_price_net: Decimal,
    term_months: int,
    annual_mileage_km: int,
    is_used: bool = False,
    vehicle_age_years: int = 0,
    data_complete: bool = True,
) -> ResultEnvelope[AssessmentResult]:
    r = policy.residual
    base = policy.base_term_rv_pct(term_months)

    # mileage adjustment (asymmetric; capped) relative to the baseline
    diff = Decimal(annual_mileage_km - policy.mileage_baseline)
    steps = diff / Decimal("5000")
    if diff > 0:
        penalty = steps * Decimal(str(r["extra_5000km_penalty_pp"]))
        penalty = min(penalty, Decimal(str(r["mileage_penalty_cap_pp"])))
        mileage_adj = -penalty
    elif diff < 0:
        bonus = (-steps) * Decimal(str(r["lower_5000km_bonus_pp"]))
        bonus = min(bonus, Decimal(str(r["mileage_uplift_cap_pp"])))
        mileage_adj = bonus
    else:
        mileage_adj = Decimal("0")

    # vehicle age adjustment (MVP: new = 0; used = -2pp per full year)
    age_adj = Decimal("-2") * Decimal(vehicle_age_years) if is_used else Decimal("0")
    market_adj = Decimal("0")  # reserved for future market signal

    rv_pct = _clamp(
        base + mileage_adj + age_adj + market_adj,
        Decimal(str(r["minimum_pct"])),
        Decimal(str(r["maximum_pct"])),
    )
    rv_amount = (list_price_net * rv_pct / Decimal("100")).quantize(_TWO, ROUND_HALF_UP)

    confidence = _confidence(term_months, annual_mileage_km, is_used, vehicle_age_years, data_complete)

    assumptions = [
        "used_vehicle" if is_used else "new_vehicle",
        f"{term_months}_month_term",
        f"{annual_mileage_km}_km_annual",
        f"rv_base_{base}pct",
    ]

    payload = AssessmentResult(
        residual_value_pct=rv_pct,
        residual_value_amount_eur=rv_amount,
        residual_confidence=confidence,
        assumptions=assumptions,
    )
    return ResultEnvelope[AssessmentResult](
        value=payload,
        engine=policy.engine_versions["residual"],
        policies={"residual_policy": policy.engine_versions["residual"]},
        inputs_digest=inputs_digest(
            {"list_price_net": list_price_net, "term": term_months, "mileage": annual_mileage_km,
             "is_used": is_used, "age": vehicle_age_years, "data_complete": data_complete}
        ),
        assumptions=assumptions,
    )


def _confidence(term_months: int, annual_mileage_km: int, is_used: bool,
                vehicle_age_years: int, data_complete: bool) -> ResidualConfidence:
    # LOW wins if any low condition holds
    if (is_used and vehicle_age_years > 3) or annual_mileage_km > 35000 or not data_complete:
        return ResidualConfidence.LOW
    # HIGH requires all of: new, term<=48, km<=25000, complete data
    if (not is_used) and term_months <= 48 and annual_mileage_km <= 25000 and data_complete:
        return ResidualConfidence.HIGH
    return ResidualConfidence.MEDIUM
