"""Loader + typed accessor for the MVP reference policy DE_PKW_V1 (docs/05).

The policy is data, not code. It lives in app/config/*.json, is versioned, and is *never* placed
in an LLM prompt. Engines read it through this typed wrapper so the constants have one home.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _dec(x: Any) -> Decimal:
    return Decimal(str(x))


class Policy:
    """Thin typed view over the raw policy dict. Keeps the JSON as the single source of numbers."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    # identity ---------------------------------------------------------------
    @property
    def policy_id(self) -> str:
        return self.raw["policy_id"]

    @property
    def currency(self) -> str:
        return self.raw["currency"]

    @property
    def engine_versions(self) -> dict[str, str]:
        return self.raw["engine_versions"]

    # term -------------------------------------------------------------------
    @property
    def term_min(self) -> int:
        return self.raw["term"]["min_months"]

    @property
    def term_max(self) -> int:
        return self.raw["term"]["max_months"]

    @property
    def term_step(self) -> int:
        return self.raw["term"]["step_months"]

    @property
    def term_preferred(self) -> list[int]:
        return list(self.raw["term"]["preferred"])

    @property
    def term_context_caps(self) -> dict[str, int]:
        return self.raw["term_context_caps"]

    # mileage ----------------------------------------------------------------
    @property
    def mileage_baseline(self) -> int:
        return self.raw["mileage"]["baseline_annual_km"]

    @property
    def mileage_min(self) -> int:
        return self.raw["mileage"]["min_annual_km"]

    @property
    def mileage_max(self) -> int:
        return self.raw["mileage"]["max_annual_km"]

    # special payment --------------------------------------------------------
    @property
    def sp_standard_max_pct(self) -> Decimal:
        return _dec(self.raw["special_payment"]["standard_max_pct"])

    @property
    def sp_review_max_pct(self) -> Decimal:
        return _dec(self.raw["special_payment"]["review_max_pct"])

    # quantity & services ----------------------------------------------------
    @property
    def quantity_min(self) -> int:
        return self.raw["quantity"]["min"]

    @property
    def quantity_max(self) -> int:
        return self.raw["quantity"]["max"]

    @property
    def maintenance_eur_month(self) -> Decimal:
        return _dec(self.raw["services"]["maintenance_eur_month"])

    @property
    def tyres_eur_month(self) -> Decimal:
        return _dec(self.raw["services"]["tyres_eur_month"])

    @property
    def insurance_annual_pct_of_value(self) -> Decimal:
        return _dec(self.raw["services"]["insurance_annual_pct_of_value"])

    # residual ---------------------------------------------------------------
    @property
    def residual(self) -> dict[str, Any]:
        return self.raw["residual"]

    def base_term_rv_pct(self, term_months: int) -> Decimal:
        """Base RV% for a term, interpolating linearly between tabulated anchor terms."""
        table = {int(k): _dec(v) for k, v in self.residual["base_term_rv_pct"].items()}
        if term_months in table:
            return table[term_months]
        anchors = sorted(table)
        if term_months <= anchors[0]:
            return table[anchors[0]]
        if term_months >= anchors[-1]:
            return table[anchors[-1]]
        lo = max(a for a in anchors if a < term_months)
        hi = min(a for a in anchors if a > term_months)
        frac = _dec(term_months - lo) / _dec(hi - lo)
        return table[lo] + (table[hi] - table[lo]) * frac

    # funding ----------------------------------------------------------------
    @property
    def funding(self) -> dict[str, Any]:
        return self.raw["funding"]

    def term_spread_pp(self, term_months: int) -> Decimal:
        for rng, pp in self.funding["term_spread_pp"].items():
            lo, hi = (int(x) for x in rng.split("-"))
            if lo <= term_months <= hi:
                return _dec(pp)
        # outside tabulated ranges -> clamp to nearest bucket
        buckets = {tuple(int(x) for x in r.split("-")): _dec(pp)
                   for r, pp in self.funding["term_spread_pp"].items()}
        if term_months < min(lo for lo, _ in buckets):
            return buckets[min(buckets)]
        return buckets[max(buckets)]

    def asset_uncertainty_spread_pp(self, confidence: str) -> Decimal:
        return _dec(self.funding["asset_uncertainty_spread_pp"][confidence])

    # margin -----------------------------------------------------------------
    @property
    def margin_base_pp(self) -> Decimal:
        return _dec(self.raw["margin"]["base_pp"])

    def risk_adjustment_pp(self, band: str) -> Decimal | None:
        v = self.raw["margin"]["risk_adjustment_pp"][band]
        return None if v is None else _dec(v)

    def deal_size_adjustment_pp(self, price_eur: Decimal) -> Decimal | str:
        m = self.raw["margin"]["deal_size_adjustment_pp"]
        if price_eur < 20000:
            return _dec(m["lt_20k"])
        if price_eur <= 60000:
            return _dec(m["20k_60k"])
        if price_eur <= 100000:
            return _dec(m["60k_100k"])
        return m["gt_100k"]  # "MANUAL_REVIEW"

    @property
    def margin_floor_pp(self) -> Decimal:
        return _dec(self.raw["margin"]["commercial_margin_floor_pp"])

    @property
    def margin_cap_pp(self) -> Decimal:
        return _dec(self.raw["margin"]["commercial_margin_cap_pp"])

    # risk -------------------------------------------------------------------
    @property
    def risk_green_min(self) -> Decimal:
        return _dec(self.raw["risk"]["green_min"])

    @property
    def risk_yellow_min(self) -> Decimal:
        return _dec(self.raw["risk"]["yellow_min"])

    def risk_weights(self, customer_type: str) -> dict[str, Decimal]:
        return {k: _dec(v) for k, v in self.raw["risk_weights"][customer_type].items()}

    @property
    def b2b_exposure_bands(self) -> dict[str, Decimal]:
        return {k: _dec(v) for k, v in self.raw["b2b_exposure_bands"].items()}

    @property
    def scoring_automatic_envelope(self) -> dict[str, Decimal]:
        """The predefined 'automatic scoring' envelope (spec §3.11). Parameters outside it make the
        scoring pattern MANUAL. Absent in a policy ⇒ empty envelope ⇒ everything scores automatically."""
        return {k: _dec(v) for k, v in self.raw.get("scoring_automatic_envelope", {}).items()}

    # eligibility ------------------------------------------------------------
    @property
    def eligibility_vehicle(self) -> dict[str, Any]:
        return self.raw["eligibility"]["vehicle"]

    @property
    def high_value_review_threshold_eur(self) -> Decimal:
        return _dec(self.raw["eligibility"]["high_value_review_threshold_eur"])

    # vat / limits / approval ------------------------------------------------
    @property
    def vat_fallback_pct(self) -> Decimal:
        return _dec(self.raw["vat"]["fallback_pct"])

    @property
    def offer_absolute_max_eur(self) -> Decimal:
        return _dec(self.raw["offer_limit"]["absolute_mvp_max_eur"])

    @property
    def approval_limits(self) -> dict[str, dict[str, int]]:
        return self.raw["approval_limits"]


def load_policy(policy_id: str = "DE_PKW_V1") -> Policy:
    from app.db.mongo_settings import get_setting

    configured = get_setting("policy")
    if configured:
        raw = configured["data"]
        if raw.get("policy_id") != policy_id:
            raise KeyError(f"policy {policy_id} is not configured")
        return Policy(raw)
    path = _CONFIG_DIR / f"{policy_id.lower()}.json"
    with path.open(encoding="utf-8") as fh:
        return Policy(json.load(fh))
