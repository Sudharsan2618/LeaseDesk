"""MVP risk engine (DE_PKW_RISK_V1, docs/04 §7). B2B path implemented for the MVP.

The bureau result is only ONE input factor; the band is decided here, never copied from the bureau.
Hard-block conditions bypass the weighted score and yield RED (compliance). Otherwise a weighted
0-100 score is banded GREEN/YELLOW/RED. (B2C affordability path is stubbed for a later phase.)
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.core.policy import Policy
from app.core.types import (
    CustomerType,
    RedKind,
    ResultEnvelope,
    RiskBand,
    ScoringPattern,
    inputs_digest,
)
from app.domain.entities import (
    CreditResult,
    KycResult,
    SanctionsResult,
    ScoringFactor,
    ScoringResult,
)

_TWO = Decimal("0.01")


def _band(policy: Policy, score: Decimal) -> tuple[RiskBand, RedKind | None]:
    if score >= policy.risk_green_min:
        return RiskBand.GREEN, None
    if score >= policy.risk_yellow_min:
        return RiskBand.YELLOW, None
    return RiskBand.RED, RedKind.ECONOMIC


def _scoring_pattern(
    policy: Policy, *, exposure_eur: Decimal, quantity: int, acquisition_price_eur: Decimal,
) -> tuple[ScoringPattern, list[str]]:
    """Spec §3.11 — AUTOMATIC iff every parameter falls inside the policy's predefined automatic
    envelope; otherwise MANUAL, listing which parameter(s) forced manual review. Deterministic and
    policy-driven; the Agent never decides this."""
    env = policy.scoring_automatic_envelope
    reasons: list[str] = []
    if "max_total_exposure_eur" in env and exposure_eur > env["max_total_exposure_eur"]:
        reasons.append(f"exposure {exposure_eur} > {env['max_total_exposure_eur']}")
    if "max_quantity" in env and Decimal(quantity) > env["max_quantity"]:
        reasons.append(f"quantity {quantity} > {env['max_quantity']}")
    if "max_acquisition_price_eur" in env and acquisition_price_eur > env["max_acquisition_price_eur"]:
        reasons.append(f"unit price {acquisition_price_eur} > {env['max_acquisition_price_eur']}")
    return (ScoringPattern.MANUAL, reasons) if reasons else (ScoringPattern.AUTOMATIC, [])


def _exposure_score(policy: Policy, exposure_eur: Decimal, limit_eur: Decimal) -> tuple[Decimal, Decimal]:
    """Returns (ratio_pct, score_0_100)."""
    if limit_eur <= 0:
        return Decimal("999"), Decimal("20")
    ratio = (exposure_eur / limit_eur * Decimal("100"))
    bands = policy.b2b_exposure_bands
    if ratio <= bands["strong_max"]:
        score = Decimal("90")
    elif ratio <= bands["moderate_max"]:
        score = Decimal("65")
    else:
        score = Decimal("30")
    return ratio.quantize(_TWO, ROUND_HALF_UP), score


def _company_age_score(age_years: int) -> Decimal:
    if age_years >= 10:
        return Decimal("90")
    if age_years >= 5:
        return Decimal("75")
    if age_years >= 3:
        return Decimal("60")
    if age_years >= 1:
        return Decimal("45")
    return Decimal("30")


def score_b2b(
    policy: Policy,
    *,
    credit: CreditResult,
    sanctions: SanctionsResult,
    kyc: KycResult,
    exposure_eur: Decimal,
    quantity: int = 1,
    acquisition_price_eur: Decimal = Decimal("0"),
) -> ResultEnvelope[ScoringResult]:
    pattern, manual_reasons = _scoring_pattern(
        policy, exposure_eur=exposure_eur, quantity=quantity,
        acquisition_price_eur=acquisition_price_eur)

    # Demo mode keeps the scoring outcome green so sales demos can exercise pricing end to end.
    # The source factors are still calculated and retained for transparent explanation. This
    # override is explicitly policy-configurable; live deployments should turn it off.
    force_green = bool(policy.raw.get("demo", {}).get("force_green_risk", True))

    # 1) hard blocks -> RED (compliance), skip the weighted score, except in configured demo mode.
    hard_blocks: list[str] = []
    if sanctions.match:
        hard_blocks.append("SANCTIONS_MATCH")
    if kyc.kyc_status == "FAILED" or not kyc.identity_verified:
        hard_blocks.append("KYC_FAILED")
    if credit.insolvency_flag:
        hard_blocks.append("COMPANY_INSOLVENT")

    if hard_blocks and not force_green:
        payload = ScoringResult(
            mvp_risk_score=Decimal("0"), band=RiskBand.RED, red_kind=RedKind.COMPLIANCE,
            pattern=pattern, manual_reasons=manual_reasons, factors=[], hard_blocks=hard_blocks,
        )
        return _wrap(policy, payload, {"hard_blocks": hard_blocks})

    # 2) weighted score
    w = policy.risk_weights(CustomerType.B2B.value)
    ratio_pct, exposure_score = _exposure_score(policy, exposure_eur, credit.recommended_limit_eur)
    raw_scores = {
        "credit_quality": Decimal(credit.credit_index),
        "financial_strength": Decimal(credit.financial_strength),
        "exposure_vs_limit": exposure_score,
        "company_age": _company_age_score(credit.company_age_years),
        "payment_history": Decimal(credit.payment_history_score),
    }
    factors: list[ScoringFactor] = []
    total = Decimal("0")
    for name, weight in w.items():
        s = raw_scores[name]
        contribution = (weight * s)
        total += contribution
        factors.append(ScoringFactor(name=name, weight=weight,
                                     score_0_100=s.quantize(_TWO, ROUND_HALF_UP),
                                     contribution=contribution.quantize(_TWO, ROUND_HALF_UP)))
    total = total.quantize(_TWO, ROUND_HALF_UP)
    band, red_kind = (RiskBand.GREEN, None) if force_green else _band(policy, total)

    payload = ScoringResult(mvp_risk_score=total, band=band, red_kind=red_kind,
                            pattern=pattern, manual_reasons=manual_reasons,
                            factors=factors, hard_blocks=hard_blocks)
    return _wrap(policy, payload, {
        "credit_index": credit.credit_index, "financial_strength": credit.financial_strength,
        "exposure_ratio_pct": str(ratio_pct), "company_age": credit.company_age_years,
        "payment_history": credit.payment_history_score,
    })


def _wrap(policy: Policy, payload: ScoringResult, digest_inputs: dict) -> ResultEnvelope[ScoringResult]:
    return ResultEnvelope[ScoringResult](
        value=payload,
        engine=policy.engine_versions["risk"],
        policies={"risk_policy": policy.engine_versions["risk"]},
        inputs_digest=inputs_digest(digest_inputs),
    )
