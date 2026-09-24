"""Reference interest-rate adapter (Bundesbank/ECB SDMX). MOCK returns a fixed series value.

IMPORTANT: this is a *reference* rate only. The funding policy adds spreads on top (docs/04 §2).
"""
from __future__ import annotations

from decimal import Decimal

from app.core.types import ProvenanceValue, SourceType
from app.integration.base import AdapterMode, ExternalServiceUnavailable


class ReferenceRateAdapter:
    name = "REFERENCE_RATE"
    source_type = SourceType.OPEN_OFFICIAL

    # Seeded reference value for repeatable demos; LIVE mode will pull the SDMX series.
    _MOCK_RATE_PCT = Decimal("3.00")

    def __init__(self, mode: AdapterMode = AdapterMode.MOCK) -> None:
        self.mode = mode

    def fetch(self, request: dict | None = None) -> ProvenanceValue[Decimal]:
        """request = {"as_of": "2026-09-23"} (ignored in MOCK). Returns reference_rate %."""
        if self.mode is not AdapterMode.MOCK:
            raise ExternalServiceUnavailable("only MOCK mode wired in Phase 1")
        return ProvenanceValue.established(
            self._MOCK_RATE_PCT, source="BUNDESBANK", source_type=SourceType.OPEN_OFFICIAL
        )
