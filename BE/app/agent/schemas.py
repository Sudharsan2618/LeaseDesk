"""Structured shapes the LLM extracts. These are PROPOSALS (INFERRED) — never authoritative.

The intent is a FLEXIBLE schema (doc 13 §3.1): known slots + open `asset_filters` (any asset
attribute the caller mentions) + `constraints` (budget / caps that shape scenarios, not direct
fields) + `ambiguities` (things the user must confirm — BR-03). This lets the agent handle *any*
phrasing, e.g. "4-seater 30 insured cars, budget $300k", rather than a fixed set of phrases.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Constraint(BaseModel):
    """A soft requirement that shapes scenario generation rather than a single offer field."""
    kind: str = Field(description="budget | monthly_cap | delivery | other")
    value: Optional[float] = Field(None, description="numeric value if any, e.g. 300000")
    currency: Optional[str] = Field(None, description="currency as stated, e.g. '$', 'EUR' — leave as written")
    basis: Optional[str] = Field(None, description="total | monthly | per_vehicle | unknown")
    note: Optional[str] = Field(None, description="free-text detail if it doesn't fit above")


class Ambiguity(BaseModel):
    """Something you were unsure about; the user must confirm before it is used (BR-03)."""
    field: str = Field(description="the field/topic in question, e.g. 'budget', 'currency', 'product'")
    reason: str = Field(description="why it is ambiguous")
    options: list[str] = Field(default_factory=list, description="candidate interpretations, if any")


class ExtractedIntent(BaseModel):
    """What the agent parses from a free-text leasing request. All optional; missing => ask."""
    make: Optional[str] = Field(None, description="vehicle manufacturer, e.g. BMW")
    model: Optional[str] = Field(None, description="commercial model name, e.g. X1")
    term_months: Optional[int] = Field(None, description="lease term in months")
    annual_mileage_km: Optional[int] = Field(None, description="annual mileage in km")
    quantity: Optional[int] = Field(None, description="number of identical vehicles (fleet size); 1 if not stated")
    special_payment_eur: Optional[float] = Field(None, description="down payment / Sonderzahlung in EUR")
    service_maintenance: Optional[bool] = Field(None, description="true if they want maintenance/servicing included")
    service_tyres: Optional[bool] = Field(None, description="true if they want tyres included")
    insurance: Optional[bool] = Field(None, description="true if they want insurance included")
    colour: Optional[str] = Field(None, description="requested vehicle colour, if stated")
    company_hint: Optional[str] = Field(None, description="customer company name or register number")
    objective: Optional[str] = Field(None, description="e.g. MINIMIZE_MONTHLY if they want low monthly")
    # flexible extensions (doc 13 §3.1)
    asset_filters: dict[str, str] = Field(
        default_factory=dict,
        description="asset attribute filters mentioned, values as strings, "
                    "e.g. {'seats':'4','fuel_type':'ELECTRIC','body_type':'SUV'}")
    constraints: list[Constraint] = Field(
        default_factory=list,
        description="budget or other soft constraints that shape scenarios (not a single field)")
    ambiguities: list[Ambiguity] = Field(
        default_factory=list,
        description="anything unclear the user must confirm — e.g. budget currency/basis, which product")
    confidence: float = Field(0.5, ge=0, le=1, description="overall extraction confidence 0..1")
