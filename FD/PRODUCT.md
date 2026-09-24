# PRODUCT.md — Agentic Offer Creation (Frontend)

> Derived from `../docs/00–09` and the LangGraph backend (`../BE`). Assumptions are labelled.

## What it is
An internal **decision console** for creating German B2B passenger-car leasing offers. A sales user
turns a plain-language request into a structured, priced, risk-scored, explainable offer; a reviewer
approves it under four-eyes; the system generates a decision-ready offer. It is **agent-assisted but
rule-governed**: AI understands and explains, deterministic services decide, humans govern.

## Who uses it (use scene)
- **Sales user** — creates offers, confirms AI-extracted intake, picks a scenario, submits for review.
- **Reviewer / Approver** — reviews the full basis, approves or returns (cannot approve own offer).
Internal staff at desks, office lighting, daytime → **light theme**, dense and legible, keyboard-friendly.

## The core job (Operate mode)
Move one Offer Case through: intake → confirm → price/score → compare scenarios → select → review →
generate. The UI must always answer: *Where am I · What do we know · What needs attention · What next.*

## Non-negotiable product truths (from docs)
- **Never a black box.** Every fact we hold — provenance, calculation breakdown, risk factors,
  exceptions, audit, and the agent's live progress — is surfaced in context.
- **Provenance on every field** (value · status · source · confidence): known vs AI-inferred vs missing.
- **Human-in-the-loop** at confirm-intake, scenario-selection, and review (persisted; resumable).
- **Four-eyes**: creator ≠ approver.
- Numbers come from the engine; the LLM only explains (grounded) — show a clear "AI" badge on prose.
- Policy `DE_PKW_V1` is an **illustrative MVP policy**, stated up front (not production pricing).

## Backend contract (BE, FastAPI on :8100, CORS open)
Actions (streaming variants added for live feed): `POST /offers/nl`, `POST /offers/{id}/confirm`,
`POST /offers/{id}/select`, `POST /offers/{id}/review`, `GET /offers`, `GET /offers/{id}`.
Snapshot fields: reference, workflow_status, readiness, band, final_outcome, monthly_net/gross,
scenarios[], selected_scenario_id, exceptions[], proposed, explanation_pricing/scenarios,
next[], interrupts[].

## MVP scope (this build = vertical slice)
Inbox → Intake (NL + confirm) → Workspace happy path (create → confirm → scenarios → select →
review → output) with the **live SSE agent feed**. Transparency panels + edge-case views + roles
land in the second pass.

## Assumptions (labelled)
- Roles are mocked personas (sales@demo.local / approver@demo.local) — no real auth in the MVP.
- EN first; DE labels wired in a later pass.
- PDF output is Phase 5; Output screen shows the validated offer summary until then.
