"""Adapter contract + registry (docs/03).

Every external source is reached through a SourceAdapter with a LIVE/SANDBOX/MOCK mode. Switching
mode must NOT change the response schema or the workflow -- only the data's origin (recorded in
provenance). Phase 1 ships MOCK adapters (deterministic fixtures); LIVE/SANDBOX are wired later.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Protocol, runtime_checkable

from app.core.types import SourceType


class AdapterMode(str, Enum):
    LIVE = "LIVE"
    SANDBOX = "SANDBOX"
    MOCK = "MOCK"


class ExternalServiceUnavailable(RuntimeError):
    """Raised by an adapter when it cannot produce a value. The engine records
    EXTERNAL_SERVICE_UNAVAILABLE and does NOT fabricate a value."""


@runtime_checkable
class SourceAdapter(Protocol):
    name: str
    source_type: SourceType
    mode: AdapterMode

    def fetch(self, request: Any) -> Any: ...


class AdapterRegistry:
    """Keyed by adapter name. Engines resolve adapters here so sources are swappable."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[AdapterMode], SourceAdapter]] = {}
        self._default_mode = AdapterMode.MOCK

    def register(self, name: str, factory: Callable[[AdapterMode], SourceAdapter]) -> None:
        self._factories[name] = factory

    def set_default_mode(self, mode: AdapterMode) -> None:
        self._default_mode = mode

    def get(self, name: str, mode: AdapterMode | None = None) -> SourceAdapter:
        if name not in self._factories:
            raise KeyError(f"no adapter registered for {name!r}")
        return self._factories[name](mode or self._default_mode)


def build_default_registry(mode: AdapterMode = AdapterMode.MOCK) -> AdapterRegistry:
    """Wire every Phase-1 adapter in the given mode (MOCK by default)."""
    from app.integration import (
        asset_assessment, credit, kyc, reference_rate, sanctions, vat, vehicle, vies,
    )

    reg = AdapterRegistry()
    reg.set_default_mode(mode)
    reg.register("VEHICLE", vehicle.VehicleAdapter)
    reg.register("REFERENCE_RATE", reference_rate.ReferenceRateAdapter)
    reg.register("VAT", vat.VatAdapter)
    reg.register("VIES", vies.ViesAdapter)
    reg.register("SANCTIONS", sanctions.SanctionsAdapter)
    reg.register("KYC", kyc.KycAdapter)
    reg.register("CREDIT", credit.CreditAdapter)
    reg.register("ASSET_ASSESSMENT", asset_assessment.AssetAssessmentAdapter)
    return reg
