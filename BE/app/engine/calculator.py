"""Lease calculator (MVP_LEASE_CALC_V1, docs/04 §5-6): amortisation-to-residual annuity.

All money is Decimal. Only the final presented monthly figures are rounded (to cents); internal
math keeps full precision. Raises SpecialPaymentTooHigh when NetCap <= PV(residual).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.core.policy import Policy
from app.core.types import ResultEnvelope, inputs_digest
from app.domain.entities import AssessmentResult, CalculationResult
from app.engine.exceptions_registry import SpecialPaymentTooHigh

_CENTS = Decimal("0.01")


def _per_km_rate(policy: Policy, vehicle_value_eur: Decimal) -> Decimal:
    rates = policy.raw["mileage_settlement"]["per_km_rate_eur_by_vehicle_value"]
    if vehicle_value_eur <= 30000:
        return Decimal(str(rates["le_30k"]))
    if vehicle_value_eur <= 60000:
        return Decimal(str(rates["30k_60k"]))
    return Decimal(str(rates["gt_60k"]))


def calculate(
    policy: Policy,
    *,
    reference_rate_pct: Decimal,
    funding_rate_pct: Decimal,
    commercial_margin_pct: Decimal,
    assessment: AssessmentResult,
    acquisition_price_net: Decimal,
    list_price_net: Decimal,
    financed_fees_eur: Decimal,
    discount_net_eur: Decimal,
    special_payment_eur: Decimal,
    recurring_service_fee_eur: Decimal,
    vat_pct: Decimal,
    term_months: int,
    annual_mileage_km: int,
    quantity: int = 1,
    service_maintenance: bool = False,
    service_tyres: bool = False,
    insurance: bool = False,
) -> ResultEnvelope[CalculationResult]:
    n = term_months
    customer_finance_rate = funding_rate_pct + commercial_margin_pct  # annual %
    r = (customer_finance_rate / Decimal("100")) / Decimal("12")      # monthly fraction

    netcap = acquisition_price_net + financed_fees_eur - discount_net_eur - special_payment_eur
    rv_amount = assessment.residual_value_amount_eur

    if r == 0:
        pv_rv = rv_amount
        if netcap <= pv_rv:
            raise SpecialPaymentTooHigh(f"NetCap {netcap} <= residual {pv_rv}")
        base_lease = (netcap - rv_amount) / Decimal(n)
    else:
        pv_rv = rv_amount / ((Decimal("1") + r) ** n)
        if netcap <= pv_rv:
            raise SpecialPaymentTooHigh(f"NetCap {netcap} <= PV(residual) {pv_rv}")
        annuity = r / (Decimal("1") - (Decimal("1") + r) ** (-n))
        base_lease = (netcap - pv_rv) * annuity

    # optional add-ons (per vehicle, net) — deterministic from DE_PKW_V1
    maint = policy.maintenance_eur_month if service_maintenance else Decimal("0")
    tyres = policy.tyres_eur_month if service_tyres else Decimal("0")
    ins = (list_price_net * policy.insurance_annual_pct_of_value / Decimal("100") / Decimal("12")
           ) if insurance else Decimal("0")

    monthly_net = base_lease + recurring_service_fee_eur + maint + tyres + ins
    monthly_gross = monthly_net * (Decimal("1") + vat_pct / Decimal("100"))
    q = max(1, int(quantity))

    payload = CalculationResult(
        reference_rate_pct=reference_rate_pct,
        funding_rate_pct=funding_rate_pct,
        commercial_margin_pct=commercial_margin_pct,
        customer_finance_rate_pct=customer_finance_rate,
        netcap_eur=netcap.quantize(_CENTS, ROUND_HALF_UP),
        residual_value_amount_eur=rv_amount,
        pv_residual_eur=pv_rv.quantize(_CENTS, ROUND_HALF_UP),
        base_lease_eur=base_lease.quantize(_CENTS, ROUND_HALF_UP),
        service_maintenance_eur=maint.quantize(_CENTS, ROUND_HALF_UP),
        service_tyres_eur=tyres.quantize(_CENTS, ROUND_HALF_UP),
        insurance_eur=ins.quantize(_CENTS, ROUND_HALF_UP),
        monthly_net_eur=monthly_net.quantize(_CENTS, ROUND_HALF_UP),
        vat_pct=vat_pct,
        monthly_gross_eur=monthly_gross.quantize(_CENTS, ROUND_HALF_UP),
        quantity=q,
        total_monthly_net_eur=(monthly_net * q).quantize(_CENTS, ROUND_HALF_UP),
        total_monthly_gross_eur=(monthly_gross * q).quantize(_CENTS, ROUND_HALF_UP),
        contract_mileage_km=int(annual_mileage_km * n / 12),
        mileage_settlement_per_km_eur=_per_km_rate(policy, acquisition_price_net),
    )
    return ResultEnvelope[CalculationResult](
        value=payload,
        engine=policy.engine_versions["lease_calc"],
        policies={
            "lease_calc": policy.engine_versions["lease_calc"],
            "funding_policy": policy.engine_versions["funding"],
            "margin_policy": policy.engine_versions["margin"],
            "residual_policy": policy.engine_versions["residual"],
            "tax_source": policy.raw["vat"]["source"],
            "reference_rate_source": policy.raw["funding"]["reference_rate_source"],
        },
        inputs_digest=inputs_digest({
            "ref": reference_rate_pct, "funding": funding_rate_pct, "margin": commercial_margin_pct,
            "acq": acquisition_price_net, "list": list_price_net, "fees": financed_fees_eur,
            "disc": discount_net_eur, "sp": special_payment_eur, "svc": recurring_service_fee_eur,
            "vat": vat_pct, "term": n, "mileage": annual_mileage_km, "rv": rv_amount,
            "qty": quantity, "maint": service_maintenance, "tyres": service_tyres, "ins": insurance,
        }),
        assumptions=list(assessment.assumptions),
    )
