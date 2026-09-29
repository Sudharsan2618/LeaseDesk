"""Explain: turn deterministic results into grounded natural-language text (EN/DE).

The LLM reads the ResultEnvelope facts and explains them; it CANNOT change a number. A grounding
check rejects any explanation that cites a number not present in the results, falling back to a
deterministic template. Without an LLM key, the template is used directly.
"""
from __future__ import annotations

import re
from decimal import Decimal

from app.agent import llm
from app.domain.entities import Offer


# --- number grounding -------------------------------------------------------- #
def _allowed_numbers(offer: Offer) -> set[str]:
    vals: set[Decimal] = set()
    if offer.calculation:
        c = offer.calculation.value
        vals |= {c.monthly_net_eur, c.monthly_gross_eur, c.funding_rate_pct, c.commercial_margin_pct,
                 c.customer_finance_rate_pct, c.reference_rate_pct, c.vat_pct, c.netcap_eur,
                 c.residual_value_amount_eur, c.pv_residual_eur, Decimal(c.contract_mileage_km)}
    if offer.assessment:
        a = offer.assessment.value
        vals |= {a.residual_value_pct, a.residual_value_amount_eur}
    if offer.scoring:
        vals |= {offer.scoring.value.mvp_risk_score}
    if offer.commercial.term_months.value is not None:
        vals.add(Decimal(offer.commercial.term_months.value))
    if offer.commercial.annual_mileage_km.value is not None:
        vals.add(Decimal(offer.commercial.annual_mileage_km.value))
    for s in offer.scenarios:
        if s.calculation:
            vals.add(s.calculation.value.monthly_gross_eur)
        vals.add(Decimal(s.term_months))
    # allow the integer and 2dp string forms of each value
    out: set[str] = set()
    for v in vals:
        out.add(f"{v.normalize():f}")
        out.add(str(int(v))) if v == v.to_integral_value() else None
        out.add(f"{v:.2f}")
        out.add(f"{v:.1f}")
    return {o for o in out if o}


_NUM = re.compile(r"\d[\d,]*\.?\d*")


def grounding_check(text: str, allowed: set[str]) -> bool:
    """Every number-looking token in the text must match an allowed value (comma-insensitive)."""
    for tok in _NUM.findall(text):
        clean = tok.replace(",", "")
        if clean in allowed:
            continue
        # tolerate rounding differences on money
        try:
            d = Decimal(clean)
            if any(abs(d - Decimal(a)) <= Decimal("0.05") for a in allowed
                   if re.fullmatch(r"-?\d+\.?\d*", a)):
                continue
        except Exception:  # noqa: BLE001
            pass
        return False
    return True


# --- explanations ------------------------------------------------------------ #
def _facts(offer: Offer) -> str:
    lines = [f"Offer {offer.reference}, language={offer.language.value}, "
             f"status={offer.workflow_status.value}."]
    if offer.scoring:
        s = offer.scoring.value
        lines.append(f"Risk band {s.band.value} (score {s.mvp_risk_score}); "
                     f"scoring pattern {s.pattern.value}; hard_blocks={s.hard_blocks}.")
    if offer.asset_assessment:
        aa = offer.asset_assessment.value
        lines.append(f"Asset assessment {aa.status.value}"
                     + (f" ({aa.result})" if aa.result else "")
                     + f" for {aa.asset_category} via {aa.mode}.")
    if offer.assessment:
        a = offer.assessment.value
        lines.append(f"Residual {a.residual_value_pct}% = {a.residual_value_amount_eur} EUR, "
                     f"confidence {a.residual_confidence.value}.")
    if offer.calculation:
        c = offer.calculation.value
        lines.append(f"Funding {c.funding_rate_pct}% + margin {c.commercial_margin_pct}% "
                     f"= finance rate {c.customer_finance_rate_pct}%. "
                     f"Monthly net {c.monthly_net_eur} EUR, gross {c.monthly_gross_eur} EUR "
                     f"(VAT {c.vat_pct}%).")
    if offer.exceptions:
        lines.append("Exceptions: " + ", ".join(e.code for e in offer.exceptions) + ".")
    return "\n".join(lines)


def _lang_word(offer: Offer) -> str:
    return "German" if offer.language.value == "de" else "English"


def explain_pricing(offer: Offer) -> str:
    template = _templated_pricing(offer)
    if not llm.llm_available():
        return template
    system = ("You explain a leasing offer to an internal user. Use ONLY the numbers in the FACTS. "
              "Do not invent or recompute any figure. Be concise (3-5 sentences). "
              f"Write in {_lang_word(offer)}.")
    try:
        text = llm.chat(system, f"FACTS:\n{_facts(offer)}\n\nExplain the pricing/outcome.")
    except Exception as e:  # noqa: BLE001
        print(f"[agent] explain_pricing LLM error: {e}")
        return template
    return text if grounding_check(text, _allowed_numbers(offer)) else template


def explain_scenarios(offer: Offer) -> str:
    template = _templated_scenarios(offer)
    if not offer.scenarios or not llm.llm_available():
        return template
    rows = "; ".join(f"{s.label}: {s.calculation.value.monthly_gross_eur} EUR/mo, "
                     f"residual {s.assessment.value.residual_value_pct}%"
                     for s in offer.scenarios if s.calculation)
    obj = offer.commercial.objective or ""
    system = ("You compare leasing scenarios for an internal user. Use ONLY the given numbers and "
              "the options shown. All scenarios preserve the requested asset, term, mileage, quantity, "
              "payment and confirmed choices; compare only their service bundles. Do not suggest "
              "different terms or claim a longer term is cheaper. You may recommend an option as "
              "ADVISORY, but you never select it. Concise. "
              f"Write in {_lang_word(offer)}.")
    try:
        text = llm.chat(system, f"Objective: {obj}\nScenarios: {rows}\n\nCompare and advise.")
    except Exception as e:  # noqa: BLE001
        print(f"[agent] explain_scenarios LLM error: {e}")
        return template
    return text if grounding_check(text, _allowed_numbers(offer)) else template


# --- deterministic fallbacks ------------------------------------------------- #
def _templated_pricing(offer: Offer) -> str:
    if offer.calculation is None:
        band = offer.scoring.value.band.value if offer.scoring else "?"
        codes = ", ".join(e.code for e in offer.exceptions) or "none"
        return (f"Offer {offer.reference} was not priced (risk band {band}). "
                f"Blocking conditions: {codes}.")
    c = offer.calculation.value
    return (f"Offer {offer.reference}: monthly rental {c.monthly_gross_eur} EUR gross "
            f"({c.monthly_net_eur} EUR net + {c.vat_pct}% VAT), finance rate "
            f"{c.customer_finance_rate_pct}% (funding {c.funding_rate_pct}% + margin "
            f"{c.commercial_margin_pct}%). Residual assumed at "
            f"{offer.assessment.value.residual_value_pct}%.")


def _templated_scenarios(offer: Offer) -> str:
    if not offer.scenarios:
        return "No scenarios available."
    parts = [f"{s.label}: {s.calculation.value.monthly_gross_eur} EUR/mo"
             for s in offer.scenarios if s.calculation]
    return "Scenarios use the requested term and differ only by optional service bundle: " + "; ".join(parts) + "."
