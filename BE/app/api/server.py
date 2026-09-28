"""FastAPI + LangGraph server (hybrid model).

- Graph is compiled here with a PostgresSaver checkpointer on the SAME Neon DB -> workflow state,
  resume and human-in-the-loop are persisted natively (no hand-rolled workflow code).
- Business reads (list/summary) come from our normalized tables (the queryable system-of-record).
- Endpoints mirror the Agentic Ticket shape (create / advance-by-resume / read), so a UI attaches
  the same way the Ticket FE does.

Run:  uvicorn app.api.server:app --port 8080   (or: python -m app.api.server)
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from app.core.policy import load_policy
from app.db import repository as repo
from app.db.connection import database_url, get_conn
from app.domain.entities import Role
from app.engine.orchestrator import compute_final_outcome
from app.engine.scenario import compare
from app.graph.build import builder
from app.domain.entities import Offer

app = FastAPI(title="Agentic Offer Creation Backend")

# CORS — the frontend (Vercel) calls this API cross-origin. Set ALLOWED_ORIGINS to a comma-separated
# list of deployed frontend origins in production; defaults to "*" for local dev. Note: the browser
# rejects wildcard origins together with credentials, so credentials are enabled only for an explicit
# allow-list (this API is token/cookie-free anyway).
_origins_env = os.environ.get("ALLOWED_ORIGINS", "*").strip()
_allow_origins = ["*"] if _origins_env in ("", "*") else [o.strip() for o in _origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_origins != ["*"],
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
def health():
    """Liveness probe for Render — deliberately does not touch the database."""
    return {"status": "ok"}

# --- persistence: one Neon pool shared by checkpointer + business writes ------ #
# Neon (serverless) closes idle connections / suspends compute after a few minutes, so a pooled
# connection can go BAD. `check` validates (and silently replaces) a connection before handing it
# out; `max_idle`/`max_lifetime` recycle connections before Neon kills them; TCP keepalives keep
# live ones from being dropped. Together these stop the "discarding closed connection" churn and the
# intermittent failures it can cause.
_pool = ConnectionPool(
    conninfo=database_url(),
    min_size=1, max_size=10,
    max_idle=60.0,
    max_lifetime=900.0,
    check=ConnectionPool.check_connection,
    kwargs={
        "autocommit": True, "prepare_threshold": 0,
        "keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 3,
    },
)
_checkpointer = PostgresSaver(_pool)
try:
    _checkpointer.setup()  # create LangGraph checkpoint tables if absent
except Exception as e:  # pragma: no cover
    print(f"[warn] checkpointer.setup(): {e}")
graph = builder.compile(checkpointer=_checkpointer)


# --- request models ---------------------------------------------------------- #
class CreateOffer(BaseModel):
    vehicle_key: str
    register_number: str
    term_months: int
    annual_mileage_km: int
    special_payment_eur: float = 0
    created_by_email: str = "sales@demo.local"
    language: str = "en"


class CreateOfferNL(BaseModel):
    nl_request: str
    created_by_email: str = "sales@demo.local"
    language: str = "en"


class IntakeTurn(BaseModel):
    """One conversational intake turn: a free-text message, confirmations, and/or explicit overrides
    picked from the catalogue (vehicle_key, register_number, term_months, ...). `confirm` accepts all
    pending fields; `confirm_field` accepts one; `proceed` accepts remaining proposals and prices."""
    message: Optional[str] = None
    confirm: bool = False
    confirm_field: Optional[str] = None
    proceed: bool = False
    overrides: Optional[dict] = None


class SelectScenario(BaseModel):
    scenario_label: Optional[str] = None
    scenario_id: Optional[str] = None


class ReviewDecision(BaseModel):
    """Human-review decision (single actor): confirm to generate, or return for correction."""
    decision: str = "confirm"          # "confirm" | "return"
    note: Optional[str] = None


# --- helpers ------------------------------------------------------------------ #
def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _summary(offer_dict: dict) -> dict:
    o = Offer.model_validate(offer_dict)
    c = o.calculation.value if o.calculation else None
    a = o.assessment.value if o.assessment else None
    s = o.scoring.value if o.scoring else None
    sel_label = None
    if o.selected_scenario_id:
        sel = next((x for x in o.scenarios if x.id == o.selected_scenario_id), None)
        sel_label = sel.label if sel else None

    calc = None
    if c:
        calc = {
            "reference_rate_pct": str(c.reference_rate_pct),
            "funding_rate_pct": str(c.funding_rate_pct),
            "commercial_margin_pct": str(c.commercial_margin_pct),
            "customer_finance_rate_pct": str(c.customer_finance_rate_pct),
            "netcap_eur": str(c.netcap_eur),
            "residual_value_amount_eur": str(c.residual_value_amount_eur),
            "pv_residual_eur": str(c.pv_residual_eur),
            "base_lease_eur": str(c.base_lease_eur),
            "service_maintenance_eur": str(c.service_maintenance_eur),
            "service_tyres_eur": str(c.service_tyres_eur),
            "insurance_eur": str(c.insurance_eur),
            "monthly_net_eur": str(c.monthly_net_eur),
            "vat_pct": str(c.vat_pct),
            "monthly_gross_eur": str(c.monthly_gross_eur),
            "quantity": c.quantity,
            "total_monthly_net_eur": str(c.total_monthly_net_eur),
            "total_monthly_gross_eur": str(c.total_monthly_gross_eur),
            "contract_mileage_km": c.contract_mileage_km,
            "mileage_settlement_per_km_eur": str(c.mileage_settlement_per_km_eur),
            "policies": o.calculation.policies,
        }
    residual = None
    if a:
        residual = {"pct": str(a.residual_value_pct), "amount_eur": str(a.residual_value_amount_eur),
                    "confidence": a.residual_confidence.value, "assumptions": a.assumptions}
    scoring_detail = None
    if s:
        scoring_detail = {
            "score": str(s.mvp_risk_score), "band": s.band.value,
            "red_kind": s.red_kind.value if s.red_kind else None,
            "hard_blocks": s.hard_blocks,
            "factors": [{"name": f.name, "weight": str(f.weight),
                         "score": str(f.score_0_100), "contribution": str(f.contribution)}
                        for f in s.factors],
        }

    return {
        "reference": o.reference,
        "workflow_status": o.workflow_status.value,
        "readiness": o.readiness.value,
        "band": s.band.value if s else None,
        "final_outcome": compute_final_outcome(o).value,
        "monthly_net_eur": str(c.monthly_net_eur) if c else None,
        "monthly_gross_eur": str(c.monthly_gross_eur) if c else None,
        "scenarios": compare(o.scenarios) if o.scenarios else [],
        "selected_scenario_id": str(o.selected_scenario_id) if o.selected_scenario_id else None,
        "selected_scenario_label": sel_label,
        "exceptions": [{"code": e.code, "severity": e.severity, "blocking": e.blocking,
                        "next_action": e.next_action, "detail": e.detail} for e in o.exceptions],
        "proposed": o.agent_context.get("proposed"),
        "transcript": o.agent_context.get("messages", []),
        "explanation_pricing": o.agent_context.get("explanation_pricing"),
        "explanation_scenarios": o.agent_context.get("explanation_scenarios"),
        "last_review": o.agent_context.get("last_review"),
        "calc": calc,
        "residual": residual,
        "scoring_detail": scoring_detail,
        "provenance": _provenance(o),
    }


def _pv(pv) -> dict | None:
    """Serialise a ProvenanceValue to {value, status, info_state, source} for the UI chips.
    `info_state` is one of the four target-experience states (spec §7.6, FR-14)."""
    from app.core.types import info_state
    if pv is None:
        return None
    status = pv.status
    return {"value": (pv.value if not isinstance(pv.value, Decimal) else str(pv.value)),
            "status": status.value if hasattr(status, "value") else str(status),
            "info_state": info_state(status),
            "source": pv.source, "confidence": pv.confidence}


def _provenance(o: Offer) -> dict:
    """Per-field provenance (value · status · source) — the 'never a black box' surface (docs/01)."""
    return {
        "term_months": _pv(o.commercial.term_months),
        "annual_mileage_km": _pv(o.commercial.annual_mileage_km),
        "quantity": _pv(o.commercial.quantity),
        "special_payment_eur": _pv(o.commercial.special_payment_eur),
        "service_maintenance": _pv(o.commercial.service_maintenance),
        "service_tyres": _pv(o.commercial.service_tyres),
        "insurance": _pv(o.commercial.insurance),
        "vehicle_make": _pv(o.vehicle.make),
        "vehicle_model": _pv(o.vehicle.commercial_name),
        "colour": _pv(o.vehicle.colour),
        "list_price_net": _pv(o.vehicle.list_price_net),
        "customer_name": _pv(o.customer.legal_name),
        "register_number": _pv(o.customer.register_number),
        "vat_id": _pv(o.customer.vat_id),
    }


def _snapshot(thread_id: str) -> dict:
    snap = graph.get_state(_cfg(thread_id))
    values = snap.values or {}
    interrupts = []
    for task in snap.tasks:
        for it in (task.interrupts or []):
            interrupts.append(it.value)
    offer_dict = values.get("offer") or {}
    field_state = (offer_dict.get("agent_context") or {}).get("field_state")
    return {
        "thread_id": thread_id,
        "next": list(snap.next),
        "status": "awaiting_input" if snap.next else "complete",
        "step": values.get("step"),
        "field_state": field_state,
        "interrupts": interrupts,
        "offer": _summary(values["offer"]) if values.get("offer") else None,
    }


def _email_to_id(email: str, role: Role) -> str:
    with get_conn() as conn:
        return str(repo.ensure_user(conn, email, role))


# --- SSE live agent feed ------------------------------------------------------ #
_NODE_LABELS = {
    "understand": "Understanding the request",
    "agent_turn": "Working through the request",
    "assemble": "Assembling the offer",
    "run_pipeline": "Assembling context, scoring risk & pricing",
    "explain_pricing": "Explaining the pricing",
    "scenarios": "Building scenario options",
    "explain_scenarios": "Comparing scenarios",
    "workspace_gate": "Ready for your decision",
    "human_review": "Human review before generation",
    "final_validation": "Final validation",
    "generate_offer": "Generating the offer",
}


def _node_line(node: str, delta: dict) -> dict:
    """A human-readable feed line + the salient values a node produced."""
    out = {"node": node, "label": _NODE_LABELS.get(node, node)}
    offer_dict = delta.get("offer") if isinstance(delta, dict) else None
    if offer_dict:
        o = Offer.model_validate(offer_dict)
        # Attach salient numbers ONLY to the node that produces them — not to every row.
        if node == "run_pipeline":
            if o.scoring:
                out["band"] = o.scoring.value.band.value
                out["score"] = str(o.scoring.value.mvp_risk_score)
            if o.calculation:
                c = o.calculation.value
                out["detail"] = f"rate {c.customer_finance_rate_pct}% · €{c.monthly_gross_eur}/mo gross"
        elif node == "scenarios" and o.scenarios:
            out["detail"] = f"{len(o.scenarios)} options priced"
    return out


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _stream_run(thread_id: str, graph_input) -> StreamingResponse:
    def gen():
        try:
            for chunk in graph.stream(graph_input, config=_cfg(thread_id), stream_mode="updates"):
                for node, delta in chunk.items():
                    if node == "__interrupt__":
                        yield _sse("await", {"label": "Awaiting your input"})
                    else:
                        yield _sse("node", _node_line(node, delta))
            yield _sse("snapshot", _snapshot(thread_id))
            yield _sse("done", {})
        except Exception as e:  # noqa: BLE001
            yield _sse("error", {"detail": str(e)})
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --- endpoints ---------------------------------------------------------------- #
@app.get("/")
def root():
    return {"status": "ok", "service": "Agentic Offer Creation", "persistence": "Neon Postgres"}


@app.post("/offers")
def create_offer(req: CreateOffer):
    from app.integration.base import AdapterMode, build_default_registry
    from app.service.offer_factory import build_b2b_offer
    from app.core.types import Language

    reg = build_default_registry(AdapterMode.MOCK)
    creator_id = _email_to_id(req.created_by_email, Role.SALES)
    with get_conn() as conn:
        repo.seed_policy(conn, "DE_PKW_V1", load_policy("DE_PKW_V1").raw)

    offer = build_b2b_offer(
        reg, vehicle_key=req.vehicle_key, register_number=req.register_number,
        term_months=req.term_months, annual_mileage_km=req.annual_mileage_km,
        special_payment_eur=Decimal(str(req.special_payment_eur)),
        language=Language(req.language))
    from uuid import UUID
    offer.created_by = UUID(creator_id)

    thread_id = str(offer.id)
    # structured creation -> skip the chat; intake is already confirmed
    graph.invoke({"offer": offer.model_dump(mode="json"), "intake_confirmed_initial": True},
                 config=_cfg(thread_id))
    return _snapshot(thread_id)


@app.post("/offers/nl")
def create_offer_nl(req: CreateOfferNL):
    """Start a conversational offer: the agent understands the request, then the graph pauses at
    intake_collect for the user to answer/correct/confirm (INFERRED -> CONFIRMED)."""
    from uuid import UUID, uuid4
    from app.core.types import Language

    creator_id = _email_to_id(req.created_by_email, Role.SALES)
    with get_conn() as conn:
        repo.seed_policy(conn, "DE_PKW_V1", load_policy("DE_PKW_V1").raw)
    offer = Offer(reference=f"OFF-{uuid4().hex[:8].upper()}", language=Language(req.language),
                  created_by=UUID(creator_id))
    thread_id = str(offer.id)
    graph.invoke({"offer": offer.model_dump(mode="json"), "nl_request": req.nl_request},
                 config=_cfg(thread_id))
    return _snapshot(thread_id)


@app.post("/offers/{thread_id}/intake")
def intake(thread_id: str, req: IntakeTurn):
    graph.invoke(Command(resume=req.model_dump()), config=_cfg(thread_id))
    return _snapshot(thread_id)


@app.get("/offers/{thread_id}")
def get_offer(thread_id: str):
    snap = _snapshot(thread_id)
    if snap["offer"] is None:
        raise HTTPException(404, "offer/thread not found")
    return snap


@app.post("/offers/{thread_id}/select")
def select(thread_id: str, req: SelectScenario):
    resume = {"action": "select", **{k: v for k, v in {"scenario_label": req.scenario_label,
                                                       "scenario_id": req.scenario_id}.items() if v is not None}}
    graph.invoke(Command(resume=resume), config=_cfg(thread_id))
    return _snapshot(thread_id)


@app.post("/offers/{thread_id}/generate")
def generate(thread_id: str):
    graph.invoke(Command(resume={"action": "generate"}), config=_cfg(thread_id))
    return _snapshot(thread_id)


@app.post("/offers/{thread_id}/adjust")
def adjust(thread_id: str):
    """Move the offer back into the agent chat so the salesperson can change anything, then re-price."""
    graph.invoke(Command(resume={"action": "adjust"}), config=_cfg(thread_id))
    return _snapshot(thread_id)


@app.post("/offers/{thread_id}/review")
def review(thread_id: str, req: ReviewDecision):
    """Resume the mandatory human-review gate: confirm (-> generate) or return (-> gate)."""
    graph.invoke(Command(resume=req.model_dump()), config=_cfg(thread_id))
    return _snapshot(thread_id)


class GotoStep(BaseModel):
    step: str          # channel | partner | product | asset | commercial


def _goto_resume(step: str) -> dict:
    # one payload works for both a confirm_step interrupt (reads `goto`) and the workspace gate (reads action)
    return {"action": "goto", "step": step, "goto": step}


@app.post("/offers/{thread_id}/goto")
def goto(thread_id: str, req: GotoStep):
    """Jump back to an earlier wizard step to edit it (controlled iteration)."""
    graph.invoke(Command(resume=_goto_resume(req.step)), config=_cfg(thread_id))
    return _snapshot(thread_id)


@app.post("/offers/{thread_id}/goto/stream")
def goto_stream(thread_id: str, req: GotoStep):
    return _stream_run(thread_id, Command(resume=_goto_resume(req.step)))


# --- streaming variants (used by the UI for the live feed) -------------------- #
@app.post("/offers/nl/stream")
def create_offer_nl_stream(req: CreateOfferNL):
    from uuid import UUID, uuid4
    from app.core.types import Language
    creator_id = _email_to_id(req.created_by_email, Role.SALES)
    with get_conn() as conn:
        repo.seed_policy(conn, "DE_PKW_V1", load_policy("DE_PKW_V1").raw)
    offer = Offer(reference=f"OFF-{uuid4().hex[:8].upper()}", language=Language(req.language),
                  created_by=UUID(creator_id))
    return _stream_run(str(offer.id),
                       {"offer": offer.model_dump(mode="json"), "nl_request": req.nl_request})


@app.post("/offers/{thread_id}/intake/stream")
def intake_stream(thread_id: str, req: IntakeTurn):
    return _stream_run(thread_id, Command(resume=req.model_dump()))


@app.post("/offers/{thread_id}/select/stream")
def select_stream(thread_id: str, req: SelectScenario):
    resume = {"action": "select", **{k: v for k, v in {"scenario_label": req.scenario_label,
                                                       "scenario_id": req.scenario_id}.items() if v is not None}}
    return _stream_run(thread_id, Command(resume=resume))


@app.post("/offers/{thread_id}/generate/stream")
def generate_stream(thread_id: str):
    return _stream_run(thread_id, Command(resume={"action": "generate"}))


@app.post("/offers/{thread_id}/adjust/stream")
def adjust_stream(thread_id: str):
    return _stream_run(thread_id, Command(resume={"action": "adjust"}))


@app.post("/offers/{thread_id}/review/stream")
def review_stream(thread_id: str, req: ReviewDecision):
    return _stream_run(thread_id, Command(resume=req.model_dump()))


@app.get("/offers/{thread_id}/budget-fit")
def budget_fit(thread_id: str):
    """Rank the (filtered) catalogue by fit to the offer's stated budget (Phase 6). The agent
    enumerates candidates, the deterministic engine prices each, we rank — the agent never prices."""
    from app.engine.budget import catalogue_budget_fit, extract_budget
    from app.graph.agent_nodes import _filter_catalogue, _REGISTRY
    from app.agent.resolve import list_vehicles
    snap = graph.get_state(_cfg(thread_id))
    if not snap.values.get("offer"):
        raise HTTPException(404, "offer/thread not found")
    o = Offer.model_validate(snap.values["offer"])
    proposed = (o.agent_context or {}).get("proposed") or {}
    was_default_recommendation = any(
        "lowest listed-price option in this demo catalogue" in (m.get("content") or "")
        for m in ((o.agent_context or {}).get("messages") or [])
        if m.get("role") == "assistant")
    show_all_assets = proposed.get("vehicle_recommended") or (
        "vehicle_recommended" not in proposed and was_default_recommendation)
    candidates = (list_vehicles() if show_all_assets
                  else _filter_catalogue(proposed))
    candidate_keys = [r["key"] for r in candidates]
    return {
        "budget": (lambda b: {"value": str(b["value"]), "basis": b["basis"], "currency": b["currency"]}
                   if b else None)(extract_budget(o)),
        "filters": proposed.get("filters") or {},
        "candidates": catalogue_budget_fit(o, _REGISTRY, candidate_keys=candidate_keys),
    }


@app.get("/offers/{thread_id}/audit")
def get_audit(thread_id: str):
    from uuid import UUID
    with get_conn() as conn:
        return repo.audit_trail(conn, UUID(thread_id))


@app.get("/audit")
def get_audit_all(limit: int = 200):
    """Global, cross-offer audit feed for the standalone Audit screen."""
    with get_conn() as conn:
        return repo.audit_trail_all(conn, limit)


@app.get("/offers/{thread_id}/detail")
def get_detail(thread_id: str):
    """Full transparency: provenance contexts + result envelopes (pass-2 panels)."""
    snap = graph.get_state(_cfg(thread_id))
    if not snap.values.get("offer"):
        raise HTTPException(404, "offer/thread not found")
    o = Offer.model_validate(snap.values["offer"])
    return {
        "reference": o.reference,
        "commercial": o.commercial.model_dump(mode="json"),
        "customer": o.customer.model_dump(mode="json"),
        "vehicle": o.vehicle.model_dump(mode="json"),
        "calculation": o.calculation.model_dump(mode="json") if o.calculation else None,
        "assessment": o.assessment.model_dump(mode="json") if o.assessment else None,
        "scoring": o.scoring.model_dump(mode="json") if o.scoring else None,
        "agent_context": o.agent_context,
    }


@app.get("/catalogue/vehicles")
def catalogue_vehicles():
    from app.agent.resolve import list_vehicles
    return list_vehicles()


@app.get("/catalogue/customers")
def catalogue_customers():
    from app.agent.resolve import list_customers
    return list_customers()


@app.get("/catalogue/partners")
def catalogue_partners(q: str = ""):
    """Partner search + duplicate candidates for the Partner step (spec §3.4, FR-06)."""
    from app.agent.resolve import search_partners
    return search_partners(q)


@app.get("/catalogue/reference")
def catalogue_reference():
    """Controlled Offer Reference Data for the selection steps (business lines, products, asset
    categories, channels) — spec §3.5-3.6, §5.5."""
    from app.domain.reference import load_reference_data
    ref = load_reference_data()
    return {
        "version": ref.version,
        "channels": [c.model_dump() for c in ref.channels],
        "business_lines": [b.model_dump() for b in ref.business_lines],
        "leasing_products": [p.model_dump() for p in ref.leasing_products],
        "asset_categories": [c.model_dump() for c in ref.asset_categories],
    }


@app.get("/offers")
def list_offers(limit: int = 50):
    """Business read-model (from our tables, not the checkpoint blobs)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, reference, workflow_status, readiness, scoring_band,
                   customer_context->'legal_name'->>'value'                       AS customer,
                   vehicle_context->'make'->>'value'                              AS make,
                   vehicle_context->'commercial_name'->>'value'                   AS model,
                   commercial_context->'quantity'->>'value'                       AS qty,
                   calculation_result->'value'->>'total_monthly_gross_eur'        AS fleet_monthly
            FROM offers ORDER BY updated_at DESC LIMIT %s
            """, (limit,)).fetchall()
    out = []
    for r in rows:
        qty = int(r[8]) if r[8] else 1
        veh = (f"{qty}× " if qty > 1 else "") + " ".join(x for x in (r[6], r[7]) if x) if (r[6] or r[7]) else None
        out.append({"id": str(r[0]), "reference": r[1], "workflow_status": r[2], "readiness": r[3],
                    "band": r[4], "customer": r[5], "vehicle": veh, "quantity": qty,
                    "fleet_monthly_eur": r[9]})
    return out


if __name__ == "__main__":
    import uvicorn
    # Render (and most PaaS) inject the port to bind via $PORT.
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
