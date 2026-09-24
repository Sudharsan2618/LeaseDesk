"""Credit bureau adapter (CRIF/Creditsafe sandbox / deterministic mock).

The output is a RAW bureau result. It is an INPUT to the MVP risk engine; it never sets the
GREEN/YELLOW/RED band itself (docs/03 §4). MOCK reads the fixture persona.
"""
from __future__ import annotations

from decimal import Decimal

from app.core.types import SourceType
from app.domain.entities import CreditResult
from app.integration._fixtures import load
from app.integration.base import AdapterMode, ExternalServiceUnavailable


class CreditAdapter:
    name = "CREDIT"
    source_type = SourceType.EXTERNAL_PROVIDER

    def __init__(self, mode: AdapterMode = AdapterMode.MOCK) -> None:
        self.mode = mode

    def fetch(self, request: dict) -> CreditResult:
        """request = {"register_number": "HRB-1001", "requested_exposure_eur": ...}."""
        if self.mode is not AdapterMode.MOCK:
            raise ExternalServiceUnavailable("only MOCK mode wired in Phase 1")
        reg = request.get("register_number")
        c = load("companies.json")["companies"].get(reg)
        if c is None:
            raise ExternalServiceUnavailable(f"company {reg!r} not found in fixture")
        cr = dict(c["credit"])
        cr["default_probability"] = Decimal(cr["default_probability"])
        cr["recommended_limit_eur"] = Decimal(cr["recommended_limit_eur"])
        return CreditResult(**cr)
