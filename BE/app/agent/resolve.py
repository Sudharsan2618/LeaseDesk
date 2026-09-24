"""Deterministic resolution of the LLM's fuzzy hints to authoritative catalogue keys.

The LLM proposes "BMW X1" / "Musterlogistik"; these functions map that to a real vehicle_key /
register_number from the fixtures (the authoritative source). No LLM here — the LLM never invents
identifiers; it only hints, and we look them up.
"""
from __future__ import annotations

from typing import Optional

from app.integration._fixtures import load


def resolve_vehicle_key(make: Optional[str], model: Optional[str]) -> Optional[str]:
    if not make and not model:
        return None
    mk = (make or "").lower()
    md = (model or "").lower()
    for row in load("vehicles.json")["vehicles"]:
        if (not mk or mk in row["make"].lower()) and (not md or md in row["commercial_name"].lower()):
            return row["key"]
    return None


def resolve_register(company_hint: Optional[str]) -> Optional[str]:
    if not company_hint:
        return None
    h = company_hint.strip().lower()
    companies = load("companies.json")["companies"]
    if company_hint in companies:                      # exact register number
        return company_hint
    for reg, c in companies.items():
        if h in c["legal_name"].lower() or h in reg.lower():
            return reg
    return None


def search_partners(query: Optional[str], limit: int = 5) -> list[dict]:
    """Partner search + duplicate detection (spec §3.4, FR-06, Screen 03).

    Returns candidate business partners matching a name/number query, most-relevant first. When 2+
    are returned the caller surfaces them as duplicate candidates for the user to pick/confirm; an
    empty query returns nothing (the step then asks who the customer is).
    """
    if not query:
        return []
    q = query.strip().lower()
    companies = load("companies.json")["companies"]
    scored: list[tuple[int, dict]] = []
    for reg, c in companies.items():
        name = c["legal_name"].lower()
        if q == reg.lower() or q == name:
            score = 3                                   # exact
        elif name.startswith(q) or reg.lower().startswith(q):
            score = 2                                   # prefix
        elif q in name or q in reg.lower():
            score = 1                                   # substring
        else:
            score = 0
        if score:
            scored.append((score, {
                "register_number": reg, "legal_name": c["legal_name"],
                "legal_form": c.get("legal_form"),
                "label": f"{c['legal_name']} ({reg})",
            }))
    scored.sort(key=lambda t: (-t[0], t[1]["legal_name"]))
    return [row for _, row in scored[:limit]]


# --- catalogue (data-driven; the UI reads these, not a hardcoded list) --------- #
def list_vehicles() -> list[dict]:
    out = []
    for v in load("vehicles.json")["vehicles"]:
        row = {k: val for k, val in v.items() if not k.startswith("_")}
        row["label"] = f"{v['make']} {v['commercial_name']} {v.get('variant', '')}".strip()
        out.append(row)
    return out


def list_customers() -> list[dict]:
    return [
        {"register_number": reg, "legal_name": c["legal_name"], "legal_form": c.get("legal_form"),
         "label": f"{c['legal_name']} ({reg})"}
        for reg, c in load("companies.json")["companies"].items()
    ]


def vehicle_label(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    return next((v["label"] for v in list_vehicles() if v["key"] == key), key)


def customer_label(register: Optional[str]) -> Optional[str]:
    if not register:
        return None
    return next((c["legal_name"] for c in list_customers() if c["register_number"] == register),
                register)
