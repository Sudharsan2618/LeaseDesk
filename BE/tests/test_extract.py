"""Phase 3 — flexible intent extraction (doc 13 §3.1). The LLM call is offline in tests, so we
build the ExtractedIntent the way the model would and prove the deterministic plumbing: the merge
folds slots + asset_filters + constraints + ambiguities into the proposal, and the catalogue filter
narrows by attribute. Worked example: "I need 4 seater 30 insured cars — my budget is $300k"."""
from app.agent.schemas import Ambiguity, Constraint, ExtractedIntent
from app.graph.agent_nodes import _filter_catalogue, _merge


def test_merge_folds_flexible_slots():
    intent = ExtractedIntent(
        asset_filters={"seats": "4", "fuel_type": "ELECTRIC"},
        quantity=30, insurance=True,
        constraints=[Constraint(kind="budget", value=300000, currency="$", basis="unknown")],
        ambiguities=[Ambiguity(field="budget", reason="currency and total-vs-monthly unclear",
                               options=["USD total", "EUR total", "EUR per month"])],
    )
    proposed = _merge({}, intent)
    assert proposed["filters"] == {"seats": "4", "fuel_type": "ELECTRIC"}
    assert proposed["quantity"] == 30
    assert proposed["insurance"] is True
    assert proposed["constraints"][0]["kind"] == "budget"
    assert proposed["constraints"][0]["value"] == 300000
    assert proposed["constraints"][0]["currency"] == "$"        # kept as written
    assert proposed["ambiguities"][0]["field"] == "budget"       # flagged, not silently resolved (BR-03)


def test_asset_filter_narrows_catalogue_by_seats():
    all_rows = _filter_catalogue({})
    four_seaters = _filter_catalogue({"filters": {"seats": "4"}})
    assert len(four_seaters) < len(all_rows)                     # actually filtered
    assert four_seaters and all(str(r["seats"]) == "4" for r in four_seaters)
    assert any(r["key"] == "porsche-taycan" for r in four_seaters)  # the 4-seater in the catalogue


def test_asset_filter_combines_attributes():
    rows = _filter_catalogue({"filters": {"seats": "4", "fuel_type": "ELECTRIC"}})
    assert rows and all(str(r["seats"]) == "4" and r["fuel_type"].upper() == "ELECTRIC" for r in rows)


def test_budget_stays_a_constraint_not_a_field():
    # A budget must NOT become special_payment or any priced field — it shapes scenarios (Phase 6).
    intent = ExtractedIntent(constraints=[Constraint(kind="budget", value=300000, currency="EUR", basis="total")])
    proposed = _merge({}, intent)
    assert "special_payment_eur" not in proposed
    assert proposed["constraints"][0]["kind"] == "budget"


def test_merge_none_is_noop():
    assert _merge({"term_months": 36}, None) == {"term_months": 36}
