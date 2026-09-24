"""Sanctions screening adapter (EU consolidated list / OpenSanctions). MOCK reads the fixture."""
from __future__ import annotations

from app.core.types import SourceType
from app.domain.entities import SanctionsResult
from app.integration._fixtures import load
from app.integration.base import AdapterMode, ExternalServiceUnavailable


class SanctionsAdapter:
    name = "SANCTIONS"
    source_type = SourceType.OPEN_OFFICIAL

    def __init__(self, mode: AdapterMode = AdapterMode.MOCK) -> None:
        self.mode = mode

    def fetch(self, request: dict) -> SanctionsResult:
        """request = {"register_number": "HRB-4004", "names": [...]}. Returns SanctionsResult."""
        if self.mode is not AdapterMode.MOCK:
            raise ExternalServiceUnavailable("only MOCK mode wired in Phase 1")
        reg = request.get("register_number")
        c = load("companies.json")["companies"].get(reg)
        if c is None:
            return SanctionsResult(match=False, hits=[])
        s = c["sanctions"]
        return SanctionsResult(match=s["match"], hits=s["hits"])
