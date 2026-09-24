"""Persistence: Offer aggregate <-> PostgreSQL (thin relational spine + JSONB payloads, docs/07).

Offers are INSERTed fully in one statement (contexts + results together) so the stale-result
invalidation trigger (which fires on UPDATE when a context changes) never wipes freshly computed
results. Re-runs use replace_offer(), which deletes children + reinserts under the same id.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.domain.entities import Offer, Role


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def _dump(model) -> dict[str, Any]:
    """Pydantic -> JSON-safe dict (Decimal->str, datetime->iso, enum->value)."""
    return model.model_dump(mode="json")


def _acq_value(offer: Offer) -> Optional[Decimal]:
    pv = offer.vehicle.acquisition_price_net
    return pv.value if pv.is_consumable else None


def _band(offer: Offer) -> Optional[str]:
    if offer.scoring is None:
        return None
    return offer.scoring.value.band.value


# --------------------------------------------------------------------------- #
# reference policy                                                             #
# --------------------------------------------------------------------------- #
def seed_policy(conn: psycopg.Connection, policy_id: str, config: dict) -> None:
    conn.execute(
        """
        INSERT INTO reference_policies (policy_id, status, config)
        VALUES (%s, 'ACTIVE', %s)
        ON CONFLICT (policy_id) DO UPDATE SET config = EXCLUDED.config
        """,
        (policy_id, Jsonb(config)),
    )


# --------------------------------------------------------------------------- #
# users                                                                        #
# --------------------------------------------------------------------------- #
def ensure_user(conn: psycopg.Connection, email: str, role: Role = Role.SALES,
                display_name: str | None = None) -> UUID:
    row = conn.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
    if row:
        return row[0]
    row = conn.execute(
        "INSERT INTO users (email, display_name, role) VALUES (%s, %s, %s) RETURNING id",
        (email, display_name or email, role.value),
    ).fetchone()
    return row[0]


# --------------------------------------------------------------------------- #
# offers                                                                       #
# --------------------------------------------------------------------------- #
def save_offer(conn: psycopg.Connection, offer: Offer) -> UUID:
    """INSERT a fully-computed offer + its scenarios/issues/exceptions, then write a creation audit
    event. selected_scenario_id is set AFTER scenarios exist (FK), via an UPDATE that touches no
    context column (so the invalidation trigger does not fire)."""
    conn.execute(
        """
        INSERT INTO offers (
            id, reference, workflow_status, readiness, customer_type, language,
            policy_version, created_by, offer_value_eur, scoring_band, selected_scenario_id,
            commercial_context, customer_context, vehicle_context, agent_context,
            calculation_result, assessment_result, asset_assessment_result, scoring_result
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            offer.id, offer.reference, offer.workflow_status.value, offer.readiness.value,
            offer.customer_type.value, offer.language.value, offer.policy_version,
            offer.created_by, _acq_value(offer), _band(offer), None,  # selected set later
            Jsonb(_dump(offer.commercial)), Jsonb(_dump(offer.customer)),
            Jsonb(_dump(offer.vehicle)), Jsonb({}),
            Jsonb(_dump(offer.calculation)) if offer.calculation else None,
            Jsonb(_dump(offer.assessment)) if offer.assessment else None,
            Jsonb(_dump(offer.asset_assessment)) if offer.asset_assessment else None,
            Jsonb(_dump(offer.scoring)) if offer.scoring else None,
        ),
    )
    _save_scenarios(conn, offer)
    _save_issues(conn, offer)
    _save_exceptions(conn, offer)
    if offer.selected_scenario_id is not None:
        conn.execute("UPDATE offers SET selected_scenario_id = %s WHERE id = %s",
                     (offer.selected_scenario_id, offer.id))
    write_audit(conn, offer.id, "OFFER_CREATED", actor=offer.created_by, actor_kind="SYSTEM",
                after={"workflow_status": offer.workflow_status.value,
                       "readiness": offer.readiness.value, "band": _band(offer),
                       "scenarios": len(offer.scenarios)})
    return offer.id


def upsert_offer(conn: psycopg.Connection, offer: Offer, *, event: str = "STATE_PERSISTED",
                 actor: UUID | None = None, reason: str | None = None) -> UUID:
    """THE single projection writer (hybrid model). Persists a fully-consistent Offer snapshot:
    upserts the offers row, replaces derived children (scenarios/issues/exceptions), and appends
    one audit event. Idempotent by offer id, so LangGraph replay-after-interrupt is safe."""
    with conn.transaction():
        conn.execute(
            """
            INSERT INTO offers (
                id, reference, workflow_status, readiness, customer_type, language,
                policy_version, created_by, offer_value_eur, scoring_band, selected_scenario_id,
                commercial_context, customer_context, vehicle_context, agent_context,
                calculation_result, assessment_result, asset_assessment_result, scoring_result
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                workflow_status = EXCLUDED.workflow_status,
                readiness       = EXCLUDED.readiness,
                offer_value_eur = EXCLUDED.offer_value_eur,
                scoring_band    = EXCLUDED.scoring_band,
                commercial_context = EXCLUDED.commercial_context,
                customer_context   = EXCLUDED.customer_context,
                vehicle_context    = EXCLUDED.vehicle_context,
                calculation_result = EXCLUDED.calculation_result,
                assessment_result  = EXCLUDED.assessment_result,
                asset_assessment_result = EXCLUDED.asset_assessment_result,
                scoring_result     = EXCLUDED.scoring_result
            """,
            (
                offer.id, offer.reference, offer.workflow_status.value, offer.readiness.value,
                offer.customer_type.value, offer.language.value, offer.policy_version,
                offer.created_by, _acq_value(offer), _band(offer), None,  # selected set after scenarios
                Jsonb(_dump(offer.commercial)), Jsonb(_dump(offer.customer)),
                Jsonb(_dump(offer.vehicle)), Jsonb(offer.agent_context or {}),
                Jsonb(_dump(offer.calculation)) if offer.calculation else None,
                Jsonb(_dump(offer.assessment)) if offer.assessment else None,
                Jsonb(_dump(offer.asset_assessment)) if offer.asset_assessment else None,
                Jsonb(_dump(offer.scoring)) if offer.scoring else None,
            ),
        )
        conn.execute("UPDATE offers SET agent_context = %s WHERE id = %s",
                     (Jsonb(offer.agent_context or {}), offer.id))
        # replace derived children (clear selected FK first to allow scenario delete)
        conn.execute("UPDATE offers SET selected_scenario_id = NULL WHERE id = %s", (offer.id,))
        conn.execute("DELETE FROM scenarios WHERE offer_id = %s", (offer.id,))
        conn.execute("DELETE FROM validation_issues WHERE offer_id = %s", (offer.id,))
        conn.execute("DELETE FROM exceptions WHERE offer_id = %s", (offer.id,))
        _save_scenarios(conn, offer)
        _save_issues(conn, offer)
        _save_exceptions(conn, offer)
        if offer.selected_scenario_id is not None:
            conn.execute("UPDATE offers SET selected_scenario_id = %s WHERE id = %s",
                         (offer.selected_scenario_id, offer.id))
        write_audit(conn, offer.id, event, actor=actor, actor_kind="SYSTEM" if actor is None else "USER",
                    after={"workflow_status": offer.workflow_status.value,
                           "readiness": offer.readiness.value, "band": _band(offer)},
                    reason=reason)
    return offer.id


def _save_scenarios(conn: psycopg.Connection, offer: Offer) -> None:
    for s in offer.scenarios:
        c = s.calculation.value if s.calculation else None
        conn.execute(
            "INSERT INTO scenarios (id, offer_id, label, parameters, calculation_result, "
            "assessment_result, scoring_result, monthly_gross_eur, scoring_band) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (s.id, offer.id, s.label,
             Jsonb({"term_months": s.term_months, "annual_mileage_km": s.annual_mileage_km,
                    "special_payment_eur": str(s.special_payment_eur),
                    "service_maintenance": s.service_maintenance, "service_tyres": s.service_tyres,
                    "insurance": s.insurance}),
             Jsonb(_dump(s.calculation)) if s.calculation else None,
             Jsonb(_dump(s.assessment)) if s.assessment else None,
             Jsonb(_dump(s.scoring)) if s.scoring else None,
             c.monthly_gross_eur if c else None,
             s.scoring.value.band.value if s.scoring else None),
        )


def _save_issues(conn: psycopg.Connection, offer: Offer) -> None:
    for i in offer.issues:
        conn.execute(
            "INSERT INTO validation_issues (offer_id, field, type, blocking, detail) "
            "VALUES (%s,%s,%s,%s,%s)",
            (offer.id, i.field, i.type, i.blocking,
             Jsonb({"why": i.why, "what_must_happen": i.what_must_happen, "who_acts": i.who_acts})),
        )


def _save_exceptions(conn: psycopg.Connection, offer: Offer) -> None:
    for e in offer.exceptions:
        conn.execute(
            "INSERT INTO exceptions (offer_id, code, severity, blocking, override_allowed, "
            "required_role, next_action, detail) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (offer.id, e.code, e.severity, e.blocking, e.override_allowed,
             e.required_role, e.next_action, Jsonb(e.detail)),
        )


def load_offer(conn: psycopg.Connection, offer_id: UUID) -> Offer:
    row = conn.execute(
        """
        SELECT reference, workflow_status, readiness, customer_type, language, policy_version,
               created_by, selected_scenario_id, commercial_context, customer_context,
               vehicle_context, calculation_result, assessment_result, asset_assessment_result,
               scoring_result, agent_context
        FROM offers WHERE id = %s
        """,
        (offer_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"offer {offer_id} not found")
    (reference, wf, readiness, ctype, lang, pver, created_by, sel_scn,
     commercial, customer, vehicle, calc, assess, asset_assess, score, agent_ctx) = row

    data: dict[str, Any] = {
        "id": offer_id, "reference": reference, "workflow_status": wf, "readiness": readiness,
        "customer_type": ctype, "language": lang, "policy_version": pver,
        "created_by": created_by, "selected_scenario_id": sel_scn,
        "commercial": commercial, "customer": customer, "vehicle": vehicle,
        "calculation": calc, "assessment": assess, "asset_assessment": asset_assess, "scoring": score,
        "agent_context": agent_ctx or {},
        "issues": _load_issues(conn, offer_id), "exceptions": _load_exceptions(conn, offer_id),
        "scenarios": _load_scenarios(conn, offer_id),
    }
    return Offer.model_validate(data)


def _load_scenarios(conn: psycopg.Connection, offer_id: UUID) -> list[dict]:
    rows = conn.execute(
        "SELECT id, label, parameters, calculation_result, assessment_result, scoring_result "
        "FROM scenarios WHERE offer_id=%s ORDER BY created_at",
        (offer_id,),
    ).fetchall()
    out = []
    for sid, label, params, calc, assess, score in rows:
        p = params or {}
        out.append({"id": sid, "label": label,
                    "term_months": p.get("term_months"),
                    "annual_mileage_km": p.get("annual_mileage_km"),
                    "special_payment_eur": p.get("special_payment_eur", "0"),
                    "service_maintenance": bool(p.get("service_maintenance", False)),
                    "service_tyres": bool(p.get("service_tyres", False)),
                    "insurance": bool(p.get("insurance", False)),
                    "calculation": calc, "assessment": assess, "scoring": score})
    return out


def _load_issues(conn: psycopg.Connection, offer_id: UUID) -> list[dict]:
    rows = conn.execute(
        "SELECT field, type, blocking, detail FROM validation_issues WHERE offer_id=%s ORDER BY created_at",
        (offer_id,),
    ).fetchall()
    out = []
    for field, typ, blocking, detail in rows:
        d = detail or {}
        out.append({"field": field, "type": typ, "blocking": blocking,
                    "why": d.get("why"), "what_must_happen": d.get("what_must_happen"),
                    "who_acts": d.get("who_acts")})
    return out


def _load_exceptions(conn: psycopg.Connection, offer_id: UUID) -> list[dict]:
    rows = conn.execute(
        "SELECT code, severity, blocking, override_allowed, required_role, next_action, detail "
        "FROM exceptions WHERE offer_id=%s ORDER BY created_at",
        (offer_id,),
    ).fetchall()
    return [{"code": c, "severity": s, "blocking": b, "override_allowed": o,
             "required_role": r, "next_action": n, "detail": d or {}}
            for c, s, b, o, r, n, d in rows]


# --------------------------------------------------------------------------- #
# audit                                                                        #
# --------------------------------------------------------------------------- #
def write_audit(conn: psycopg.Connection, offer_id: UUID, event: str, *,
                actor: UUID | None = None, actor_kind: str = "USER",
                before: dict | None = None, after: dict | None = None,
                reason: str | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_events (offer_id, event, actor, actor_kind, before, after, reason) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (offer_id, event, actor, actor_kind,
         Jsonb(before) if before else None, Jsonb(after) if after else None, reason),
    )


def save_output(conn: psycopg.Connection, offer: Offer, *, file_ref: str | None = None) -> None:
    """Persist a frozen validated-offer snapshot (docs/06 §5). PDF file_ref filled in Phase 5."""
    conn.execute(
        "INSERT INTO offer_outputs (offer_id, language, format, offer_snapshot, file_ref) "
        "VALUES (%s,%s,%s,%s,%s)",
        (offer.id, offer.language.value, "PDF", Jsonb(offer.model_dump(mode="json")), file_ref),
    )
    write_audit(conn, offer.id, "OFFER_GENERATED", actor_kind="SYSTEM",
                after={"language": offer.language.value})


def record_review(conn: psycopg.Connection, offer_id: UUID, reviewer_id: UUID, decision: str,
                  comments: str | None = None) -> None:
    """Insert a review (four-eyes enforced by DB trigger) + an audit event. decision in
    APPROVE/RETURN/CORRECT."""
    conn.execute(
        "INSERT INTO reviews (offer_id, reviewer_id, decision, comments) VALUES (%s,%s,%s,%s)",
        (offer_id, reviewer_id, decision, comments),
    )
    write_audit(conn, offer_id, f"REVIEW_{decision}", actor=reviewer_id, actor_kind="USER",
                reason=comments)


def audit_trail(conn: psycopg.Connection, offer_id: UUID) -> list[dict]:
    rows = conn.execute(
        "SELECT event, actor_kind, reason, created_at FROM audit_events "
        "WHERE offer_id=%s ORDER BY created_at",
        (offer_id,),
    ).fetchall()
    return [{"event": e, "actor_kind": k, "reason": r, "at": t.isoformat()} for e, k, r, t in rows]


def audit_trail_all(conn: psycopg.Connection, limit: int = 200) -> list[dict]:
    """Global audit feed across every offer (newest first) — for the standalone Audit screen."""
    rows = conn.execute(
        "SELECT a.event, a.actor_kind, a.reason, a.created_at, "
        "       o.id, o.reference, o.customer_context->'legal_name'->>'value' AS customer "
        "FROM audit_events a JOIN offers o ON o.id = a.offer_id "
        "ORDER BY a.created_at DESC LIMIT %s",
        (limit,),
    ).fetchall()
    return [{"event": e, "actor_kind": k, "reason": r, "at": t.isoformat(),
             "offer_id": str(oid), "reference": ref, "customer": cust}
            for e, k, r, t, oid, ref, cust in rows]
