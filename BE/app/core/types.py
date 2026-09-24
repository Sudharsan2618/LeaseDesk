"""Core building blocks shared by every layer.

The two envelopes here are the contract for the whole system (see docs/02):
- ProvenanceValue[T]  wraps every *material data field*   -> "where did this fact come from?"
- ResultEnvelope[T]   wraps every *engine computation*     -> "which policy produced this, from what?"

No AI, no I/O here. Pure, deterministic, serialisable types.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


# --------------------------------------------------------------------------- #
# Enumerations                                                                 #
# --------------------------------------------------------------------------- #
class FieldStatus(str, Enum):
    """Per-field validation status carried on every ProvenanceValue (docs/02 §1.1)."""

    ESTABLISHED = "ESTABLISHED"            # authoritative source (open/official, provider, reference data)
    CONFIRMED = "CONFIRMED"                # a human explicitly confirmed it
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    INFERRED = "INFERRED"                  # agent-proposed (always carries confidence + needs confirmation)
    MISSING = "MISSING"
    INVALID = "INVALID"
    INCONSISTENT = "INCONSISTENT"


class SourceType(str, Enum):
    USER_INPUT = "USER_INPUT"
    AGENT_INFERENCE = "AGENT_INFERENCE"
    OPEN_OFFICIAL = "OPEN_OFFICIAL"
    EXTERNAL_PROVIDER = "EXTERNAL_PROVIDER"
    CONTROLLED_REFERENCE_DATA = "CONTROLLED_REFERENCE_DATA"
    SEED = "SEED"                          # seeded value where no free public source exists


class CustomerType(str, Enum):
    B2B = "B2B"
    B2C = "B2C"


class Language(str, Enum):
    EN = "en"
    DE = "de"


class RiskBand(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class RedKind(str, Enum):
    ECONOMIC = "ECONOMIC"
    COMPLIANCE = "COMPLIANCE"


class ScoringPattern(str, Enum):
    """The two credit-scoring patterns (spec §3.11). AUTOMATIC = the offer parameters match the
    predefined automatic process and are scored without intervention; MANUAL = parameters fall
    outside that envelope and the outcome requires manual review before it can proceed. The band
    (GREEN/YELLOW/RED) is still produced either way; the pattern says whether a human must intervene."""
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"


class AssetAssessmentStatus(str, Enum):
    """Outcome availability for the §3.7 asset-assessment dependency. AVAILABLE = the assessment
    was obtained; UNAVAILABLE = a required assessment dependency could not be reached and therefore
    prevents progression (FR-22); NOT_REQUIRED = the asset category needs no assessment."""
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_REQUIRED = "NOT_REQUIRED"


class ResidualConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# Statuses the engines are allowed to consume. Anything else must be resolved first.
CONSUMABLE_STATUSES = frozenset({FieldStatus.ESTABLISHED, FieldStatus.CONFIRMED})


# The four info states the target experience shows on every field (spec §7.6, FR-14).
def info_state(status: "FieldStatus") -> str:
    """Collapse the internal FieldStatus onto the four UI states the workbench displays."""
    if status == FieldStatus.ESTABLISHED:
        return "established"                 # ✓ from an authoritative source
    if status == FieldStatus.CONFIRMED:
        return "confirmed"                   # ✓ a human confirmed it
    if status in (FieldStatus.REQUIRES_CONFIRMATION, FieldStatus.INFERRED):
        return "requires_confirmation"       # ◐ proposed / unsure — needs a human yes
    return "needs_action"                    # ⚠ MISSING / INVALID / INCONSISTENT


# --------------------------------------------------------------------------- #
# ProvenanceValue                                                              #
# --------------------------------------------------------------------------- #
class ProvenanceValue(BaseModel, Generic[T]):
    """A material data field plus its origin. Never store a bare value on an Offer."""

    model_config = ConfigDict(use_enum_values=False)

    value: Optional[T] = None
    status: FieldStatus = FieldStatus.MISSING
    source: Optional[str] = None                 # "USER", "EEA", "BUNDESBANK", "DE_PKW_V1", ...
    source_type: Optional[SourceType] = None
    confidence: Optional[float] = None           # only meaningful when INFERRED
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_consumable(self) -> bool:
        """True iff an engine may consume this field (ESTABLISHED/CONFIRMED with a value)."""
        return self.value is not None and self.status in CONSUMABLE_STATUSES

    # -- convenience constructors -------------------------------------------- #
    @classmethod
    def established(cls, value: T, source: str, source_type: SourceType) -> "ProvenanceValue[T]":
        return cls(value=value, status=FieldStatus.ESTABLISHED, source=source, source_type=source_type)

    @classmethod
    def confirmed(cls, value: T, source: str = "USER") -> "ProvenanceValue[T]":
        return cls(value=value, status=FieldStatus.CONFIRMED, source=source, source_type=SourceType.USER_INPUT)

    @classmethod
    def inferred(cls, value: T, confidence: float, source: str = "AGENT") -> "ProvenanceValue[T]":
        return cls(value=value, status=FieldStatus.INFERRED, source=source,
                   source_type=SourceType.AGENT_INFERENCE, confidence=confidence)

    @classmethod
    def missing(cls) -> "ProvenanceValue[T]":
        return cls(value=None, status=FieldStatus.MISSING)


# --------------------------------------------------------------------------- #
# ResultEnvelope                                                               #
# --------------------------------------------------------------------------- #
def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    raise TypeError(f"not serialisable: {type(obj)!r}")


def inputs_digest(payload: Any) -> str:
    """Deterministic hash of the exact inputs -> makes engine results reproducible/cacheable."""
    blob = json.dumps(payload, default=_json_default, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ResultEnvelope(BaseModel, Generic[T]):
    """An engine output plus the policy provenance needed to explain and audit it."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    value: T
    engine: str
    policies: dict[str, Optional[str]] = Field(default_factory=dict)
    inputs_digest: str
    assumptions: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
