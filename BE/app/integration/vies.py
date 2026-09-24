"""VAT-ID validation adapter (VIES). MOCK validates the DE format + looks up the fixture company."""
from __future__ import annotations

import re

from app.core.types import SourceType
from app.integration._fixtures import load
from app.integration.base import AdapterMode, ExternalServiceUnavailable

_DE_VAT = re.compile(r"^DE\d{9}$")


class ViesAdapter:
    name = "VIES"
    source_type = SourceType.OPEN_OFFICIAL

    def __init__(self, mode: AdapterMode = AdapterMode.MOCK) -> None:
        self.mode = mode

    def fetch(self, request: dict) -> dict:
        """request = {"vat_id": "DE100000001"}. Returns {valid, name?, address?}."""
        if self.mode is not AdapterMode.MOCK:
            raise ExternalServiceUnavailable("only MOCK mode wired in Phase 1")
        vat_id = (request.get("vat_id") or "").strip().upper()
        if not _DE_VAT.match(vat_id):
            return {"valid": False}
        for c in load("companies.json")["companies"].values():
            if c["vat_id"].upper() == vat_id:
                return {"valid": True, "name": c["legal_name"], "address": c["address"]}
        # well-formed but unknown -> valid format, no identity data
        return {"valid": True}
