"""Controlled Offer Reference Data — the generic domain taxonomy (spec §3.5–3.6, §5.5).

This is the layer that makes the system **asset-agnostic**: Business Line → Leasing Product →
Asset Category, all driven by `app/config/reference_data.json`. A Leasing Product points at a
`policy_id` (e.g. DE_PKW_V1) that carries its Offer Parameters and calculation inputs, so the
deterministic engine stays unchanged — only *where the parameters come from* is generalized.

The Agent READS this data to know which rules/params/attributes apply; it never defines or modifies
it (BR-08/09). PKW is active and fully wired; Equipment/NFZ/ITK are declared but `planned`.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class AssetAttribute(BaseModel):
    key: str
    label_en: str
    label_de: str = ""
    type: str = "string"          # string | enum | int | money
    required: bool = False
    filterable: bool = False


class AssessmentConfig(BaseModel):
    """§3.7 asset-assessment policy for a category: whether it is required, and how it is obtained
    (external assessment service for applicable object types; ITK handled internally). Reference data
    — the Agent reads it, never defines it."""
    required: bool = False
    mode: str = "external"         # external | internal
    service: str = "ASSET_ASSESSMENT"   # the external dependency name (when mode == external)


class AssetCategory(BaseModel):
    key: str                       # PKW | Equipment | NFZ | ITK
    name_en: str
    name_de: str = ""
    status: str = "active"         # active | planned
    attribute_schema: list[AssetAttribute] = Field(default_factory=list)
    assessment: AssessmentConfig = Field(default_factory=AssessmentConfig)

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def filters(self) -> list[AssetAttribute]:
        return [a for a in self.attribute_schema if a.filterable]


class LeasingProduct(BaseModel):
    key: str
    name_en: str
    name_de: str = ""
    business_line: str
    asset_category: str
    status: str = "active"
    policy_id: str                 # → app/config/<policy_id>.json (Offer Parameters)
    description_en: str = ""
    description_de: str = ""

    @property
    def is_active(self) -> bool:
        return self.status == "active"


class BusinessLine(BaseModel):
    key: str
    name_en: str
    name_de: str = ""
    status: str = "active"
    products: list[str] = Field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.status == "active"


class Channel(BaseModel):
    key: str                       # internal_sales | partner_sales | credit_partner
    name_en: str
    name_de: str = ""
    status: str = "active"         # active | stub
    partner_kind: str = "business_partner"  # business_partner | offer_partner


class ReferenceData(BaseModel):
    """Typed view over reference_data.json with lookup helpers."""
    version: str
    business_lines: list[BusinessLine] = Field(default_factory=list)
    leasing_products: list[LeasingProduct] = Field(default_factory=list)
    asset_categories: list[AssetCategory] = Field(default_factory=list)
    channels: list[Channel] = Field(default_factory=list)

    # ---- lookups (return None when absent; callers surface a validation issue) ----
    def business_line(self, key: str) -> Optional[BusinessLine]:
        return next((b for b in self.business_lines if b.key == key), None)

    def product(self, key: str) -> Optional[LeasingProduct]:
        return next((p for p in self.leasing_products if p.key == key), None)

    def asset_category(self, key: str) -> Optional[AssetCategory]:
        return next((c for c in self.asset_categories if c.key == key), None)

    def channel(self, key: str) -> Optional[Channel]:
        return next((c for c in self.channels if c.key == key), None)

    def products_for(self, business_line_key: str) -> list[LeasingProduct]:
        return [p for p in self.leasing_products if p.business_line == business_line_key]

    def active_business_lines(self) -> list[BusinessLine]:
        return [b for b in self.business_lines if b.is_active]

    def active_products(self) -> list[LeasingProduct]:
        return [p for p in self.leasing_products if p.is_active]

    def policy_id_for_product(self, product_key: str) -> Optional[str]:
        p = self.product(product_key)
        return p.policy_id if p else None


@lru_cache(maxsize=1)
def load_reference_data() -> ReferenceData:
    path = _CONFIG_DIR / "reference_data.json"
    with path.open(encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)
    raw.pop("_note", None)
    return ReferenceData.model_validate(raw)


# Seed defaults for the representative PKW scenario (spec §9.5) — used so existing PKW flows keep
# working while the selection hierarchy (Phase 2) is wired in.
DEFAULT_CHANNEL = "internal_sales"
DEFAULT_BUSINESS_LINE = "mobility"
DEFAULT_PRODUCT = "pkw_km_leasing"
DEFAULT_ASSET_CATEGORY = "PKW"
