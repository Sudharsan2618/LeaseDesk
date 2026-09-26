"""LLM + agent graph nodes (Phase 2/7) — stepped, agent-driven intake.

Intake is the selection hierarchy with a DISTINCT confirm interrupt per step (spec §3.3-3.6):

    understand → select_channel → select_partner → select_product → select_asset
               → select_commercial → assemble → run_pipeline

`understand` extracts the initial free text and pre-fills every step it can, so each gate opens
already populated; the salesperson confirms, edits, or talks to the agent at each one. A step cannot
be confirmed while a mandatory field is missing (FR-16, BR-02). The LLM only understands, clarifies
and explains — it never prices, scores, decides, selects, or invents identifiers. Everything
degrades to safe deterministic behaviour without a key. Persistence goes only through
repository.upsert_offer.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from langgraph.types import interrupt

from app.agent import explain
from app.agent.extract import understand
from app.agent.turn import SET_KEYS as _TURN_SET_KEYS, plan_turn
from app.agent.resolve import (
    customer_label,
    list_customers,
    list_vehicles,
    resolve_register,
    resolve_vehicle_key,
    search_partners,
    vehicle_label,
)
from app.core.types import RiskBand
from app.domain.entities import Offer, WorkflowStatus, _ref_seed
from app.domain.reference import (
    DEFAULT_ASSET_CATEGORY,
    DEFAULT_BUSINESS_LINE,
    DEFAULT_CHANNEL,
    DEFAULT_PRODUCT,
    load_reference_data,
)
from app.graph.nodes import _dump, _load, _persist, _REGISTRY
from app.service.offer_factory import build_b2b_offer

STEPS = ["channel", "partner", "product", "asset", "commercial"]
_NEXT_STEP = {"channel": "select_partner", "partner": "select_product",
              "product": "select_asset", "asset": "select_commercial",
              "commercial": "assemble"}
_STAY = {"channel": "select_channel", "partner": "select_partner", "product": "select_product",
         "asset": "select_asset", "commercial": "select_commercial"}
_STEP_NODE = {s: f"select_{s}" for s in STEPS}


def _goto(reply, step: str):
    """A request to jump back to an earlier step to edit it (spec: controlled iteration)."""
    if isinstance(reply, dict):
        g = reply.get("goto")
        if g in STEPS and g != step:
            return g
    return None


def _confirm_echo(step: str, proposed: dict) -> str | None:
    """Narrate each structured confirmation into the chat, so the card and the conversation stay tied."""
    if step == "channel":
        return f"Channel set: {proposed.get('channel', 'internal_sales').replace('_', ' ')}. Next — the customer."
    if step == "partner":
        return f"Customer set: {customer_label(proposed.get('register_number')) or proposed.get('register_number')}. Next — business line & product."
    if step == "product":
        return f"Product set: {proposed.get('leasing_product', 'pkw_km_leasing').replace('_', ' ')}. Next — the asset."
    if step == "asset":
        return f"Asset set: {vehicle_label(proposed.get('vehicle_key')) or proposed.get('vehicle_key')}. Next — commercial requirements."
    if step == "commercial":
        return "Commercial requirements confirmed. Pricing now…"
    return None


# --- what the user actually confirmed (chat = single source of truth) -------- #
_STEP_FIELD = {"channel": "channel", "partner": "register_number",
               "product": "leasing_product", "asset": "vehicle_key"}
_COMMERCIAL_KEYS = ("term_months", "annual_mileage_km", "quantity", "special_payment_eur",
                    "service_maintenance", "service_tyres", "insurance")


def _step_value(step: str, proposed: dict):
    """The value(s) a step owns — used to tell an edit (changed) from a plain set."""
    if step == "commercial":
        return tuple(proposed.get(k) for k in _COMMERCIAL_KEYS)
    return proposed.get(_STEP_FIELD.get(step, ""))


def _confirm_summary(step: str, proposed: dict) -> tuple[str, str] | None:
    """(label, value) of what was confirmed, echoed as a user chat entry so the conversation records
    the human decision — not just the agent's response."""
    if step == "channel":
        return ("Channel", (proposed.get("channel", "internal_sales") or "").replace("_", " ").title())
    if step == "partner":
        return ("Customer", customer_label(proposed.get("register_number")) or str(proposed.get("register_number") or "—"))
    if step == "product":
        return ("Product", (proposed.get("leasing_product", "") or "").replace("_", " ").title())
    if step == "asset":
        return ("Asset", vehicle_label(proposed.get("vehicle_key")) or str(proposed.get("vehicle_key") or "—"))
    if step == "commercial":
        parts: list[str] = []
        if proposed.get("term_months"):
            parts.append(f"{proposed['term_months']} mo")
        if proposed.get("quantity"):
            parts.append(f"{int(proposed['quantity'])}×")
        if proposed.get("annual_mileage_km"):
            parts.append(f"{int(proposed['annual_mileage_km']):,} km/yr")
        if float(proposed.get("special_payment_eur") or 0) > 0:
            parts.append(f"€{float(proposed['special_payment_eur']):,.0f} down")
        svc = [n for n, k in (("maintenance", "service_maintenance"), ("tyres", "service_tyres"),
                              ("insurance", "insurance")) if proposed.get(k)]
        if svc:
            parts.append(", ".join(svc))
        return ("Commercial terms", " · ".join(parts) or "confirmed")
    return None


# --- proposal helpers -------------------------------------------------------- #
def _num(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _merge(proposed: dict, intent) -> dict:
    """Merge a fresh extraction into the running proposal (new non-null values win).

    When the make/model changes, DROP the stale vehicle_key so it re-resolves; same for the customer
    when a new company is named (fixes 'change the car/customer' being ignored)."""
    if intent is None:
        return proposed
    if intent.make or intent.model:
        if intent.make:
            proposed["make"] = intent.make
        if intent.model:
            proposed["model"] = intent.model
        proposed["vehicle_key"] = None
        proposed["colour"] = None
    if intent.colour:
        proposed["colour"] = intent.colour
    if intent.company_hint:
        proposed["company_hint"] = intent.company_hint
        proposed["register_number"] = None
    if intent.objective:
        proposed["objective"] = intent.objective
    if intent.term_months:
        proposed["term_months"] = intent.term_months
    if intent.annual_mileage_km:
        proposed["annual_mileage_km"] = intent.annual_mileage_km
    if intent.quantity:
        proposed["quantity"] = intent.quantity
    if intent.special_payment_eur is not None:
        proposed["special_payment_eur"] = intent.special_payment_eur
    for f in ("service_maintenance", "service_tyres", "insurance"):
        v = getattr(intent, f, None)
        if v is not None:
            proposed[f] = v
    # flexible extensions (doc 13 §3.1): asset attribute filters, constraints (budget), ambiguities
    if getattr(intent, "asset_filters", None):
        filters = dict(proposed.get("filters") or {})
        filters.update({k: v for k, v in intent.asset_filters.items() if v not in (None, "")})
        proposed["filters"] = filters
    if getattr(intent, "constraints", None):
        proposed["constraints"] = [c.model_dump() if hasattr(c, "model_dump") else c
                                   for c in intent.constraints]
    if getattr(intent, "ambiguities", None):
        proposed["ambiguities"] = [a.model_dump() if hasattr(a, "model_dump") else a
                                   for a in intent.ambiguities]
    if intent.confidence:
        proposed["confidence"] = intent.confidence
    return proposed


def _resolve(proposed: dict) -> dict:
    if not proposed.get("vehicle_key"):
        proposed["vehicle_key"] = resolve_vehicle_key(proposed.get("make"), proposed.get("model"))
    if not proposed.get("register_number"):
        proposed["register_number"] = resolve_register(proposed.get("company_hint"))
    return proposed


def _apply_turn(proposed: dict, reply: dict) -> dict:
    """Fold one interrupt reply (free-text message and/or explicit overrides) into the proposal."""
    if not isinstance(reply, dict):
        reply = {"message": str(reply)}
    if reply.get("message"):
        proposed = _merge(proposed, understand(reply["message"]))
    for k, v in (reply.get("overrides") or {}).items():
        if v not in (None, ""):
            proposed[k] = v
    return _resolve(proposed)


def _filter_catalogue(proposed: dict) -> list[dict]:
    """Catalogue narrowed by any asset attribute filters the agent extracted (Phase 3 fills these;
    Phase 2 supports make/model hints + a generic `filters` map)."""
    rows = list_vehicles()
    mk, md = (proposed.get("make") or "").lower(), (proposed.get("model") or "").lower()
    if mk:
        rows = [r for r in rows if mk in r["make"].lower()]
    if md:
        rows = [r for r in rows if md in r["commercial_name"].lower()]
    for attr, want in (proposed.get("filters") or {}).items():
        if want in (None, ""):
            continue
        rows = [r for r in rows if str(r.get(attr, "")).lower() == str(want).lower()]
    return rows


def _proposed_from_offer(offer: Offer) -> dict:
    v, c, cu = offer.vehicle, offer.commercial, offer.customer
    return _resolve({
        "make": v.make.value, "model": v.commercial_name.value,
        "register_number": cu.register_number.value,
        "term_months": c.term_months.value, "annual_mileage_km": c.annual_mileage_km.value,
        "quantity": int(c.quantity.value or 1),
        "special_payment_eur": float(c.special_payment_eur.value or 0),
        "service_maintenance": bool(c.service_maintenance.value),
        "service_tyres": bool(c.service_tyres.value),
        "insurance": bool(c.insurance.value),
        "colour": offer.vehicle.colour.value,
        "channel": offer.channel.value, "business_line": offer.business_line_key.value,
        "leasing_product": offer.leasing_product_key.value,
        "asset_category": offer.asset_category_key.value,
        "objective": c.objective, "confidence": 1.0,
    })


# --- understand (no interrupt) ----------------------------------------------- #
def understand_node(state) -> dict:
    """Extract the initial request and pre-fill the wizard; structured creation skips the gates."""
    offer = _load(state)
    ac = offer.agent_context

    if state.get("intake_confirmed_initial"):
        proposed = _proposed_from_offer(offer)
        ac["proposed"] = proposed
        offer.agent_context = ac
        offer.workflow_status = WorkflowStatus.CONTEXT_COMPLETE
        _persist(offer, "INTAKE_CONFIRMED")
        return {"offer": _dump(offer), "intake_ready": True, "pending": None}

    proposed = dict(ac.get("proposed") or {})
    proposed.setdefault("channel", DEFAULT_CHANNEL)
    proposed.setdefault("business_line", DEFAULT_BUSINESS_LINE)
    proposed.setdefault("leasing_product", DEFAULT_PRODUCT)
    proposed.setdefault("asset_category", DEFAULT_ASSET_CATEGORY)
    text = state.get("nl_request")
    transcript = ac.get("messages", [])
    if text:
        transcript.append({"role": "user", "content": text})
        proposed = _merge(proposed, understand(text))
    proposed = _resolve(proposed)
    transcript.append({"role": "assistant",
                       "content": "Got it — I've filled in what I could. Confirm the fields, or just tell me "
                                  "any change here in the chat (e.g. “48 months”, “change the customer to …”, "
                                  "or “confirm all”)."})
    ac["messages"] = transcript
    ac["proposed"] = proposed
    offer.agent_context = ac
    offer.workflow_status = WorkflowStatus.UNDERSTANDING
    _persist(offer, "AGENT_UNDERSTOOD")
    return {"offer": _dump(offer), "intake_ready": False, "pending": None}


# --- single conversational intake turn (docs/16: state-driven, chat-first) --- #
_AFFIRM = {"yes", "y", "yep", "yeah", "ok", "okay", "confirm", "confirmed", "confirm all",
           "looks good", "sounds good", "correct", "sure", "do it", "agreed"}
_PROCEED = {"proceed", "generate", "go ahead", "go", "continue", "price it", "next", "done"}


def _detect_action(msg: str) -> str | None:
    """Lightweight affirmation/intent detection so the chat can confirm/proceed even without an LLM."""
    t = (msg or "").strip().lower().rstrip(".!")
    if t in _PROCEED or any(t.startswith(p + " ") for p in _PROCEED):
        return "proceed"
    if t in _AFFIRM or t.startswith("confirm"):
        return "confirm"
    return None


def agent_turn_node(state) -> dict:
    """The whole intake as one conversational turn over a field-state model. The human can set,
    confirm or edit ANY field here (chat or structured payload); an edit re-confirms only the fields it
    affects. Loops until every required field is confirmed, then hands off to assemble."""
    from app.agent import fieldstate as F
    offer = _load(state)
    ac = offer.agent_context
    proposed = _resolve(dict(ac.get("proposed") or {}))
    proposed.setdefault("channel", DEFAULT_CHANNEL)
    proposed.setdefault("leasing_product", DEFAULT_PRODUCT)
    fs = F.restore(ac, proposed)

    reply = interrupt({
        "type": "agent_turn", "reference": offer.reference,
        "field_state": F.public(fs, proposed),
        "pending": F.pending(fs),
        "focus": (F.pending(fs) or [None])[0],
        "proposed": proposed,
        "ambiguities": proposed.get("ambiguities", []),
        "transcript": ac.get("messages", []),
    })

    reply = reply if isinstance(reply, dict) else {"message": str(reply)}
    before = dict(proposed)
    user_fields: set[str] = set()

    # structured payload (from a card / quick action)
    for k, v in (reply.get("overrides") or {}).items():
        if v not in (None, ""):
            proposed[k] = v
    user_fields |= F.fields_for_keys((reply.get("overrides") or {}).keys())
    confirm_all = bool(reply.get("confirm"))
    confirm_fields: list[str] = [reply["confirm_field"]] if reply.get("confirm_field") else []
    proceed = bool(reply.get("proceed"))
    agent_reply: str | None = None

    # free-text chat turn — the agent interprets intent (set / confirm / proceed / answer questions)
    msg = reply.get("message")
    if msg:
        ac.setdefault("messages", []).append({"role": "user", "content": msg})
        plan = plan_turn(msg, F.summary(fs, proposed), F.options_summary())
        if plan is not None:
            for k, v in (plan.set or {}).items():
                if k in _TURN_SET_KEYS and v not in (None, ""):
                    proposed[k] = v
            if "make" in plan.set or "model" in plan.set:
                proposed["vehicle_key"] = None      # re-resolve the asset from the new make/model
            if "company_hint" in plan.set:
                proposed["register_number"] = None  # re-resolve the customer from the new name
            user_fields |= F.fields_for_keys((plan.set or {}).keys())
            confirm_fields += [f for f in (plan.confirm or []) if f in F.LABELS]
            confirm_all = confirm_all or bool(plan.confirm_all)
            proceed = proceed or bool(plan.proceed)
            agent_reply = (plan.reply or "").strip() or None
        else:                                       # no LLM: deterministic affirmation only
            intent = understand(msg)
            if intent is not None:
                proposed = _merge(proposed, intent)
            act = _detect_action(msg)
            if act == "confirm":
                confirm_all = True
            elif act == "proceed":
                proceed = True

    # derive product hierarchy + re-resolve keys, then fold into the status map
    proposed = F.derive_product(proposed, before)
    proposed = _resolve(proposed)
    user_fields |= F.changed_fields(before, proposed)          # any value the human's turn changed
    fs, ripple = F.apply(fs, before, proposed, user_fields=user_fields,
                         confirm=confirm_all, confirm_field=None)
    for f in confirm_fields:                                    # per-field confirmations (chat or card)
        if f in fs:
            fs[f]["status"] = "confirmed"

    # if the human asked to proceed, treat remaining agent-proposals as accepted
    if proceed:
        for f in fs:
            if fs[f].get("status") == "proposed":
                fs[f]["status"] = "confirmed"

    if agent_reply:
        nxt = F.next_prompt(fs, proposed)
        line = agent_reply if ("price it" in agent_reply.lower() or nxt in agent_reply) \
            else agent_reply.rstrip(". ") + ". " + nxt
    else:
        line = F.echo(ripple, fs, proposed)
    if line:
        ac.setdefault("messages", []).append({"role": "assistant", "content": line})

    ready = F.is_ready(fs)
    ac["proposed"] = proposed
    ac["field_state"] = fs
    offer.agent_context = ac
    offer.workflow_status = WorkflowStatus.CONTEXT_COMPLETE if ready else WorkflowStatus.UNDERSTANDING
    _persist(offer, "AGENT_TURN")
    return {"offer": _dump(offer), "intake_ready": ready, "pending": None}


# --- per-step confirm gates (legacy; retained for reference, not wired) ------- #
def _is_empty(v) -> bool:
    if isinstance(v, tuple):
        return all(x in (None, "") for x in v)
    return v in (None, "")


def _finish_step(offer: Offer, ac: dict, proposed: dict, step: str, ok: bool, event: str) -> dict:
    if ok:
        # Edit vs. plain set: compare against the pre-turn proposal (ac["proposed"] is untouched here —
        # the node worked on a copy — so a changed value means the human edited the agent's proposal).
        before = _step_value(step, ac.get("proposed") or {})
        edited = not _is_empty(before) and _step_value(step, proposed) != before
        summ = _confirm_summary(step, proposed)
        if summ:
            ac.setdefault("messages", []).append({
                "role": "user", "kind": "confirm", "title": summ[0],
                "content": f"Confirmed {summ[0].lower()}", "detail": summ[1], "edited": edited})
        msg = _confirm_echo(step, proposed)
        if msg:
            ac.setdefault("messages", []).append({"role": "assistant", "content": msg})
    ac["proposed"] = proposed
    offer.agent_context = ac
    offer.workflow_status = WorkflowStatus.CONTEXT_REQUIRED if not ok else WorkflowStatus.UNDERSTANDING
    _persist(offer, event)
    return {"offer": _dump(offer), "pending": None, "step": step, "step_ok": ok, "goto_step": None}


def select_channel_node(state) -> dict:
    offer = _load(state)
    ac = offer.agent_context
    proposed = dict(ac.get("proposed") or {})
    proposed.setdefault("channel", DEFAULT_CHANNEL)
    ref = load_reference_data()
    reply = interrupt({
        "type": "confirm_step", "step": "channel", "reference": offer.reference,
        "title": "Sales channel",
        "prompt": "Which sales channel is this offer created through?",
        "options": [{"key": c.key, "label": c.name_en, "status": c.status} for c in ref.channels],
        "value": proposed.get("channel"), "missing": [], "proposed": proposed,
        "transcript": ac.get("messages", []),
    })
    g = _goto(reply, "channel")
    if g:
        return {"offer": _dump(offer), "pending": None, "step": "channel", "goto_step": g, "step_ok": False}
    proposed = _apply_turn(proposed, reply)
    proposed.setdefault("channel", DEFAULT_CHANNEL)
    ok = bool(reply.get("confirm")) if isinstance(reply, dict) else False
    if ok:
        offer.channel = _ref_seed(proposed["channel"])
    return _finish_step(offer, ac, proposed, "channel", ok, "STEP_CHANNEL")


def select_partner_node(state) -> dict:
    offer = _load(state)
    ac = offer.agent_context
    proposed = _resolve(dict(ac.get("proposed") or {}))
    q = proposed.get("company_hint") or proposed.get("register_number")
    ref = load_reference_data()
    channel = ref.channel(proposed.get("channel") or DEFAULT_CHANNEL)
    partner_kind = channel.partner_kind if channel else "business_partner"
    # Show matches when the agent has a name to go on; otherwise show the whole partner directory so
    # the user can just pick (spec §3.4: for internal sales the Business Partner is loaded from the
    # directory; partner/credit channels create a minimal Offer Partner — MVP uses the same catalogue).
    matches = search_partners(q)
    candidates = matches if matches else list_customers()
    reply = interrupt({
        "type": "confirm_step", "step": "partner", "reference": offer.reference,
        "title": "Customer / partner",
        "prompt": ("The customer is the leasing partner this offer is for. "
                   + ("Pick the business partner from the directory, search, or tell me the name."
                      if partner_kind == "business_partner"
                      else "This channel creates an offer partner — pick one or tell me the name.")),
        "partner_kind": partner_kind,
        "query": q, "candidates": candidates, "is_search": bool(matches),
        "selected": proposed.get("register_number"),
        "selected_label": customer_label(proposed.get("register_number")),
        "missing": [] if proposed.get("register_number") else ["register_number"],
        "ambiguities": proposed.get("ambiguities", []),
        "proposed": proposed, "transcript": ac.get("messages", []),
    })
    g = _goto(reply, "partner")
    if g:
        return {"offer": _dump(offer), "pending": None, "step": "partner", "goto_step": g, "step_ok": False}
    proposed = _apply_turn(proposed, reply)
    cands = search_partners(proposed.get("company_hint") or proposed.get("register_number"))
    if not proposed.get("register_number") and len(cands) == 1:      # unambiguous -> auto-pick
        proposed["register_number"] = cands[0]["register_number"]
    ok = bool(reply.get("confirm")) and bool(proposed.get("register_number"))
    return _finish_step(offer, ac, proposed, "partner", ok, "STEP_PARTNER")


def select_product_node(state) -> dict:
    offer = _load(state)
    ac = offer.agent_context
    proposed = dict(ac.get("proposed") or {})
    proposed.setdefault("leasing_product", DEFAULT_PRODUCT)
    ref = load_reference_data()
    reply = interrupt({
        "type": "confirm_step", "step": "product", "reference": offer.reference,
        "title": "Business line & product",
        "prompt": "Confirm the business line and leasing product (its parameters govern the offer).",
        "business_lines": [{"key": b.key, "label": b.name_en, "status": b.status}
                           for b in ref.business_lines],
        "products": [{"key": p.key, "label": p.name_en, "business_line": p.business_line,
                      "asset_category": p.asset_category, "status": p.status}
                     for p in ref.leasing_products],
        "value": proposed.get("leasing_product"), "missing": [], "proposed": proposed,
        "transcript": ac.get("messages", []),
    })
    g = _goto(reply, "product")
    if g:
        return {"offer": _dump(offer), "pending": None, "step": "product", "goto_step": g, "step_ok": False}
    proposed = _apply_turn(proposed, reply)
    proposed.setdefault("leasing_product", DEFAULT_PRODUCT)
    prod = ref.product(proposed.get("leasing_product"))
    ok = bool(reply.get("confirm")) and prod is not None and prod.is_active
    if ok:
        offer.leasing_product_key = _ref_seed(prod.key)
        offer.business_line_key = _ref_seed(prod.business_line)
        offer.asset_category_key = _ref_seed(prod.asset_category)
        offer.policy_version = prod.policy_id
        proposed["business_line"] = prod.business_line
        proposed["asset_category"] = prod.asset_category
    return _finish_step(offer, ac, proposed, "product", ok, "STEP_PRODUCT")


def select_asset_node(state) -> dict:
    offer = _load(state)
    ac = offer.agent_context
    proposed = _resolve(dict(ac.get("proposed") or {}))
    ref = load_reference_data()
    cat = ref.asset_category(proposed.get("asset_category") or DEFAULT_ASSET_CATEGORY)
    reply = interrupt({
        "type": "confirm_step", "step": "asset", "reference": offer.reference,
        "title": "Asset",
        "prompt": "Confirm the asset. Filter by attributes or tell me what you need.",
        "asset_category": cat.key if cat else DEFAULT_ASSET_CATEGORY,
        "attribute_schema": [a.model_dump() for a in (cat.attribute_schema if cat else [])],
        "catalogue": _filter_catalogue(proposed),
        "filters": proposed.get("filters") or {},
        "selected": proposed.get("vehicle_key"),
        "selected_label": vehicle_label(proposed.get("vehicle_key")),
        "colour": proposed.get("colour"),
        "missing": [] if proposed.get("vehicle_key") else ["vehicle_key"],
        "ambiguities": proposed.get("ambiguities", []),
        "proposed": proposed, "transcript": ac.get("messages", []),
    })
    g = _goto(reply, "asset")
    if g:
        return {"offer": _dump(offer), "pending": None, "step": "asset", "goto_step": g, "step_ok": False}
    proposed = _apply_turn(proposed, reply)
    ok = bool(reply.get("confirm")) and bool(proposed.get("vehicle_key"))
    return _finish_step(offer, ac, proposed, "asset", ok, "STEP_ASSET")


def select_commercial_node(state) -> dict:
    offer = _load(state)
    ac = offer.agent_context
    proposed = dict(ac.get("proposed") or {})
    proposed.setdefault("quantity", 1)
    missing = [f for f in ("term_months", "annual_mileage_km") if not proposed.get(f)]
    reply = interrupt({
        "type": "confirm_step", "step": "commercial", "reference": offer.reference,
        "title": "Commercial requirements",
        "prompt": "Confirm term, mileage, quantity and any services / insurance. "
                  "You can also give me a budget and I'll find scenarios that fit.",
        "value": {k: proposed.get(k) for k in (
            "term_months", "annual_mileage_km", "quantity", "special_payment_eur",
            "service_maintenance", "service_tyres", "insurance")},
        "constraints": proposed.get("constraints") or [],
        "ambiguities": proposed.get("ambiguities", []),
        "missing": missing, "proposed": proposed, "transcript": ac.get("messages", []),
    })
    g = _goto(reply, "commercial")
    if g:
        return {"offer": _dump(offer), "pending": None, "step": "commercial", "goto_step": g, "step_ok": False}
    proposed = _apply_turn(proposed, reply)
    proposed.setdefault("quantity", 1)
    missing = [f for f in ("term_months", "annual_mileage_km") if not proposed.get(f)]
    ok = bool(reply.get("confirm")) and not missing
    return _finish_step(offer, ac, proposed, "commercial", ok, "STEP_COMMERCIAL")


# --- assemble (no interrupt) ------------------------------------------------- #
def _assemble(offer: Offer, proposed: dict) -> Offer:
    try:
        sp_dec = Decimal(str(proposed.get("special_payment_eur") or 0))
    except InvalidOperation:
        sp_dec = Decimal("0")
    fresh = build_b2b_offer(
        _REGISTRY, vehicle_key=proposed["vehicle_key"], register_number=proposed["register_number"],
        term_months=int(proposed["term_months"]), annual_mileage_km=int(proposed["annual_mileage_km"]),
        quantity=int(proposed.get("quantity") or 1), special_payment_eur=sp_dec,
        service_maintenance=bool(proposed.get("service_maintenance")),
        service_tyres=bool(proposed.get("service_tyres")),
        insurance=bool(proposed.get("insurance")),
        colour=proposed.get("colour"))
    offer.customer = fresh.customer
    offer.vehicle = fresh.vehicle
    offer.commercial = fresh.commercial
    if proposed.get("objective"):
        offer.commercial.objective = proposed["objective"]
    return offer


def assemble_node(state) -> dict:
    offer = _load(state)
    proposed = offer.agent_context.get("proposed", {})
    offer = _assemble(offer, proposed)
    offer.workflow_status = WorkflowStatus.CONTEXT_COMPLETE
    ac = offer.agent_context
    ac.setdefault("messages", []).append(
        {"role": "assistant", "content": f"Confirmed. Pricing {vehicle_label(proposed.get('vehicle_key'))} now…"})
    offer.agent_context = ac
    _persist(offer, "INTAKE_ASSEMBLED")
    return {"offer": _dump(offer), "intake_ready": True, "pending": None}


# --- explain nodes (read-only, grounded) -------------------------------------- #
def _correction_message(offer: Offer) -> str:
    codes = {e.code for e in offer.exceptions if e.blocking}
    if "TERM_OUT_OF_RANGE" in codes:
        return "That term is outside the allowed range (12–60 months). Give me a valid term."
    if "MILEAGE_OUT_OF_RANGE" in codes:
        return "That annual mileage is out of policy (max 40,000 km). Give me a lower figure."
    if any(c in codes for c in ("SPECIAL_PAYMENT_TOO_HIGH", "PRODUCT_INELIGIBLE")):
        return "The special payment is too high (over 30% of the price). Lower it and I'll re-price."
    if offer.scoring and offer.scoring.value.band is RiskBand.RED:
        return ("This is Red on affordability/exposure. I can try a cheaper vehicle, a shorter term, "
                "a lower mileage, or a higher special payment — tell me which and I'll re-price.")
    return "I couldn't price this as-is. Adjust a detail and I'll try again."


def explain_pricing_node(state) -> dict:
    offer = _load(state)
    if offer.calculation is None and not _compliance_blocked(offer):
        ac = offer.agent_context
        ac.setdefault("messages", []).append({"role": "assistant", "content": _correction_message(offer)})
        offer.agent_context = ac
    offer.agent_context["explanation_pricing"] = explain.explain_pricing(offer)
    _persist(offer, "AGENT_EXPLAINED_PRICING")
    return {"offer": _dump(offer)}


def _scenario_summary(offer: Offer) -> str | None:
    """A quick, human summary of the priced options for the chat (a glanceable recap)."""
    scns = [s for s in (offer.scenarios or []) if s.calculation]
    if not scns:
        return None
    band = offer.scoring.value.band.value if offer.scoring else ""
    lowest = min(scns, key=lambda s: s.calculation.value.monthly_gross_eur)
    parts = [f"{s.label} €{s.calculation.value.monthly_gross_eur}/mo"
             + (" (lowest)" if s.id == lowest.id else "") for s in scns]
    return (f"Priced {len(scns)} option{'s' if len(scns) != 1 else ''} · band {band}: "
            + " · ".join(parts)
            + ". Pick one on the left, tell me which, or say “generate”.")


def explain_scenarios_node(state) -> dict:
    offer = _load(state)
    offer.agent_context["explanation_scenarios"] = explain.explain_scenarios(offer)
    summ = _scenario_summary(offer)
    if summ:
        offer.agent_context.setdefault("messages", []).append({"role": "assistant", "content": summ})
    _persist(offer, "AGENT_EXPLAINED_SCENARIOS")
    return {"offer": _dump(offer)}


def _compliance_blocked(offer: Offer) -> bool:
    return bool(offer.scoring and offer.scoring.value.band is RiskBand.RED
                and offer.scoring.value.red_kind and offer.scoring.value.red_kind.value == "COMPLIANCE")


# --- routers ----------------------------------------------------------------- #
def route_after_understand(state) -> str:
    return "run_pipeline" if state.get("intake_ready") else "agent_turn"


def route_after_turn(state) -> str:
    """One conversational intake turn: loop until every required field is confirmed, then assemble."""
    return "assemble" if state.get("intake_ready") else "agent_turn"


def _step_router(step: str):
    def _r(state) -> str:
        g = state.get("goto_step")
        if g and g in STEPS and g != step:
            return _STEP_NODE[g]            # jump back to edit an earlier step
        return _NEXT_STEP[step] if state.get("step_ok") else _STAY[step]
    return _r


route_after_channel = _step_router("channel")
route_after_partner = _step_router("partner")
route_after_product = _step_router("product")
route_after_asset = _step_router("asset")
route_after_commercial = _step_router("commercial")


def route_after_pipeline(state) -> str:
    offer = _load(state)
    if offer.calculation is not None:
        return "scenarios"
    if _compliance_blocked(offer):
        return "final_validation"      # hard compliance block -> terminal
    return "agent_turn"                # economic RED / out-of-range -> reopen the chat to adjust
