"""KYC adapter (CRIF UAT sandbox / fixture). MOCK reads the fixture persona (docs/03 §3.5)."""
from __future__ import annotations

from app.core.types import SourceType
from app.domain.entities import KycResult
from app.integration._fixtures import load
from app.integration.base import AdapterMode, ExternalServiceUnavailable


class KycAdapter:
    name = "KYC"
    source_type = SourceType.EXTERNAL_PROVIDER

    def __init__(self, mode: AdapterMode = AdapterMode.MOCK) -> None:
        self.mode = mode

    def fetch(self, request: dict) -> KycResult:
        """request = {"register_number": "HRB-1001"}. Returns KycResult."""
        if self.mode is not AdapterMode.MOCK:
            raise ExternalServiceUnavailable("only MOCK mode wired in Phase 1")
        reg = request.get("register_number")
        c = load("companies.json")["companies"].get(reg)
        if c is None:
            raise ExternalServiceUnavailable(f"company {reg!r} not found in fixture")
        return KycResult(**c["kyc"])
