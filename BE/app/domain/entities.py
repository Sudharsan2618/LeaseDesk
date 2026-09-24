"""Domain entities (docs/02). Storage-agnostic; JSONB mapping lives in db/schema.sql (docs/07).

MVP scope = B2B. B2C fields are modelled but the B2B path is what the engine exercises first.
Every *material* field is a ProvenanceValue so uncertainty is never silently treated as truth.
Engine outputs (Calculation/Assessment/Scoring) are plain payloads; they get wrapped in a
ResultEnvelope by the engine before being attached to an Offer/Scenario.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.core.types import (
    AssetAssessmentStatus,
    CustomerType,
    Language,
    ProvenanceValue,
    RedKind,
    ResidualConfidence,
    ResultEnvelope,
    RiskBand,
    ScoringPattern,
    SourceType,
)
from app.domain.reference import (
    DEFAULT_ASSET_CATEGORY,
    DEFAULT_BUSINESS_LINE,
    DEFAULT_CHANNEL,
    DEFAULT_PRODUCT,
)


def _ref_seed(value: str) -> ProvenanceValue[str]:
    """A selection value seeded from controlled reference data (the representative PKW product)."""
    return ProvenanceValue.established(value, "REF_V1", SourceType.CONTROLLED_REFERENCE_DATA)


# --------------------------------------------------------------------------- #
# Enums local to the domain                                                    #
# --------------------------------------------------------------------------- #
class WorkflowStatus(str, Enum):
    DRAFT = "DRAFT"
    UNDERSTANDING = "UNDERSTANDING"
    CONTEXT_REQUIRED = "CONTEXT_REQUIRED"
    CONTEXT_COMPLETE = "CONTEXT_COMPLETE"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    READY_FOR_CALCULATION = "READY_FOR_CALCULATION"
    CALCULATED = "CALCULATED"
    SCENARIOS_AVAILABLE = "SCENARIOS_AVAILABLE"
    SCENARIO_SELECTED = "SCENARIO_SELECTED"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    APPROVED = "APPROVED"
    RETURNED = "RETURNED"
    FINAL_VALIDATION = "FINAL_VALIDATION"
    OFFER_GENERATED = "OFFER_GENERATED"


class Readiness(str, Enum):
    COMPLETE = "COMPLETE"
    MISSING = "MISSING"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    INCONSISTENT = "INCONSISTENT"
    INVALID = "INVALID"


class FinalOutcome(str, Enum):
    READY = "READY"
    REQUIRES_ACTION = "REQUIRES_ACTION"
    BLOCKED = "BLOCKED"


class Role(str, Enum):
    SALES = "SALES"
    REVIEWER = "REVIEWER"
    APPROVER = "APPROVER"
    SENIOR_APPROVER = "SENIOR_APPROVER"
    POLICY_ADMIN = "POLICY_ADMIN"


# --------------------------------------------------------------------------- #
# Actors                                                                       #
# --------------------------------------------------------------------------- #
class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: str
    display_name: Optional[str] = None
    role: Role = Role.SALES


# --------------------------------------------------------------------------- #
# Vehicle / Asset (structure from EEA CO2 dataset; price seeded)               #
# --------------------------------------------------------------------------- #
class Vehicle(BaseModel):
    # EEA/KBA structural identity (each an ESTABLISHED ProvenanceValue in practice)
    make: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    commercial_name: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    variant: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    version: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    type_approval_number: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    hsn: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    tsn: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    vehicle_category: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)  # "M1"
    fuel_type: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    engine_power_kw: ProvenanceValue[int] = Field(default_factory=ProvenanceValue.missing)
    wltp_co2_g_km: ProvenanceValue[int] = Field(default_factory=ProvenanceValue.missing)

    colour: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)

    # commercial
    list_price_net: ProvenanceValue[Decimal] = Field(default_factory=ProvenanceValue.missing)   # residual base
    acquisition_price_net: ProvenanceValue[Decimal] = Field(default_factory=ProvenanceValue.missing)
    discount_net: ProvenanceValue[Decimal] = Field(default_factory=ProvenanceValue.missing)

    # used-vehicle fields (new -> VIN optional; used -> required)
    is_used: bool = False
    vin: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    registration_date: Optional[date] = None
    mileage_now_km: Optional[int] = None


# --------------------------------------------------------------------------- #
# Customer / Partner (B2B first)                                               #
# --------------------------------------------------------------------------- #
class SanctionsResult(BaseModel):
    match: bool
    hits: list[dict] = Field(default_factory=list)


class KycResult(BaseModel):
    identity_verified: bool
    representative_established: bool
    ubo_established: bool
    pep_match: bool
    kyc_status: str  # "COMPLETE" / "FAILED" / "PENDING"


class CreditResult(BaseModel):
    """Raw bureau output. It is an INPUT to scoring; it never sets the G/Y/R band itself."""
    credit_index: int                 # 0-100-ish quality proxy (mock)
    default_probability: Decimal
    recommended_limit_eur: Decimal
    financial_strength: int           # 0-100 (mock)
    company_age_years: int
    payment_history_score: int        # 0-100 (mock)
    negatives: list[str] = Field(default_factory=list)
    insolvency_flag: bool = False


class Customer(BaseModel):
    customer_type: CustomerType = CustomerType.B2B
    # B2B identity (each a ProvenanceValue in the Offer's customer_context)
    legal_name: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    register_number: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    legal_form: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    vat_id: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    address: ProvenanceValue[str] = Field(default_factory=ProvenanceValue.missing)
    # adapter caches
    sanctions: Optional[SanctionsResult] = None
    kyc: Optional[KycResult] = None
    credit: Optional[CreditResult] = None


# --------------------------------------------------------------------------- #
# Commercial requirement (per-offer user input)                                #
# --------------------------------------------------------------------------- #
class CommercialRequirement(BaseModel):
    term_months: ProvenanceValue[int] = Field(default_factory=ProvenanceValue.missing)
    annual_mileage_km: ProvenanceValue[int] = Field(default_factory=ProvenanceValue.missing)
    quantity: ProvenanceValue[int] = Field(default_factory=ProvenanceValue.missing)   # fleet size (N identical)
    special_payment_eur: ProvenanceValue[Decimal] = Field(default_factory=ProvenanceValue.missing)
    recurring_service_fee_eur: ProvenanceValue[Decimal] = Field(default_factory=ProvenanceValue.missing)
    financed_fees_eur: ProvenanceValue[Decimal] = Field(default_factory=ProvenanceValue.missing)
    # optional add-ons (full-service leasing) — priced deterministically from DE_PKW_V1
    service_maintenance: ProvenanceValue[bool] = Field(default_factory=ProvenanceValue.missing)
    service_tyres: ProvenanceValue[bool] = Field(default_factory=ProvenanceValue.missing)
    insurance: ProvenanceValue[bool] = Field(default_factory=ProvenanceValue.missing)
    target_monthly_rental_eur: ProvenanceValue[Decimal] = Field(default_factory=ProvenanceValue.missing)
    objective: Optional[str] = None  # e.g. "MINIMIZE_MONTHLY"


# --------------------------------------------------------------------------- #
# Engine result payloads (wrapped in ResultEnvelope by the engine)             #
# --------------------------------------------------------------------------- #
class AssessmentResult(BaseModel):
    residual_value_pct: Decimal
    residual_value_amount_eur: Decimal
    residual_confidence: ResidualConfidence
    assumptions: list[str] = Field(default_factory=list)


class CalculationResult(BaseModel):
    reference_rate_pct: Decimal
    funding_rate_pct: Decimal
    commercial_margin_pct: Decimal
    customer_finance_rate_pct: Decimal        # annual
    netcap_eur: Decimal                        # per vehicle
    residual_value_amount_eur: Decimal         # per vehicle
    pv_residual_eur: Decimal
    base_lease_eur: Decimal                     # per vehicle, finance only
    # add-ons (per vehicle, net)
    service_maintenance_eur: Decimal = Decimal("0")
    service_tyres_eur: Decimal = Decimal("0")
    insurance_eur: Decimal = Decimal("0")
    # per vehicle
    monthly_net_eur: Decimal                    # base_lease + services + insurance + recurring fee
    vat_pct: Decimal
    monthly_gross_eur: Decimal
    # fleet totals
    quantity: int = 1
    total_monthly_net_eur: Decimal = Decimal("0")
    total_monthly_gross_eur: Decimal = Decimal("0")
    contract_mileage_km: int                    # per vehicle
    mileage_settlement_per_km_eur: Decimal


class ScoringFactor(BaseModel):
    name: str
    weight: Decimal
    score_0_100: Decimal
    contribution: Decimal


class ScoringResult(BaseModel):
    mvp_risk_score: Decimal          # 0-100
    band: RiskBand
    red_kind: Optional[RedKind] = None
    pattern: ScoringPattern = ScoringPattern.AUTOMATIC   # spec §3.11 automatic vs manual scoring
    manual_reasons: list[str] = Field(default_factory=list)  # why the pattern is MANUAL (audit)
    factors: list[ScoringFactor] = Field(default_factory=list)
    hard_blocks: list[str] = Field(default_factory=list)


class AssetAssessmentOutcome(BaseModel):
    """The §3.7 asset-assessment outcome — a DISTINCT outcome from residual value (AssessmentResult).
    A required-but-UNAVAILABLE assessment prevents progression (FR-19/22, BR-13-style dependency)."""
    status: AssetAssessmentStatus
    asset_category: str
    mode: str = "external"           # external | internal | none
    service: Optional[str] = None    # the assessment dependency (e.g. ASSET_ASSESSMENT), when external
    result: Optional[str] = None     # PASS | CONCERNS | None (only when AVAILABLE)
    detail: Optional[str] = None
    assumptions: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Exceptions & validation                                                      #
# --------------------------------------------------------------------------- #
class Exception_(BaseModel):
    """Typed business exception (docs/05 §4). Named Exception_ to avoid shadowing builtins."""
    code: str
    severity: str                    # "GREEN" / "YELLOW" / "RED" / "" (info)
    blocking: bool
    override_allowed: bool
    required_role: Optional[str] = None
    next_action: Optional[str] = None
    detail: dict = Field(default_factory=dict)


class ValidationIssue(BaseModel):
    field: str
    type: str                        # MISSING / INVALID / INCONSISTENT / REQUIRES_CONFIRMATION
    blocking: bool = False
    why: Optional[str] = None
    what_must_happen: Optional[str] = None
    who_acts: Optional[str] = None


# --------------------------------------------------------------------------- #
# Scenario                                                                     #
# --------------------------------------------------------------------------- #
class Scenario(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    label: str
    term_months: int
    annual_mileage_km: int
    special_payment_eur: Decimal = Decimal("0")
    # service/insurance bundle this scenario was priced with (a scenario may vary the bundle, not just
    # the term — but only ever ADDS options the customer left open; explicit choices are honoured).
    service_maintenance: bool = False
    service_tyres: bool = False
    insurance: bool = False
    calculation: Optional[ResultEnvelope[CalculationResult]] = None
    assessment: Optional[ResultEnvelope[AssessmentResult]] = None
    scoring: Optional[ResultEnvelope[ScoringResult]] = None
    # budget fit (Phase 6) — set only when the offer carries a budget constraint; computed from the
    # engine's numbers (arranging, not pricing).
    fits_budget: Optional[bool] = None
    budget_metric_eur: Optional[Decimal] = None      # the figure compared against the budget
    budget_headroom_eur: Optional[Decimal] = None    # budget - metric (negative = over budget)


# --------------------------------------------------------------------------- #
# Offer (aggregate root)                                                        #
# --------------------------------------------------------------------------- #
class Offer(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    reference: str
    workflow_status: WorkflowStatus = WorkflowStatus.DRAFT
    readiness: Readiness = Readiness.MISSING
    customer_type: CustomerType = CustomerType.B2B
    language: Language = Language.EN
    policy_version: str = "DE_PKW_V1"
    created_by: Optional[UUID] = None

    # generic selection hierarchy (spec §3.4-3.6) — seeded to the representative PKW product;
    # Phase 2 wires real per-step selection + confirm gates. The product's policy_id drives the engine.
    channel: ProvenanceValue[str] = Field(default_factory=lambda: _ref_seed(DEFAULT_CHANNEL))
    business_line_key: ProvenanceValue[str] = Field(default_factory=lambda: _ref_seed(DEFAULT_BUSINESS_LINE))
    leasing_product_key: ProvenanceValue[str] = Field(default_factory=lambda: _ref_seed(DEFAULT_PRODUCT))
    asset_category_key: ProvenanceValue[str] = Field(default_factory=lambda: _ref_seed(DEFAULT_ASSET_CATEGORY))

    customer: Customer = Field(default_factory=Customer)
    vehicle: Vehicle = Field(default_factory=Vehicle)
    commercial: CommercialRequirement = Field(default_factory=CommercialRequirement)

    calculation: Optional[ResultEnvelope[CalculationResult]] = None
    assessment: Optional[ResultEnvelope[AssessmentResult]] = None          # residual value (§3.8)
    asset_assessment: Optional[ResultEnvelope[AssetAssessmentOutcome]] = None  # §3.7 asset assessment
    scoring: Optional[ResultEnvelope[ScoringResult]] = None

    scenarios: list[Scenario] = Field(default_factory=list)
    selected_scenario_id: Optional[UUID] = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    exceptions: list[Exception_] = Field(default_factory=list)
    agent_context: dict = Field(default_factory=dict)   # LLM extraction + explanations (non-authoritative)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
