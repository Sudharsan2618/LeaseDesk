"""Assemble a B2B Offer from primitive inputs + the fixture catalogues.

This is the deterministic "Assemble" step done without AI: vehicle structure via the VEHICLE
adapter, customer identity via the company fixture, and the user's commercial requirement wrapped
as CONFIRMED ProvenanceValues. Used by tests now and reusable by the API layer later.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import uuid4

from app.core.types import CustomerType, Language, ProvenanceValue, SourceType
from app.domain.entities import CommercialRequirement, Customer, Offer
from app.integration._fixtures import load
from app.integration.base import AdapterRegistry

def _pv(value):
    return ProvenanceValue.confirmed(value, source="USER")


def build_b2b_offer(
    registry: AdapterRegistry,
    *,
    vehicle_key: str,
    register_number: str,
    term_months: int,
    annual_mileage_km: int,
    quantity: int = 1,
    special_payment_eur: Decimal = Decimal("0"),
    recurring_service_fee_eur: Decimal = Decimal("0"),
    financed_fees_eur: Decimal = Decimal("0"),
    discount_net_eur: Decimal = Decimal("0"),
    service_maintenance: bool = False,
    service_tyres: bool = False,
    insurance: bool = False,
    colour: Optional[str] = None,
    language: Language = Language.EN,
    reference: Optional[str] = None,
) -> Offer:
    # vehicle structure (ESTABLISHED) via adapter
    vehicle = registry.get("VEHICLE").fetch({"key": vehicle_key})
    if colour:
        vehicle.colour = ProvenanceValue.confirmed(colour, source="USER")
    if discount_net_eur:
        vehicle.discount_net = ProvenanceValue.established(
            discount_net_eur, source="USER", source_type=SourceType.USER_INPUT)
        acq = vehicle.list_price_net.value - discount_net_eur
        vehicle.acquisition_price_net = ProvenanceValue.confirmed(acq, source="USER")

    # customer identity from the company fixture
    company = load("companies.json")["companies"].get(register_number, {})
    customer = Customer(
        customer_type=CustomerType.B2B,
        legal_name=ProvenanceValue.established(company.get("legal_name", ""), "REGISTER",
                                               SourceType.OPEN_OFFICIAL),
        register_number=ProvenanceValue.confirmed(register_number, "USER"),
        legal_form=ProvenanceValue.established(company.get("legal_form", ""), "REGISTER",
                                               SourceType.OPEN_OFFICIAL),
        vat_id=ProvenanceValue.established(company.get("vat_id", ""), "VIES",
                                           SourceType.OPEN_OFFICIAL),
        address=ProvenanceValue.established(company.get("address", ""), "REGISTER",
                                            SourceType.OPEN_OFFICIAL),
    )

    commercial = CommercialRequirement(
        term_months=_pv(term_months),
        annual_mileage_km=_pv(annual_mileage_km),
        quantity=_pv(int(quantity)),
        special_payment_eur=_pv(special_payment_eur),
        recurring_service_fee_eur=_pv(recurring_service_fee_eur),
        financed_fees_eur=_pv(financed_fees_eur),
        service_maintenance=_pv(bool(service_maintenance)),
        service_tyres=_pv(bool(service_tyres)),
        insurance=_pv(bool(insurance)),
    )

    return Offer(
        reference=reference or f"OFF-{uuid4().hex[:8].upper()}",
        customer_type=CustomerType.B2B,
        language=language,
        customer=customer,
        vehicle=vehicle,
        commercial=commercial,
    )
