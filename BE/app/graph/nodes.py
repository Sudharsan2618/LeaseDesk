"""Graph nodes: deterministic bodies call the EXISTING engine (Phases 1-3). No LLM yet.

Human-in-the-loop uses interrupt()/Command(resume=...). Everything BEFORE an interrupt() may run
twice (initial pause + resume), so all side-effecting writes happen AFTER the interrupt() and are
idempotent (upsert by id). Persistence goes only through repository.upsert_offer (single writer).
"""
from __future__ import annotations

from uuid import UUID

from langgraph.types import interrupt

from app.core.policy import load_policy
from app.db import repository as repo
from app.db.connection import get_conn
from app.domain.entities import FinalOutcome, Offer, WorkflowStatus
from app.engine.orchestrator import compute_final_outcome, run_pipeline
from app.engine.scenario import compare, generate_scenarios, select_scenario
from app.graph.state import OfferState
from app.integration.base import AdapterMode, build_default_registry

_REGISTRY = build_default_registry(AdapterMode.MOCK)


# --- helpers ---------------------------------------------------------------- #
def _load(state: OfferState) -> Offer:
    return Offer.model_validate(state["offer"])


def _dump(offer: Offer) -> dict:
    return offer.model_dump(mode="json")


def _persist(offer: Offer, event: str, *, actor: UUID | None = None, reason: str | None = None):
    with get_conn() as conn:
        repo.upsert_offer(conn, offer, event=event, actor=actor, reason=reason)


# --- nodes ------------------------------------------------------------------ #
def run_pipeline_node(state: OfferState) -> dict:
    """Assemble context + residual + scoring + calc + eligibility (Phases 1-2)."""
    offer = _load(state)
    policy = load_policy(offer.policy_version)
    run_pipeline(offer, _REGISTRY, policy)
    _persist(offer, "PIPELINE_RUN")
    return {"offer": _dump(offer)}


def scenarios_node(state: OfferState) -> dict:
    """Price the requested terms with optional service-bundle alternatives."""
    from app.engine.budget import annotate_scenarios
    offer = _load(state)
    policy = load_policy(offer.policy_version)
    generate_scenarios(offer, _REGISTRY, policy)
    annotate_scenarios(offer)                       # tag/sort by budget fit (no-op without a budget)
    offer.workflow_status = WorkflowStatus.SCENARIOS_AVAILABLE
    _persist(offer, "SCENARIOS_GENERATED")
    return {"offer": _dump(offer)}


def _selected_scenario(offer):
    if not offer.selected_scenario_id:
        return None
    return next((s for s in offer.scenarios if s.id == offer.selected_scenario_id), None)


def workspace_gate_node(state: OfferState) -> dict:
    """The single-actor hub (no approver). The salesperson picks/changes a scenario, asks the agent
    to adjust, or generates the offer. The offer stays MUTABLE — even after generation the thread
    returns here so it can be re-selected, adjusted, or regenerated at any time (docs/09)."""
    offer = _load(state)
    sel = _selected_scenario(offer)
    action = interrupt({
        "type": "workspace_gate",
        "reference": offer.reference,
        "scenarios": compare(offer.scenarios),
        "selected_label": sel.label if sel else None,
        "can_generate": offer.selected_scenario_id is not None,
        "generated": offer.workflow_status is WorkflowStatus.OFFER_GENERATED,
    })
    a = ((action.get("action") if isinstance(action, dict) else str(action)) or "").lower()

    if a == "generate" and offer.selected_scenario_id is not None:
        selected = _selected_scenario(offer)
        if selected is not None and selected.fits_budget is False:
            offer.agent_context.setdefault("messages", []).append({
                "role": "assistant",
                "content": "That scenario exceeds the stated budget, so I can't generate it. "
                           "Choose a budget-fitting vehicle or revise the budget.",
            })
            _persist(offer, "GENERATION_BLOCKED_BUDGET")
            return {"offer": _dump(offer), "gate_action": "select", "finalize": False}
        # generation now goes THROUGH the human-review gate (BR-15); finalize is set there, not here.
        # Mark PENDING_HUMAN_REVIEW here (the gate returns normally, so this commits to graph state):
        # human_review_node sets it too, but that assignment runs before its interrupt() and so never
        # reaches the graph channel — setting it here makes the review-pending status visible at pause.
        offer.workflow_status = WorkflowStatus.PENDING_HUMAN_REVIEW
        _persist(offer, "REVIEW_REQUESTED")
        return {"offer": _dump(offer), "gate_action": "generate", "finalize": False}
    if a == "adjust":
        return {"gate_action": "adjust", "finalize": False}
    if a == "goto" and isinstance(action, dict) and action.get("step") in _WIZARD_STEPS:
        return {"gate_action": "goto", "goto_step": action["step"], "finalize": False}

    # default = select (or generate without a selection -> ask to select first)
    chosen = None
    if isinstance(action, dict):
        if action.get("scenario_id"):
            chosen = next((s for s in offer.scenarios if str(s.id) == str(action["scenario_id"])), None)
        elif action.get("scenario_label"):
            chosen = next((s for s in offer.scenarios if s.label == action["scenario_label"]), None)
    if chosen is not None:
        select_scenario(offer, chosen.id)
        if offer.workflow_status is not WorkflowStatus.OFFER_GENERATED:
            offer.workflow_status = WorkflowStatus.SCENARIO_SELECTED
        _persist(offer, "SCENARIO_SELECTED")
    return {"offer": _dump(offer), "gate_action": "select", "finalize": False}


def human_review_node(state: OfferState) -> dict:
    """Mandatory human review before generation (spec §9.10, FR-35-40, BR-15). Single actor: the
    salesperson reviews the complete offer + exceptions and decides confirm / return. Generation is
    blocked here when the offer is not eligible (FR-46, BR-19). A material change made afterwards
    re-runs the wizard -> pipeline, so the offer is always reassessed before a second review."""
    offer = _load(state)
    outcome = compute_final_outcome(offer)
    can_generate = outcome is not FinalOutcome.BLOCKED
    sel = _selected_scenario(offer)
    offer.workflow_status = WorkflowStatus.PENDING_HUMAN_REVIEW
    _persist(offer, "PENDING_HUMAN_REVIEW")
    decision = interrupt({
        "type": "human_review",
        "reference": offer.reference,
        "outcome": outcome.value,
        "can_generate": can_generate,
        "selected_scenario_label": sel.label if sel else None,
        "exceptions": [{"code": e.code, "severity": e.severity, "blocking": e.blocking,
                        "next_action": e.next_action} for e in offer.exceptions],
        "prompt": ("Review the complete offer, then confirm to generate or return for correction."
                   if can_generate else
                   "This offer cannot be generated while a blocking condition remains. Return to correct it."),
    })
    d = ((decision.get("decision") if isinstance(decision, dict) else str(decision)) or "").lower()
    ac = offer.agent_context
    if d in ("confirm", "approve", "generate") and can_generate:
        ac["last_review"] = {"decision": "confirmed", "outcome": outcome.value}
        offer.agent_context = ac
        _persist(offer, "REVIEW_CONFIRMED")
        return {"offer": _dump(offer), "finalize": True, "gate_action": "review_confirm"}
    ac["last_review"] = {"decision": "returned", "outcome": outcome.value,
                         "note": (decision.get("note") if isinstance(decision, dict) else None)}
    offer.agent_context = ac
    _persist(offer, "REVIEW_RETURNED")
    return {"offer": _dump(offer), "finalize": False, "gate_action": "review_return"}


def route_after_review(state: OfferState) -> str:
    return "final_validation" if state.get("finalize") else "workspace_gate"


def final_validation_node(state: OfferState) -> dict:
    """Compute READY / REQUIRES_ACTION / BLOCKED (docs/06 §3)."""
    offer = _load(state)
    offer.workflow_status = WorkflowStatus.FINAL_VALIDATION
    _persist(offer, "FINAL_VALIDATION")
    return {"offer": _dump(offer)}


def generate_offer_node(state: OfferState) -> dict:
    """Freeze the validated offer snapshot (PDF rendering is Phase 5)."""
    offer = _load(state)
    offer.workflow_status = WorkflowStatus.OFFER_GENERATED
    _persist(offer, "OFFER_GENERATED_STATUS")
    with get_conn() as conn:
        repo.save_output(conn, offer)
    return {"offer": _dump(offer)}


# --- routers ---------------------------------------------------------------- #
def route_after_pipeline(state: OfferState) -> str:
    offer = _load(state)
    # not priced (RED / blocking exception) -> straight to final validation (will be BLOCKED)
    if offer.calculation is None:
        return "final_validation"
    return "scenarios"


_WIZARD_STEPS = ("channel", "partner", "product", "asset", "commercial")


def route_after_gate(state: OfferState) -> str:
    a = state.get("gate_action")
    if a == "generate":
        return "human_review"        # generation goes THROUGH the mandatory review gate (BR-15)
    if a in ("adjust", "goto"):
        return "agent_turn"          # reopen the conversational intake to edit any field, then re-price
    return "workspace_gate"          # select / default -> stay at the hub


def route_after_final(state: OfferState) -> str:
    # Generate when the salesperson finalised (that action IS the human decision) and nothing is
    # hard-blocked. Not-priced/compliance paths reach here without finalize and must NOT generate.
    offer = _load(state)
    if state.get("finalize") and compute_final_outcome(offer) is not FinalOutcome.BLOCKED:
        return "generate_offer"
    return "END"
