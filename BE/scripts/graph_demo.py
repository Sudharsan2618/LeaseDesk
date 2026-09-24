"""Drive the LangGraph workflow end-to-end against Neon (persistent + human-in-the-loop).

Run:  python -m scripts.graph_demo
Shows: GREEN offer pausing for scenario selection, then for review, then generating; and a RED
offer routed straight to BLOCKED. All state persists via the Postgres checkpointer.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg_pool import ConnectionPool

from app.core.policy import load_policy
from app.core.types import Language
from app.db import repository as repo
from app.db.connection import database_url, get_conn
from app.domain.entities import Offer, Role
from app.engine.scenario import compare
from app.graph.build import builder
from app.integration.base import AdapterMode, build_default_registry
from app.service.offer_factory import build_b2b_offer

pool = ConnectionPool(conninfo=database_url(), max_size=5,
                      kwargs={"autocommit": True, "prepare_threshold": 0})
checkpointer = PostgresSaver(pool)
checkpointer.setup()
graph = builder.compile(checkpointer=checkpointer)
registry = build_default_registry(AdapterMode.MOCK)


def cfg(tid):
    return {"configurable": {"thread_id": tid}}


def interrupts(tid):
    snap = graph.get_state(cfg(tid))
    out = []
    for t in snap.tasks:
        for it in (t.interrupts or []):
            out.append(it.value)
    return snap, out


def summary(tid):
    snap = graph.get_state(cfg(tid))
    o = Offer.model_validate(snap.values["offer"])
    c = o.calculation.value if o.calculation else None
    gross = str(c.monthly_gross_eur) if c else "-"
    return f"{o.reference}  status={o.workflow_status.value}  band={o.scoring.value.band.value if o.scoring else '-'}  gross={gross}  next={list(snap.next)}"


def new_offer(register, veh, term, mileage, creator_id):
    offer = build_b2b_offer(registry, vehicle_key=veh, register_number=register,
                            term_months=term, annual_mileage_km=mileage,
                            special_payment_eur=Decimal("0"), language=Language.EN)
    offer.created_by = creator_id
    return offer


def main():
    with get_conn() as conn:
        repo.seed_policy(conn, "DE_PKW_V1", load_policy("DE_PKW_V1").raw)
        sales = repo.ensure_user(conn, "sales@demo.local", Role.SALES)

    # ---- GREEN offer: single-actor gate (select -> generate) -----------------
    print("=== GREEN offer (single actor, mutable gate) ===")
    offer = new_offer("HRB-1001", "bmw-x1-sdrive18i", 36, 20000, sales)
    tid = str(offer.id)
    graph.invoke({"offer": offer.model_dump(mode="json"), "intake_confirmed_initial": True},
                 config=cfg(tid))
    snap, ints = interrupts(tid)
    print(" after create ->", summary(tid))
    print(" AT GATE; scenarios:", [(r["scenario"], str(r["monthly_gross_eur"])) for r in ints[0]["scenarios"]])

    graph.invoke(Command(resume={"action": "select", "scenario_label": "48M"}), config=cfg(tid))
    print(" after select 48M ->", summary(tid))

    graph.invoke(Command(resume={"action": "generate"}), config=cfg(tid))
    print(" after generate ->", summary(tid), "(still revisitable at the gate)")

    # ---- RED compliance offer: straight to BLOCKED ---------------------------
    print("\n=== RED compliance offer (sanctions) ===")
    red = new_offer("HRB-4004", "bmw-x1-sdrive18i", 36, 20000, sales)
    rtid = str(red.id)
    graph.invoke({"offer": red.model_dump(mode="json"), "intake_confirmed_initial": True},
                 config=cfg(rtid))
    print(" after create ->", summary(rtid))

    # ---- persistence proof: audit trail for the GREEN offer ------------------
    print("\n=== audit trail (GREEN) ===")
    with get_conn() as conn:
        for ev in repo.audit_trail(conn, UUID(tid)):
            print("  ", ev["at"], ev["actor_kind"], ev["event"])

    pool.close()


if __name__ == "__main__":
    main()
