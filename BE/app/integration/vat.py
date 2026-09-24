"""VAT-rate adapter (EU TEDB). MOCK returns Germany standard 19%."""
from __future__ import annotations

from decimal import Decimal

from app.core.types import ProvenanceValue, SourceType
from app.integration.base import AdapterMode, ExternalServiceUnavailable


class VatAdapter:
    name = "VAT"
    source_type = SourceType.OPEN_OFFICIAL

    def __init__(self, mode: AdapterMode = AdapterMode.MOCK) -> None:
        self.mode = mode

    def fetch(self, request: dict | None = None) -> ProvenanceValue[Decimal]:
        """request = {"country": "DE", "date": "..."} (ignored in MOCK). Returns VAT %."""
        if self.mode is not AdapterMode.MOCK:
            raise ExternalServiceUnavailable("only MOCK mode wired in Phase 1")
        return ProvenanceValue.established(
            Decimal("19"), source="EU_TEDB", source_type=SourceType.OPEN_OFFICIAL
        )
