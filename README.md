# Agentic Offer Creation — MVP Knowledge Base

**Domain:** B2B leasing Offer Creation — **asset-agnostic** (PKW · Equipment · NFZ · ITK); PKW is the
representative seed. · **Output:** decision-ready Offer (EN/DE) · **Scope boundary:** ends at a
generated Offer — **no contract creation.**
**Stack:** FastAPI + PostgreSQL (JSONB) + LangGraph + Next.js (monorepo: `BE/` + `FD/`).

> ### ⭐ Current source of truth — read first
> The **original client requirements PDF** has been extracted into **[docs/11-client-spec-extract.md](docs/11-client-spec-extract.md)**.
> It, plus **[docs/12-business-logic-bookmark.md](docs/12-business-logic-bookmark.md)** (gap analysis +
> locked decisions), **[docs/13-agent-workbench-design.md](docs/13-agent-workbench-design.md)** (60/40
> UI + general extraction) and **[docs/14-build-plan.md](docs/14-build-plan.md)** (phased build),
> **outrank docs 00–10 wherever they conflict.** Docs 00–10 remain the earlier PKW-only foundation and
> are being generalized per the build plan.

---

## Why this repo exists (read this first)

Before writing any LangGraph / AI / UI code, we are locking down the **data and calculation
foundation**: every data-integration piece, every input/output structure, how they interconnect,
and how the calculation/decision logic works. Once this base is validated, the AI/orchestration/UI
layers get built on top of it — not the other way round.

This folder is the **source of truth** for that foundation. It is documentation only; no
application code yet.

---

## The one thing to understand

> **AI assists → deterministic rules decide → humans govern.**
> The system is a *stateful Offer Case* moving through a state machine. The LLM understands,
> assembles, compares and explains — but **never** performs calculation, scoring, or eligibility
> decisions. Those are deterministic, versioned, explainable services. Every field carries
> **provenance** so uncertainty is never silently turned into business truth.

Two decisions reshaped the MVP:
1. **Vendors aren't a blocker** — build on free/trial/sandbox data plus a *public data structure*
   (the EEA CO₂ dataset gives the vehicle shape). Adapters expose a `LIVE / SANDBOX / MOCK` switch.
2. **Client-controlled rules won't be provided** — so we author them ourselves as the versioned
   **MVP Reference Policy `DE_PKW_V1`** (funding, margin, residual, risk, eligibility, approval),
   deterministic and replaceable later.

---

## Documents (read in order)

| # | Doc | What it gives you |
|---|---|---|
| 00 | [Source of truth](docs/00-source-of-truth.md) | The frozen original conversation. Everything else derives from it. |
| 01 | [Knowledge graph](docs/01-knowledge-graph.md) | The whole problem as one connected, deduplicated picture. **Start here for shape.** |
| 02 | [Domain entities](docs/02-domain-entities.md) | The data structures, the `ProvenanceValue`/`ResultEnvelope` envelopes, and how entities connect. |
| 03 | [Data sources & integration](docs/03-data-sources-and-integration.md) | Every integration, its I/O contract, and its MVP treatment (live/sandbox/mock). |
| 04 | [Calculation & decision logic](docs/04-calculation-logic.md) | The deterministic engine step by step, edge cases, a worked example, a validation checklist. |
| 05 | [MVP reference policy `DE_PKW_V1`](docs/05-mvp-reference-policy.md) | All client-controlled constants as concrete config + roles/approval/exceptions/PDF. |
| 06 | [State model](docs/06-state-model.md) | Workflow status × validation state, transitions, guards, recalculation rules. |
| 07 | [Data model (JSONB/Postgres)](docs/07-data-model-jsonb-postgres.md) | The relational spine + JSONB payload schema. |
| 08 | [Open questions & verification](docs/08-open-questions-and-verification.md) | Decided vs open; and every research claim to verify before trusting it. |
| 09 | [UI & screenflow](docs/09-ui-and-screenflow.md) | First UI/screenflow pass (superseded by 13). |
| 10 | [Screen redesign](docs/10-screen-redesign.md) | Mode-driven workspace (superseded by 13). |
| **11** | **[Client spec extract](docs/11-client-spec-extract.md)** | **The client PDF, transcribed: FR/BR/AC, screens, process, interventions. AUTHORITATIVE.** |
| **12** | **[Business-logic bookmark](docs/12-business-logic-bookmark.md)** | **Gap analysis (spec vs build) + locked decisions.** |
| **13** | **[Agent workbench design](docs/13-agent-workbench-design.md)** | **60/40 wizard + chat; the general intent-extraction model.** |
| **14** | **[Build plan](docs/14-build-plan.md)** | **Phased divide→build→validate task list. The current work driver.** |
| 15 | [Traceability matrix](docs/15-traceability.md) | Every FR/BR/AC → status → implementation → proving test. |

---

## After reading this, you can

- **Gather requirements precisely** — you have the settled decisions, the genuine open questions
  (doc 08 §3), and the doc-consistency items to reconcile (doc 08 §5).
- **Start developing the foundation** — the entity contracts (02), the integration contracts (03),
  the deterministic engine (04 + its checklist), and the DB schema (07) are specified enough to
  implement and unit-test with **no AI and no UI**.
- **Explain and defend the design** — the knowledge graph (01) and the three-engine / source-class
  model give you the rationale behind every boundary.

## What NOT to do yet (deliberately deferred)

LangGraph orchestration, the LLM agent, and the React workbench come **after** the data + calc base
is validated. The source's own build order: **Phase 1 Offer engine (no AI) → Phase 2 Workbench →
Phase 3 Agent → Phase 4 Orchestration → Phase 5 Negative flows → Phase 6 PDF + demo.** The user
will provide references for the AI/UI phases separately.

---

## Important caveat

Every external API capability, field list, endpoint, and legal claim in docs 00/03/08 was asserted
by the prior research chat and is **not re-verified here**. Verify against the live source before
building an adapter or making any compliance statement (see doc 08 §4).
