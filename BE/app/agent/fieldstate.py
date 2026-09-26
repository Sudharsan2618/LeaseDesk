"""Field-level intake state + dependency model (docs/16).

The intake is a single conversational turn where the human can set/confirm/edit ANY field at any
time. Values still live in `agent_context["proposed"]` (what `_assemble` reads); this module keeps a
parallel status map `agent_context["field_state"]` so the agent can ask the human to confirm exactly
the fields an edit affected.

Status per field: unset → proposed (agent inferred) → confirmed (human accepted) ; an edit can push a
confirmed dependent back to `stale` (must re-confirm).  "Rules decide" still holds — this module only
tracks who-said-what and what-an-edit-invalidates; it never prices or scores.
"""
from __future__ import annotations

from app.agent.resolve import customer_label, vehicle_label
from app.domain.reference import load_reference_data

# field -> primary key in `proposed`
FIELD_KEY = {
    "channel": "channel", "customer": "register_number", "product": "leasing_product",
    "asset": "vehicle_key", "term": "term_months", "mileage": "annual_mileage_km",
    "quantity": "quantity", "special_payment": "special_payment_eur",
    "maintenance": "service_maintenance", "tyres": "service_tyres", "insurance": "insurance",
}
LABELS = {
    "channel": "Channel", "customer": "Customer", "product": "Product", "asset": "Asset",
    "term": "Term", "mileage": "Mileage", "quantity": "Quantity", "special_payment": "Special payment",
    "maintenance": "Maintenance", "tyres": "Tyres", "insurance": "Insurance",
}
ORDER = ["channel", "customer", "product", "asset", "term", "mileage",
         "quantity", "special_payment", "maintenance", "tyres", "insurance"]
REQUIRED = ["channel", "customer", "product", "asset", "term", "mileage"]

# edited field -> confirmed dependents that must be RE-CONFIRMED (marked stale).
# Keep this minimal: only invalidate when the edit genuinely changes what's valid downstream.
# (channel does NOT invalidate customer here — the partner directory is the same across channels.)
INVALIDATES = {
    "product": ["asset"],      # a product change can change the asset category
}
_BOOL = {"maintenance", "tyres", "insurance"}


def _value(field: str, proposed: dict):
    return proposed.get(FIELD_KEY[field])


def display(field: str, proposed: dict):
    v = _value(field, proposed)
    if field == "customer":
        return customer_label(v) or v
    if field == "asset":
        return vehicle_label(v) or v
    if field in ("channel", "product"):
        return (v or "").replace("_", " ").title() if v else None
    if field in _BOOL:
        return "yes" if v else "no"
    return v


def _has(field: str, proposed: dict) -> bool:
    if field in _BOOL:
        return True                       # booleans always have a yes/no value
    return _value(field, proposed) not in (None, "")


# --------------------------------------------------------------------------- #
def restore(ac: dict, proposed: dict) -> dict:
    """Return the field_state map, seeding missing entries from `proposed`. Never downgrades a
    confirmed/stale status; a field that has a value but no status yet is 'proposed'."""
    fs = dict(ac.get("field_state") or {})
    for field in ORDER:
        cur = fs.get(field)
        if cur is None:
            fs[field] = {"status": "proposed" if _has(field, proposed) else "unset", "source": "agent"}
        elif cur.get("status") == "unset" and _has(field, proposed):
            cur["status"] = "proposed"
    return fs


def changed_fields(before: dict, after: dict) -> set[str]:
    return {f for f in ORDER if _value(f, before) != _value(f, after)}


def fields_for_keys(keys) -> set[str]:
    rev = {v: k for k, v in FIELD_KEY.items()}
    out = set()
    for k in keys:
        if k in rev:
            out.add(rev[k])
        if k in ("make", "model", "colour"):
            out.add("asset")
    return out


def derive_product(proposed: dict, before: dict) -> dict:
    """When the product changed, pull its business line + asset category from controlled reference
    data; if the asset category changed, drop the selected vehicle so a valid one is re-picked."""
    if _value("product", proposed) == _value("product", before):
        return proposed
    ref = load_reference_data()
    prod = ref.product(proposed.get("leasing_product"))
    if prod is not None:
        proposed["business_line"] = prod.business_line
        if prod.asset_category != before.get("asset_category"):
            proposed["asset_category"] = prod.asset_category
            proposed["vehicle_key"] = None   # re-pick within the new category
    return proposed


def apply(fs: dict, before: dict, after: dict, *, user_fields: set[str],
          confirm: bool, confirm_field: str | None) -> tuple[dict, dict]:
    """Fold one turn into the status map and return (field_state, ripple).

    - a field whose VALUE changed becomes `confirmed` if the human supplied it, else `proposed`;
    - its confirmed dependents (INVALIDATES) are pushed to `stale` (must re-confirm);
    - a dependent cleared to empty (e.g. asset after a category change) becomes `unset`;
    - `confirm_field` / `confirm` promote pending fields to `confirmed`.
    """
    ripple = {"changed": [], "invalidated": [], "cleared": []}
    for field in ORDER:
        if _value(field, before) == _value(field, after):
            continue
        ripple["changed"].append(field)
        by_user = field in user_fields
        fs.setdefault(field, {})
        fs[field]["status"] = "confirmed" if by_user else "proposed"
        fs[field]["source"] = "user" if by_user else "agent"
        for dep in INVALIDATES.get(field, []):
            if not _has(dep, after):
                fs.setdefault(dep, {})["status"] = "unset"
                ripple["cleared"].append(dep)
            elif fs.get(dep, {}).get("status") == "confirmed":
                fs[dep]["status"] = "stale"
                ripple["invalidated"].append(dep)
    if confirm_field and confirm_field in fs:
        fs[confirm_field]["status"] = "confirmed"
    if confirm:
        for f in fs:
            if fs[f].get("status") in ("proposed", "stale"):
                fs[f]["status"] = "confirmed"
    return fs, ripple


def pending(fs: dict) -> list[str]:
    """Required fields still needing the human: unset, agent-proposed, or invalidated (stale)."""
    return [f for f in REQUIRED if fs.get(f, {}).get("status") in ("unset", "proposed", "stale")]


def is_ready(fs: dict) -> bool:
    return not pending(fs)


def public(fs: dict, proposed: dict) -> list[dict]:
    """UI-facing view of the field state (the wizard rail renders this)."""
    return [{
        "field": f, "label": LABELS[f], "status": fs.get(f, {}).get("status", "unset"),
        "value": display(f, proposed), "required": f in REQUIRED,
    } for f in ORDER]


def summary(fs: dict, proposed: dict) -> str:
    """Compact text of the current fields + status — context for the LLM turn planner."""
    return "\n".join(
        f"- {f} ({LABELS[f]}): {display(f, proposed)} [{fs.get(f, {}).get('status', 'unset')}]"
        for f in ORDER)


def options_summary() -> str:
    """The controlled reference options the agent may offer (never invented)."""
    ref = load_reference_data()
    ch = ", ".join(c.name_en for c in ref.channels)
    pr = ", ".join(p.name_en for p in ref.leasing_products)
    return f"channels: {ch}\nproducts: {pr}"


def next_prompt(fs: dict, proposed: dict) -> str:
    """Proactively guide the human to the next thing needed — one field at a time."""
    pend = pending(fs)
    if not pend:
        return "Everything's confirmed — say “price it” and I'll build the scenarios."
    f = pend[0]
    val = display(f, proposed)
    rest = len(pend) - 1
    tail = f" ({rest} more after this)" if rest > 0 else ""
    if val in (None, ""):
        return f"Next, I need the {LABELS[f]}{tail}."
    return f"Next — confirm the {LABELS[f]} ({val}), or tell me a change{tail}."


def echo(ripple: dict, fs: dict, proposed: dict) -> str | None:
    """A concise agent line: what changed, what must be re-confirmed, then the next step."""
    parts = [f"{LABELS[f]} set to {display(f, proposed)}" for f in ripple["changed"]]
    reconfirm = ripple["invalidated"] + ripple["cleared"]
    if reconfirm:
        parts.append("re-confirm " + ", ".join(LABELS[f] for f in reconfirm) + " (affected by that change)")
    base = "; ".join(parts)
    return (base + ". " if base else "") + next_prompt(fs, proposed)
