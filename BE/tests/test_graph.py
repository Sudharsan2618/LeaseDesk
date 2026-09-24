"""LangGraph workflow tests — stepped agent-driven intake (spec §3.3-3.6), single-actor gate.
Skips if DB unreachable (nodes persist to Neon via the projection writer)."""
from __future__ import annotations

import pytest

pytest.importorskip("langgraph")
psycopg = pytest.importorskip("psycopg")

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.core.policy import load_policy
from app.core.types import Language
from app.domain.entities import Offer, Role
from app.graph.build import builder
from app.integration.base import AdapterMode, build_default_registry
from app.service.offer_factory import build_b2b_offer


@pytest.fixture(scope="module")
def graph():
    try:
        from app.db.connection import get_conn
        from app.db import repository as repo
        with get_conn() as conn:
            repo.seed_policy(conn, "DE_PKW_V1", load_policy("DE_PKW_V1").raw)
    except Exception as e:
        pytest.skip(f"database unavailable: {e}")
    return builder.compile(checkpointer=MemorySaver())


def _sales():
    from app.db.connection import get_conn
    from app.db import repository as repo
    with get_conn() as conn:
        return repo.ensure_user(conn, "gtest-sales@demo.local", Role.SALES)


def _structured(reg="HRB-1001", veh="bmw-x1-sdrive18i", **kw):
    r = build_default_registry(AdapterMode.MOCK)
    o = build_b2b_offer(r, vehicle_key=veh, register_number=reg, term_months=36,
                        annual_mileage_km=20000, language=Language.EN, **kw)
    o.created_by = _sales()
    return o


def _start(graph, offer):
    cfg = {"configurable": {"thread_id": str(offer.id)}}
    graph.invoke({"offer": offer.model_dump(mode="json"), "intake_confirmed_initial": True}, config=cfg)
    return cfg


def _nl(graph, text="Lease a BMW X1"):
    from uuid import uuid4
    offer = Offer(reference=f"OFF-{uuid4().hex[:8].upper()}", language=Language.EN, created_by=_sales())
    cfg = {"configurable": {"thread_id": str(offer.id)}}
    graph.invoke({"offer": offer.model_dump(mode="json"), "nl_request": text}, config=cfg)
    return cfg


def _confirm(graph, cfg, overrides=None):
    graph.invoke(Command(resume={"confirm": True, "overrides": overrides or {}}), config=cfg)


def _here(graph, cfg):
    return graph.get_state(cfg).next


# --- structured creation still short-circuits straight to the gate ----------- #
def test_gate_select_review_then_generate(graph):
    offer = _structured()
    cfg = _start(graph, offer)
    assert _here(graph, cfg) == ("workspace_gate",)

    graph.invoke(Command(resume={"action": "select", "scenario_label": "48M"}), config=cfg)
    assert _here(graph, cfg) == ("workspace_gate",)
    o = Offer.model_validate(graph.get_state(cfg).values["offer"])
    assert o.selected_scenario_id is not None

    graph.invoke(Command(resume={"action": "generate"}), config=cfg)  # -> mandatory review gate
    assert _here(graph, cfg) == ("human_review",)
    o = Offer.model_validate(graph.get_state(cfg).values["offer"])
    assert o.workflow_status.value == "PENDING_HUMAN_REVIEW"          # BR-15: review before generate
    assert o.workflow_status.value != "OFFER_GENERATED"              # not generated until confirmed

    graph.invoke(Command(resume={"decision": "confirm"}), config=cfg)
    snap = graph.get_state(cfg)
    assert snap.next == ("workspace_gate",)                          # generated but still revisitable
    assert Offer.model_validate(snap.values["offer"]).workflow_status.value == "OFFER_GENERATED"


def test_review_return_goes_back_to_gate_without_generating(graph):
    offer = _structured()
    cfg = _start(graph, offer)
    graph.invoke(Command(resume={"action": "select", "scenario_label": "36M"}), config=cfg)
    graph.invoke(Command(resume={"action": "generate"}), config=cfg)
    assert _here(graph, cfg) == ("human_review",)
    graph.invoke(Command(resume={"decision": "return", "note": "check mileage"}), config=cfg)
    snap = graph.get_state(cfg)
    assert snap.next == ("workspace_gate",)                          # returned, still editable
    assert Offer.model_validate(snap.values["offer"]).workflow_status.value != "OFFER_GENERATED"


def test_generate_needs_a_selection(graph):
    offer = _structured()
    cfg = _start(graph, offer)
    graph.invoke(Command(resume={"action": "generate"}), config=cfg)  # no selection yet
    assert _here(graph, cfg) == ("workspace_gate",)                  # no review, stays at hub
    o = Offer.model_validate(graph.get_state(cfg).values["offer"])
    assert o.workflow_status.value != "OFFER_GENERATED"


def test_red_compliance_blocks(graph):
    offer = _structured(reg="HRB-4004")
    cfg = _start(graph, offer)
    snap = graph.get_state(cfg)
    assert snap.next == ()                                            # blocked, terminal
    assert Offer.model_validate(snap.values["offer"]).scoring.value.band.value == "RED"


# --- stepped intake: each step is its own confirm gate (FR-06/08/09) --------- #
def test_stepped_intake_walks_every_gate(graph):
    cfg = _nl(graph)
    # the wizard pauses at each step in order
    assert _here(graph, cfg) == ("select_channel",)
    _confirm(graph, cfg)                                              # channel (default internal_sales)
    assert _here(graph, cfg) == ("select_partner",)
    _confirm(graph, cfg, {"register_number": "HRB-1001"})            # partner
    assert _here(graph, cfg) == ("select_product",)
    _confirm(graph, cfg)                                              # product (default PKW)
    assert _here(graph, cfg) == ("select_asset",)
    _confirm(graph, cfg, {"vehicle_key": "bmw-x1-sdrive18i"})        # asset
    assert _here(graph, cfg) == ("select_commercial",)
    _confirm(graph, cfg, {"term_months": 36, "annual_mileage_km": 20000})  # commercial
    assert _here(graph, cfg) == ("workspace_gate",)                  # priced -> hub


def test_step_blocks_without_mandatory_field(graph):
    cfg = _nl(graph, text="hello")
    _confirm(graph, cfg)                                              # channel
    assert _here(graph, cfg) == ("select_partner",)
    _confirm(graph, cfg)                                              # confirm WITHOUT a partner -> cannot advance
    assert _here(graph, cfg) == ("select_partner",)                  # FR-16 / BR-02: stays put


def test_adjust_reopens_wizard_then_back_to_gate(graph):
    offer = _structured()
    cfg = _start(graph, offer)
    graph.invoke(Command(resume={"action": "adjust"}), config=cfg)
    assert _here(graph, cfg) == ("select_asset",)                    # reopened at asset
    _confirm(graph, cfg)                                              # re-confirm asset (already set)
    assert _here(graph, cfg) == ("select_commercial",)
    _confirm(graph, cfg, {"term_months": 48})                        # change term -> re-price
    assert _here(graph, cfg) == ("workspace_gate",)


def test_adjust_after_full_nl_wizard_then_commercial_advances(graph):
    """Repro of the reported bug: NL → walk every step → gate → select → adjust → asset → commercial
    must reach the gate again (commercial confirm should advance, not stall)."""
    cfg = _nl(graph)
    _confirm(graph, cfg)                                              # channel
    _confirm(graph, cfg, {"register_number": "HRB-1001"})            # partner
    _confirm(graph, cfg)                                              # product
    _confirm(graph, cfg, {"vehicle_key": "bmw-x1-sdrive18i"})        # asset
    _confirm(graph, cfg, {"term_months": 36, "annual_mileage_km": 20000})  # commercial
    assert _here(graph, cfg) == ("workspace_gate",)                  # priced
    graph.invoke(Command(resume={"action": "select", "scenario_label": "36M"}), config=cfg)
    graph.invoke(Command(resume={"action": "adjust"}), config=cfg)
    assert _here(graph, cfg) == ("select_asset",)
    _confirm(graph, cfg)                                              # re-confirm asset
    assert _here(graph, cfg) == ("select_commercial",)
    _confirm(graph, cfg, {"term_months": 48})                        # change term
    assert _here(graph, cfg) == ("workspace_gate",)                  # <-- must advance


def _goto(graph, cfg, step):
    graph.invoke(Command(resume={"action": "goto", "step": step, "goto": step}), config=cfg)


def test_goto_back_to_edit_a_confirmed_step(graph):
    """Controlled iteration: from a later step, jump back to edit an earlier one, then continue."""
    cfg = _nl(graph)
    _confirm(graph, cfg)                                              # channel
    _confirm(graph, cfg, {"register_number": "HRB-1001"})            # partner
    _confirm(graph, cfg)                                              # product
    assert _here(graph, cfg) == ("select_asset",)
    _goto(graph, cfg, "partner")                                     # jump back to the partner step
    assert _here(graph, cfg) == ("select_partner",)
    _confirm(graph, cfg, {"register_number": "HRB-2002"})           # pick a different customer
    assert _here(graph, cfg) == ("select_product",)                 # continues forward from there
    _confirm(graph, cfg)                                             # product
    _confirm(graph, cfg, {"vehicle_key": "bmw-x1-sdrive18i"})       # asset
    _confirm(graph, cfg, {"term_months": 36, "annual_mileage_km": 20000})  # commercial
    assert _here(graph, cfg) == ("workspace_gate",)
    o = Offer.model_validate(graph.get_state(cfg).values["offer"])
    assert o.customer.register_number.value == "HRB-2002"           # the edit took effect


def test_goto_from_priced_gate(graph):
    offer = _structured()
    cfg = _start(graph, offer)
    assert _here(graph, cfg) == ("workspace_gate",)
    _goto(graph, cfg, "asset")                                      # jump back to asset from pricing
    assert _here(graph, cfg) == ("select_asset",)


def test_out_of_range_correction_loop(graph):
    cfg = _nl(graph, text="x")
    _confirm(graph, cfg)                                              # channel
    _confirm(graph, cfg, {"register_number": "HRB-1001"})            # partner
    _confirm(graph, cfg)                                              # product
    _confirm(graph, cfg, {"vehicle_key": "bmw-x1-sdrive18i"})        # asset
    _confirm(graph, cfg, {"term_months": 72, "annual_mileage_km": 20000})  # commercial: term out of range
    assert _here(graph, cfg) == ("select_asset",)                    # pricing withheld -> wizard reopened
    _confirm(graph, cfg)                                              # re-confirm asset
    _confirm(graph, cfg, {"term_months": 48})                        # fix term
    assert _here(graph, cfg) == ("workspace_gate",)
