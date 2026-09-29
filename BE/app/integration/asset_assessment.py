"""Asset-assessment adapter (spec §3.7). The selected asset proceeds through an assessment process:
an external assessment service for applicable object types (PKW/Equipment/NFZ), ITK handled
internally. An unavailable external dependency can prevent progression (FR-22).

MOCK returns a deterministic PASS for the representative PKW scenario (spec §9.5). Switching to
LIVE/SANDBOX later must not change the schema — only the data's origin. To exercise the
"dependency unavailable ⇒ cannot progress" path, register a stub adapter that raises
ExternalServiceUnavailable (see tests) — the engine records the UNAVAILABLE outcome, never a fake pass.
"""
from __future__ import annotations

from app.core.types import SourceType
from app.integration.base import AdapterMode, ExternalServiceUnavailable


class AssetAssessmentAdapter:
    name = "ASSET_ASSESSMENT"
    source_type = SourceType.EXTERNAL_PROVIDER

    def __init__(self, mode: AdapterMode = AdapterMode.MOCK) -> None:
        self.mode = mode

    def fetch(self, request: dict) -> dict:
        """request = {"asset_category": "PKW", "mode": "external", "attributes": {...}}.
        Returns {"result": "PASS"|"CONCERNS", "detail": str}. Raises ExternalServiceUnavailable
        when the assessment dependency cannot be reached (the engine turns that into an UNAVAILABLE
        outcome that blocks progression)."""
        if self.mode is not AdapterMode.MOCK:
            raise ExternalServiceUnavailable("only MOCK mode wired for asset assessment")
        # Representative deterministic outcome: the object is assessable and passes.
        from app.db.mongo_settings import get_setting
        configured = get_setting("engine_inputs")
        inputs = configured["data"] if configured else {}
        return {
            "result": inputs.get("asset_assessment_result", "PASS"),
            "detail": inputs.get("asset_assessment_detail", "representative MVP assessment (mock)"),
        }
