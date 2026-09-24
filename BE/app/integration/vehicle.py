"""Vehicle structure adapter. MOCK returns EEA-shaped structure + SEEDED list price (docs/03 §3.1)."""
from __future__ import annotations

from decimal import Decimal

from app.core.types import ProvenanceValue, SourceType
from app.domain.entities import Vehicle
from app.integration._fixtures import load
from app.integration.base import AdapterMode, ExternalServiceUnavailable, SourceType as _ST  # noqa: F401


class VehicleAdapter:
    name = "VEHICLE"
    source_type = SourceType.OPEN_OFFICIAL

    def __init__(self, mode: AdapterMode = AdapterMode.MOCK) -> None:
        self.mode = mode

    def fetch(self, request: dict) -> Vehicle:
        """request = {"key": "bmw-x1-sdrive18i"}. Returns a Vehicle with structure ESTABLISHED
        from EEA/KBA and list_price_net marked SEED."""
        if self.mode is not AdapterMode.MOCK:
            raise ExternalServiceUnavailable("only MOCK mode wired in Phase 1")

        key = request["key"]
        row = next((v for v in load("vehicles.json")["vehicles"] if v["key"] == key), None)
        if row is None:
            raise ExternalServiceUnavailable(f"vehicle {key!r} not found in fixture")

        def est(val, src="EEA", st=SourceType.OPEN_OFFICIAL):
            return ProvenanceValue.established(val, source=src, source_type=st)

        return Vehicle(
            make=est(row["make"]),
            commercial_name=est(row["commercial_name"]),
            variant=est(row["variant"]),
            version=est(row.get("version", row.get("variant", ""))),
            type_approval_number=est(row["type_approval_number"]),
            hsn=est(row["hsn"], src="KBA"),
            tsn=est(row["tsn"], src="KBA"),
            vehicle_category=est(row["vehicle_category"]),
            fuel_type=est(row["fuel_type"]),
            engine_power_kw=est(row["engine_power_kw"]),
            wltp_co2_g_km=est(row["wltp_co2_g_km"]),
            list_price_net=est(Decimal(row["list_price_net"]), src="SEED", st=SourceType.SEED),
            acquisition_price_net=est(Decimal(row["list_price_net"]), src="SEED", st=SourceType.SEED),
            discount_net=ProvenanceValue.established(Decimal("0"), source="SEED", source_type=SourceType.SEED),
        )
