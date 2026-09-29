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

import re
from decimal import Decimal, InvalidOperation

from langgraph.types import interrupt

from app.agent import explain
from app.agent.extract import understand
from app.agent.turn import SET_KEYS as _TURN_SET_KEYS, plan_turn
from app.agent.resolve import (
    customer_label,
    list_customers,
    list_vehicles,
    recommend_default_customer,
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


def _merge(proposed: dict, intent, *, source_text: str = "") -> dict:
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
        proposed["vehicle_recommended"] = False
    if intent.colour:
        proposed["colour"] = intent.colour
    if intent.company_hint:
        proposed["company_hint"] = intent.company_hint
        proposed["register_number"] = None
        proposed["customer_recommended"] = False
    if intent.objective:
        proposed["objective"] = intent.objective
    years = re.search(r"\b(\d+)\s*(?:years?|yrs?)\b", source_text.lower()) if source_text else None
    if years:
        proposed["term_months"] = int(years.group(1)) * 12
    elif intent.term_months:
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
        proposed["vehicle_recommended"] = False
    if getattr(intent, "constraints", None):
        proposed["constraints"] = [c.model_dump() if hasattr(c, "model_dump") else c
                                   for c in intent.constraints]
        text = source_text.lower()
        if any(p in text for p in ("per year", "a year", "annual", "annually", "yearly", "/year")):
            basis = "annual"
        elif any(p in text for p in ("per month", "a month", "monthly", "/month")):
            basis = "monthly"
        elif "per vehicle" in text or "per car" in text:
            basis = "per_vehicle"
        elif any(p in text for p in ("whole contract", "total contract", "over the contract")):
            basis = "total"
        else:
            basis = None
        if basis:
            for constraint in proposed["constraints"]:
                if (constraint.get("kind") or "").lower() in ("budget", "monthly_cap"):
                    constraint["basis"] = basis
    if getattr(intent, "ambiguities", None):
        proposed["ambiguities"] = [a.model_dump() if hasattr(a, "model_dump") else a
                                   for a in intent.ambiguities]
    if intent.confidence:
        proposed["confidence"] = intent.confidence
    return proposed


def _resolve(proposed: dict) -> dict:
    if not proposed.get("vehicle_key"):
        proposed["vehicle_key"] = resolve_vehicle_key(proposed.get("make"), proposed.get("model"))
    if not proposed.get("vehicle_key") and proposed.get("filters"):
        matches = _filter_catalogue(proposed)
        if len(matches) == 1:
            proposed["vehicle_key"] = matches[0]["key"]
            proposed["make"] = matches[0]["make"]
            proposed["model"] = matches[0]["commercial_name"]
    if not proposed.get("register_number"):
        proposed["register_number"] = resolve_register(proposed.get("company_hint"))
    return proposed


def _catalogue_answer(message: str, proposed: dict) -> str | None:
    """Answer catalogue questions from the same controlled data used by the intake UI."""
    text = (message or "").lower()
    asks_options = any(word in text for word in ("option", "available", "list", "which", "what are"))
    if not asks_options:
        return None
    if any(word in text for word in ("customer", "company", "partner", "client")):
        rows = list_customers()
        names = "; ".join(c["legal_name"] for c in rows)
        return f"Available customers ({len(rows)}): {names}. Choose one in the wizard or tell me the customer name."
    if any(word in text for word in ("vehicle", "car", "asset", "model")):
        rows = list_vehicles()
        return "Available vehicles: " + "; ".join(v["label"] for v in rows) + ". Choose one in the wizard."
    if "channel" in text:
        ref = load_reference_data()
        choices = "; ".join(c.name_en for c in ref.channels if c.status == "active")
        current = ref.channel(proposed.get("channel"))
        selected = f" Current selection: {current.name_en}." if current else ""
        return "Channel options: " + choices + "." + selected
    if "product" in text:
        ref = load_reference_data()
        return "Available active products: " + "; ".join(p.name_en for p in ref.active_products()) + "."
    return None


_CONFIRM_FIELD_TERMS = {
    "channel": ("channel",), "customer": ("customer", "company", "client", "partner"),
    "product": ("product",), "asset": ("asset", "vehicle", "car", "model"),
    "term": ("term", "duration", "months"), "mileage": ("mileage", "km"),
    "quantity": ("quantity", "fleet", "cars"),
    "special_payment": ("special payment", "deposit", "down payment"),
    "maintenance": ("maintenance",), "tyres": ("tyres", "tires"),
    "insurance": ("insurance",),
}


def _mentioned_confirmation_fields(message: str) -> list[str]:
    text = (message or "").lower()
    return [field for field, terms in _CONFIRM_FIELD_TERMS.items()
            if any(term in text for term in terms)]


def _confirmation_scope(message: str) -> tuple[bool, list[str], bool]:
    """Return (confirm_all, explicitly_named_fields, needs_clarification).

    A conversational confirmation never guesses its target from the current wizard position. If no
    field is named, the agent must ask which field the user means.
    """
    text = (message or "").lower().replace("’", "'")
    explicit_all = any(phrase in text for phrase in (
        "confirm all", "confirm everything", "approve all", "all fields", "everything is correct",
        "everything looks good", "looks good, confirm all"))
    if explicit_all:
        return True, [], False
    named = _mentioned_confirmation_fields(text)
    bare_affirmation = text.strip(" .,!?") in {"yes", "y", "yep", "yeah", "ok", "okay", "sure"}
    has_confirmation_verb = any(word in text for word in (
        "confirm", "confirming", "confirmed", "confirmation"))
    is_confirmation = (bare_affirmation or has_confirmation_verb
                       or (bool(named) and any(word in text for word in ("correct", "agree", "agreed"))))
    if not is_confirmation:
        return False, [], False
    if named:
        return False, named, False
    return False, [], True


def _recommend_default_vehicle(proposed: dict) -> tuple[dict, str | None]:
    """Propose the lowest listed-price vehicle when a fleet request omits its asset."""
    if proposed.get("vehicle_key") or not proposed.get("quantity"):
        return proposed, None
    if proposed.get("make") or proposed.get("model") or proposed.get("filters"):
        return proposed, None
    rows = list_vehicles()
    if not rows:
        return proposed, None
    vehicle = min(rows, key=lambda row: Decimal(str(row.get("list_price_net") or "Infinity")))
    proposed["vehicle_key"] = vehicle["key"]
    proposed["make"] = vehicle["make"]
    proposed["model"] = vehicle["commercial_name"]
    proposed["vehicle_recommended"] = True
    message = f"Suggested vehicle: {vehicle['label']}. You can confirm or change it in the wizard."
    return proposed, message


def _recommend_default_customer(proposed: dict) -> tuple[dict, str | None]:
    """Suggest a configured customer profile sized to the preliminary fleet exposure, if possible."""
    if proposed.get("register_number") or proposed.get("company_hint"):
        return proposed, None
    quantity = int(proposed.get("quantity") or 0)
    vehicle = next((v for v in list_vehicles() if v["key"] == proposed.get("vehicle_key")), None)
    rough_exposure = (Decimal(str(vehicle.get("list_price_net"))) * quantity
                      if vehicle and quantity > 0 else None)
    customer = recommend_default_customer(rough_exposure)
    if not customer:
        return proposed, None
    proposed["register_number"] = customer["register_number"]
    proposed["customer_recommended"] = True
    return proposed, (
        f"Suggested customer: {customer['legal_name']}. You can confirm or change it in the wizard."
    )


def _initial_agent_message() -> str:
    """Keep the opening focused on the next action; the wizard shows values and recommendations."""
    return "I’ve captured your request. Please answer or confirm each question in the wizard to continue with the offer calculation."


def _apply_turn(proposed: dict, reply: dict) -> dict:
    """Fold one interrupt reply (free-text message and/or explicit overrides) into the proposal."""
    if not isinstance(reply, dict):
        reply = {"message": str(reply)}
    if reply.get("message"):
        proposed = _merge(proposed, understand(reply["message"]))
    for k, v in (reply.get("overrides") or {}).items():
        if v not in (None, ""):
            proposed[k] = v
    if any(k in (reply.get("overrides") or {}) for k in ("vehicle_key", "make", "model")):
        proposed["vehicle_recommended"] = False
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
        proposed = _merge(proposed, understand(text), source_text=text)
    proposed = _resolve(proposed)
    proposed, asset_note = _recommend_default_vehicle(proposed)
    proposed, customer_note = _recommend_default_customer(proposed)
    transcript.append({"role": "assistant",
                       "content": _initial_agent_message()})
    ac["messages"] = transcript
    ac["proposed"] = proposed
    offer.agent_context = ac
    offer.workflow_status = WorkflowStatus.UNDERSTANDING
    _persist(offer, "AGENT_UNDERSTOOD")
    return {"offer": _dump(offer), "intake_ready": False, "pending": None}


# --- single conversational intake turn (docs/16: state-driven, chat-first) --- #
def _explicit_pricing_confirmation(message: str) -> bool:
    """Require a distinct user turn to start calculation after intake is complete."""
    text = re.sub(r"[^a-z0-9]+", " ", (message or "").lower()).strip()
    exact = {
        "price it", "calculate", "calculate it", "calculate pricing", "calculate scenarios",
        "start calculating", "start calculation", "start pricing", "run pricing",
        "yes calculate", "yes calculate it", "yes calculate pricing", "yes calculate scenarios",
        "yes start calculating", "yes start pricing", "go ahead and calculate",
        "go ahead and price it", "please calculate", "please calculate it",
        "please calculate pricing", "please start calculating", "confirm and price it",
    }
    if text in exact:
        return True
    return bool(re.fullmatch(
        r"(?:(?:yes|please|okay|ok|go ahead|can you|could you|let s)\s+)*(?:start\s+)?"
        r"(?:calculat(?:e|ing|ion)(?:\s+(?:the\s+)?(?:pricing|scenarios?))?|"
        r"pric(?:e it|ing)|run pricing)(?:\s+now)?",
        text,
    ))


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
    if any(k in (reply.get("overrides") or {}) for k in ("company_hint", "register_number")):
        proposed["customer_recommended"] = False
    user_fields |= F.fields_for_keys((reply.get("overrides") or {}).keys())
    confirm_all = bool(reply.get("confirm"))
    confirm_fields: list[str] = [reply["confirm_field"]] if reply.get("confirm_field") else []
    proceed = bool(reply.get("proceed"))
    agent_reply: str | None = None
    standalone_reply = False

    # free-text chat turn — the agent interprets intent (set / confirm / proceed / answer questions)
    msg = reply.get("message")
    if msg:
        ac.setdefault("messages", []).append({"role": "user", "content": msg})
        scoped_all, scoped_fields, ambiguous_confirmation = _confirmation_scope(msg)
        awaiting_target = bool(ac.get("awaiting_confirmation_field"))
        clarification_fields = _mentioned_confirmation_fields(msg) if awaiting_target else []
        if awaiting_target:
            if clarification_fields:
                ac.pop("awaiting_confirmation_field", None)
                confirm_fields += clarification_fields
                missing_values = [f for f in clarification_fields if not F._has(f, proposed)]
                if missing_values:
                    labels = ", ".join(F.LABELS[f] for f in missing_values)
                    catalogue_answer = (f"I can't confirm {labels} yet because no usable value is set. "
                                        "Please provide or select that value.")
                else:
                    labels = ", ".join(F.LABELS[f] for f in clarification_fields)
                    catalogue_answer = f"Understood. I'll confirm {labels} only."
            else:
                catalogue_answer = ("Please name the field you want me to confirm, such as Customer, "
                                    "Product, Vehicle, or Term. I haven't changed any fields.")
            standalone_reply = True
        elif ambiguous_confirmation:
            ac["awaiting_confirmation_field"] = True
            catalogue_answer = ("I’m not sure which field you mean. Please name the field you want "
                                "me to confirm, such as Customer, Product, Vehicle, or Term.")
            standalone_reply = True
        else:
            catalogue_answer = _catalogue_answer(msg, proposed)
        pricing_confirmation = _explicit_pricing_confirmation(msg)
        plan = None if catalogue_answer or pricing_confirmation else plan_turn(
            msg, F.summary(fs, proposed), F.options_summary())
        if plan is not None:
            for k, v in (plan.set or {}).items():
                if k in _TURN_SET_KEYS and v not in (None, ""):
                    proposed[k] = v
            if "make" in plan.set or "model" in plan.set:
                proposed["vehicle_key"] = None      # re-resolve the asset from the new make/model
                proposed["vehicle_recommended"] = False
            elif "vehicle_key" in plan.set:
                proposed["vehicle_recommended"] = False
            if "company_hint" in plan.set:
                proposed["register_number"] = None  # re-resolve the customer from the new name
                proposed["customer_recommended"] = False
            user_fields |= F.fields_for_keys((plan.set or {}).keys())
            explicit_field_confirm = bool(scoped_all or scoped_fields)
            confirm_fields += ([f for f in (plan.confirm or []) if f in F.LABELS]
                               if not explicit_field_confirm else scoped_fields)
            confirm_all = confirm_all or scoped_all
            # A planner's generic `proceed` classification is not consent to price. The user
            # must make a clear pricing request in this separate turn.
            proceed = proceed or pricing_confirmation
            agent_reply = (plan.reply or "").strip() or None
        else:                                       # no LLM: deterministic affirmation only
            if catalogue_answer:
                agent_reply = catalogue_answer
            else:
                if scoped_all or scoped_fields:
                    confirm_all = confirm_all or scoped_all
                    confirm_fields += scoped_fields
                elif not pricing_confirmation:
                    intent = understand(msg)
                    if intent is not None:
                        proposed = _merge(proposed, intent, source_text=msg)
                if not scoped_all and not scoped_fields and pricing_confirmation:
                    proceed = True

    # derive product hierarchy + re-resolve keys, then fold into the status map
    proposed = F.derive_product(proposed, before)
    proposed = _resolve(proposed)
    user_fields |= F.changed_fields(before, proposed)          # any value the human's turn changed
    if proposed.get("company_hint") != before.get("company_hint"):
        # A chat assignment updates the customer proposal, then the user can explicitly confirm it
        # in the next turn. Structured customer selection remains an explicit user confirmation.
        user_fields.discard("customer")
    fs, ripple = F.apply(fs, before, proposed, user_fields=user_fields,
                         confirm=confirm_all, confirm_field=None)
    for f in confirm_fields:                                    # per-field confirmations (chat or card)
        if f in fs and F._has(f, proposed):
            fs[f]["status"] = "confirmed"

    # Record structured wizard actions as user messages too, so the chosen values stay visible
    # in the shared chat transcript (not just in the field panel).
    structured_fields = user_fields | set(confirm_fields)
    if confirm_all:
        structured_fields |= {f for f, status in fs.items()
                              if status.get("status") == "confirmed" and F._has(f, proposed)}
    if not msg:
        for field in F.ORDER:
            if field not in structured_fields or not F._has(field, proposed):
                continue
            value = F.display(field, proposed)
            action = "Selected" if field in confirm_fields or confirm_all else "Set"
            ac.setdefault("messages", []).append({
                "role": "user", "content": f"{action} {F.LABELS[field]}: {value}"})

    # Completing the last field is not consent to start pricing. Only an explicit pricing
    # confirmation on this turn may hand off to the deterministic calculation graph.
    all_confirmed = F.is_ready(fs)
    start_pricing = all_confirmed and proceed

    if agent_reply and standalone_reply:
        line = agent_reply
    elif start_pricing:
        line = "All required fields are confirmed. I’ll calculate the pricing scenario now."
    elif all_confirmed:
        recap_fields = ("channel", "customer", "product", "asset", "term", "mileage", "quantity",
                        "special_payment", "maintenance", "tyres", "insurance")
        recap = "; ".join(
            f"{F.LABELS[field]}: {F.display(field, proposed) or 'not provided'}"
            for field in recap_fields)
        budgets = [c for c in (proposed.get("constraints") or [])
                   if (c.get("kind") or "").lower() in ("budget", "monthly_cap")]
        if budgets:
            budget = budgets[-1]
            recap += f"; Budget: {budget.get('currency') or 'EUR'} {budget.get('value')} ({budget.get('basis') or 'basis not specified'})"
        line = ("Everything is confirmed: " + recap
                + ". Should I start the pricing calculation? Reply ‘yes, calculate’ or ‘price it’.")
    elif agent_reply:
        nxt = F.next_prompt(fs, proposed)
        line = agent_reply if ("price it" in agent_reply.lower() or nxt in agent_reply) \
            else agent_reply.rstrip(". ") + ". " + nxt
    else:
        line = F.echo(ripple, fs, proposed)
    if line:
        ac.setdefault("messages", []).append({"role": "assistant", "content": line})

    ready = start_pricing
    ac["proposed"] = proposed
    ac["field_state"] = fs
    offer.agent_context = ac
    offer.workflow_status = WorkflowStatus.CONTEXT_COMPLETE if start_pricing else WorkflowStatus.UNDERSTANDING
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
    if (offer.scoring and offer.scoring.value.band is RiskBand.RED
            and offer.scoring.value.red_kind and offer.scoring.value.red_kind.value == "COMPLIANCE"):
        hard_blocks = set(offer.scoring.value.hard_blocks or [])
        if "SANCTIONS_MATCH" in hard_blocks:
            message = ("The selected customer matched the configured sanctions screening records, so this offer is "
                       "blocked for compliance (risk score 0). Changing the vehicle or lease terms will not "
                       "clear a customer-level match; confirm the intended customer and follow compliance review.")
            manual = next((e for e in offer.exceptions if e.code == "SCORING_MANUAL_REVIEW"), None)
            reasons = (manual.detail or {}).get("reasons", []) if manual else []
            if reasons:
                message += " Separately, these figures require manual review: " + "; ".join(reasons) + "."
            return message
        if "KYC_FAILED" in hard_blocks:
            return "The selected customer failed KYC checks, so this offer is blocked for compliance. Resolve KYC before starting a new offer."
        if "COMPANY_INSOLVENT" in hard_blocks:
            return "The selected customer is marked insolvent in the risk data, so this offer is blocked for compliance."
    if offer.scoring and offer.scoring.value.band is RiskBand.RED:
        return ("This is Red on affordability/exposure. I can try a cheaper vehicle, a shorter term, "
                "a lower mileage, or a higher special payment — tell me which and I'll re-price.")
    return "I couldn't price this as-is. Adjust a detail and I'll try again."


def explain_pricing_node(state) -> dict:
    offer = _load(state)
    if offer.calculation is None:
        ac = offer.agent_context
        ac.setdefault("messages", []).append({"role": "assistant", "content": _correction_message(offer)})
        offer.agent_context = ac
    offer.agent_context["explanation_pricing"] = explain.explain_pricing(offer)
    _persist(offer, "AGENT_EXPLAINED_PRICING")
    return {"offer": _dump(offer)}


def _scenario_summary(offer: Offer) -> str | None:
    """A quick, human summary of the priced scenario(s) for the chat."""
    scns = [s for s in (offer.scenarios or []) if s.calculation]
    if not scns:
        return None
    band = offer.scoring.value.band.value if offer.scoring else ""
    lowest = min(scns, key=lambda s: s.calculation.value.monthly_gross_eur)
    parts = [f"{s.label} €{s.calculation.value.monthly_gross_eur}/mo"
             + (" (lowest)" if s.id == lowest.id else "") for s in scns]
    if len(scns) == 1:
        return (f"Calculated the requested {scns[0].term_months}-month terms · band {band}: "
                + parts[0] + ". Review the result on the left, then choose whether to generate the offer.")
    return (f"Priced {len(scns)} options · band {band}: " + " · ".join(parts)
            + ". These options are shown on the left for review.")


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
