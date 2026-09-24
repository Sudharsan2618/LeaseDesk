"""Phase 5 — Scoring (G/Y/R + auto/manual patterns) & asset assessment (spec §3.7, §3.11-3.12).

Deterministic, no AI, no DB. Proves:
  5.1 scoring returns a band AND an auto-vs-manual pattern driven by the policy envelope;
  5.2 Green proceeds · Yellow/Manual -> Requires Action · compliance-Red blocks;
  5.3 asset assessment is a distinct outcome; an unavailable required dependency blocks progression;
  5.4 the engine records the outcome — the pattern/assessment are established facts, not agent guesses.
"""
from __future__ import annotations

import pytest

from app.core.policy import load_policy
from app.core.types import AssetAssessmentStatus, RedKind, RiskBand, ScoringPattern
from app.domain.entities import FinalOutcome
from app.engine.orchestrator import compute_final_outcome, run_pipeline
from app.integration.base import AdapterMode, ExternalServiceUnavailable, build_default_registry
from app.service.offer_factory import build_b2b_offer

POLICY = load_policy("DE_PKW_V1")


@pytest.fixture()
def registry():
    return build_default_registry(AdapterMode.MOCK)


def _offer(registry, **kw):
    defaults = dict(vehicle_key="bmw-x1-sdrive18i", register_number="HRB-1001",
                    term_months=36, annual_mileage_km=20000)
    defaults.update(kw)
    return build_b2b_offer(registry, **defaults)


# ── 5.1 scoring pattern: automatic vs manual ────────────────────────────────────
def test_small_offer_scores_automatically(registry):
    offer = run_pipeline(_offer(registry), registry, POLICY)
    assert offer.scoring.value.band is RiskBand.GREEN
    assert offer.scoring.value.pattern is ScoringPattern.AUTOMATIC
    assert offer.scoring.value.manual_reasons == []


def test_fleet_over_envelope_forces_manual_pattern(registry):
    # 30 units x 37.8k acquisition = 1.13M exposure, and quantity 30 > 10 -> outside the envelope.
    offer = run_pipeline(_offer(registry, quantity=30), registry, POLICY)
    s = offer.scoring.value
    assert s.pattern is ScoringPattern.MANUAL
    assert any("exposure" in r for r in s.manual_reasons)
    assert any("quantity" in r for r in s.manual_reasons)


def test_high_unit_price_forces_manual_pattern(registry):
    # Porsche Taycan list 104.6k > 100k automatic-envelope unit price cap.
    offer = run_pipeline(_offer(registry, vehicle_key="porsche-taycan"), registry, POLICY)
    assert offer.scoring.value.pattern is ScoringPattern.MANUAL
    assert any("unit price" in r for r in offer.scoring.value.manual_reasons)


# ── 5.2 routing: green proceeds · manual/yellow -> requires action · red blocks ──
def test_green_automatic_is_ready_and_priced(registry):
    offer = run_pipeline(_offer(registry), registry, POLICY)
    assert offer.calculation is not None
    assert compute_final_outcome(offer) is FinalOutcome.READY


def test_manual_pattern_prices_but_requires_action(registry):
    offer = run_pipeline(_offer(registry, quantity=30), registry, POLICY)
    # a manual scoring pattern still prices (band is GREEN) but must be reviewed by a human
    assert offer.calculation is not None
    assert compute_final_outcome(offer) is FinalOutcome.REQUIRES_ACTION
    codes = [e.code for e in offer.exceptions]
    assert "SCORING_MANUAL_REVIEW" in codes
    manual = next(e for e in offer.exceptions if e.code == "SCORING_MANUAL_REVIEW")
    assert manual.blocking is False and manual.next_action == "human_review"


def test_compliance_red_blocks_and_is_not_priced(registry):
    offer = run_pipeline(_offer(registry, register_number="HRB-4004"), registry, POLICY)  # sanctions
    assert offer.scoring.value.band is RiskBand.RED
    assert offer.scoring.value.red_kind is RedKind.COMPLIANCE
    assert offer.calculation is None
    assert compute_final_outcome(offer) is FinalOutcome.BLOCKED


# ── 5.3 asset assessment as a distinct, blocking-when-unavailable outcome ────────
def test_asset_assessment_available_for_pkw(registry):
    offer = run_pipeline(_offer(registry), registry, POLICY)
    aa = offer.asset_assessment.value
    assert aa.status is AssetAssessmentStatus.AVAILABLE
    assert aa.result == "PASS"
    assert aa.asset_category == "PKW"
    assert aa.mode == "external"


def test_unavailable_assessment_blocks_progression(registry):
    """FR-22 / §3.7: a required assessment dependency that is unavailable prevents progression."""
    class _DownAdapter:
        name = "ASSET_ASSESSMENT"
        source_type = None

        def __init__(self, *_a, **_k):
            self.mode = AdapterMode.MOCK

        def fetch(self, _request):
            raise ExternalServiceUnavailable("assessment service down")

    registry.register("ASSET_ASSESSMENT", _DownAdapter)
    offer = run_pipeline(_offer(registry), registry, POLICY)

    assert offer.asset_assessment.value.status is AssetAssessmentStatus.UNAVAILABLE
    assert offer.calculation is None                      # not priced while the dependency is down
    assert compute_final_outcome(offer) is FinalOutcome.BLOCKED
    assert "ASSESSMENT_UNAVAILABLE" in [e.code for e in offer.exceptions]


# ── 5.4 the pattern/assessment are ESTABLISHED engine facts (agent cannot set them) ──
def test_scoring_and_assessment_are_engine_envelopes(registry):
    offer = run_pipeline(_offer(registry), registry, POLICY)
    # both outcomes carry engine + policy provenance, so the agent can only explain, never author them
    assert offer.scoring.engine == "DE_PKW_RISK_V1"
    assert offer.asset_assessment.engine == "DE_ASSET_ASSESS_V1"
    assert offer.asset_assessment.inputs_digest.startswith("sha256:")
