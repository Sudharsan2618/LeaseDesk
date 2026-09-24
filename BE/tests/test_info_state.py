"""Phase 4 — the four info states shown on every field (spec §7.6, FR-14)."""
from app.core.types import FieldStatus, info_state


def test_info_state_maps_to_four_ui_states():
    assert info_state(FieldStatus.ESTABLISHED) == "established"
    assert info_state(FieldStatus.CONFIRMED) == "confirmed"
    assert info_state(FieldStatus.REQUIRES_CONFIRMATION) == "requires_confirmation"
    assert info_state(FieldStatus.INFERRED) == "requires_confirmation"   # agent-proposed -> needs a yes
    assert info_state(FieldStatus.MISSING) == "needs_action"
    assert info_state(FieldStatus.INVALID) == "needs_action"
    assert info_state(FieldStatus.INCONSISTENT) == "needs_action"


def test_only_four_distinct_states():
    states = {info_state(s) for s in FieldStatus}
    assert states == {"established", "confirmed", "requires_confirmation", "needs_action"}
