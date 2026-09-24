"""Asset-assessment engine (spec §3.7, FR-19/22). Produces a DISTINCT outcome from residual value:
whether the selected asset's assessment was obtained, and — when a required assessment dependency is
unavailable — signals that progression is prevented.

The category's assessment policy (required / external vs internal / which service) is controlled
reference data, resolved from `reference_data.json`; the outcome itself comes from the adapter (or is
NOT_REQUIRED). The Agent never fabricates a pass and never decides requirement.
"""
from __future__ import annotations

from app.core.policy import Policy
from app.core.types import AssetAssessmentStatus, ResultEnvelope, inputs_digest
from app.domain.entities import AssetAssessmentOutcome
from app.domain.reference import ReferenceData, load_reference_data
from app.integration.base import AdapterRegistry, ExternalServiceUnavailable

_ENGINE_KEY = "asset_assessment"


def run_asset_assessment(
    policy: Policy,
    registry: AdapterRegistry,
    *,
    asset_category_key: str,
    attributes: dict | None = None,
    reference: ReferenceData | None = None,
) -> ResultEnvelope[AssetAssessmentOutcome]:
    """Resolve the category's assessment policy from reference data, then obtain the outcome.

    - not required (or unknown category) -> NOT_REQUIRED (non-blocking).
    - internal mode -> assessed internally, AVAILABLE/PASS (no external dependency).
    - external mode -> call the assessment service; on ExternalServiceUnavailable -> UNAVAILABLE
      (the orchestrator turns that into a blocking exception, FR-22).
    """
    ref = reference or load_reference_data()
    category = ref.asset_category(asset_category_key)
    cfg = category.assessment if category else None
    attributes = attributes or {}

    if cfg is None or not cfg.required:
        return _wrap(policy, AssetAssessmentOutcome(
            status=AssetAssessmentStatus.NOT_REQUIRED, asset_category=asset_category_key,
            mode="none", detail="no assessment required for this category",
        ), {"asset_category": asset_category_key, "required": False})

    if cfg.mode == "internal":
        return _wrap(policy, AssetAssessmentOutcome(
            status=AssetAssessmentStatus.AVAILABLE, asset_category=asset_category_key,
            mode="internal", result="PASS", detail="assessed internally",
            assumptions=["internal_assessment"],
        ), {"asset_category": asset_category_key, "mode": "internal"})

    # external mode -> call the dependency
    try:
        resp = registry.get(cfg.service).fetch(
            {"asset_category": asset_category_key, "mode": "external", "attributes": attributes})
        return _wrap(policy, AssetAssessmentOutcome(
            status=AssetAssessmentStatus.AVAILABLE, asset_category=asset_category_key,
            mode="external", service=cfg.service, result=resp.get("result"),
            detail=resp.get("detail"), assumptions=["external_assessment"],
        ), {"asset_category": asset_category_key, "mode": "external", "result": resp.get("result")})
    except ExternalServiceUnavailable as e:
        return _wrap(policy, AssetAssessmentOutcome(
            status=AssetAssessmentStatus.UNAVAILABLE, asset_category=asset_category_key,
            mode="external", service=cfg.service, detail=str(e),
        ), {"asset_category": asset_category_key, "mode": "external", "unavailable": True})


def _wrap(policy: Policy, payload: AssetAssessmentOutcome, digest_inputs: dict
          ) -> ResultEnvelope[AssetAssessmentOutcome]:
    engine = policy.engine_versions.get(_ENGINE_KEY, "DE_ASSET_ASSESS_V1")
    return ResultEnvelope[AssetAssessmentOutcome](
        value=payload, engine=engine,
        policies={"asset_assessment_policy": engine},
        inputs_digest=inputs_digest(digest_inputs),
        assumptions=payload.assumptions,
    )
