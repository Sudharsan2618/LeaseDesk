# Overall TODO / Roadmap — Agentic Offer Creation MVP

Build order follows the source's own sequencing: **data + calc foundation → persistence →
scenarios → human review → PDF → AI/orchestration → UI → negative flows → demo hardening.**
Scope = German B2B passenger-car kilometre leasing; ends at a decision-ready Offer PDF (no contract).

Legend: `[x]` done · `[~]` partial · `[ ]` not started.

---

## Phase 0 — Requirement crystallisation & decisions
- [x] Freeze source-of-truth + knowledge base (`docs/00`–`08`, `README.md`)
- [x] Settle scope: B2B first, Germany, PKW kilometre leasing, EN/DE, PDF (docs/08 §1)
- [x] Author the MVP reference policy `DE_PKW_V1` (docs/05, `app/config/de_pkw_v1.json`)
- [x] Resolve Q-CALC-1 (residual applies to list price, net basis for B2B)
- [ ] Resolve remaining open items (docs/08 §3): Q-CALC-2 (service fees/tax in rate?),
      Q-CALC-3 (exact Bundesbank series id), Q-RISK-1 (mock credit input fields), Q-DEMO-1
      (which negative flows to demo), Q-AUTH-1 (real auth vs personas)
- [ ] Reconcile doc-consistency flags (FR count vs FR-63; AC-16/AC-17 duplicate) with doc owner

## Phase 1 — Deterministic foundation (NO AI / NO UI)  ✅ built
- [x] Core envelopes: `ProvenanceValue`, `ResultEnvelope`, enums (`app/core/types.py`)
- [x] Policy loader over `DE_PKW_V1` (`app/core/policy.py`)
- [x] Domain entities + Offer aggregate (`app/domain/entities.py`)
- [x] Adapter protocol + registry with LIVE/SANDBOX/MOCK (`app/integration/base.py`)
- [x] MOCK adapters: vehicle, reference-rate, VAT, VIES, sanctions, KYC, credit + fixtures
- [x] Engine: residual, funding, margin, calculator, B2B risk, eligibility, exceptions, orchestrator
- [x] Offer factory (assemble B2B offer from primitives) (`app/service/offer_factory.py`)
- [x] DB schema + triggers (`db/schema.sql`, `db/triggers.sql`) — review-validated
- [x] Tests = docs/04 §10 checklist + persona flows (`tests/test_engine.py`, 18 pass, deterministic)

## Phase 1.5 — Validate & tidy the foundation
- [ ] Execute `db/schema.sql` + `triggers.sql` against a real PostgreSQL 13+ instance
- [ ] Reconcile residual base once in code comments/tests (net list price) end-to-end
- [ ] Add property-based/edge tests: interpolated terms (30/42/54m), mileage-cap boundaries,
      margin clamp reachability, exposure-ratio boundaries
- [ ] Capture one real response per LIVE source and save as the MOCK fixture (docs/03 §7)
- [ ] Decide "material field" set formally (drives readiness rollup + completeness)

## Phase 2 — Persistence (Offer ↔ PostgreSQL JSONB)  ✅ built (Neon)
- [x] Schema + triggers applied to live Neon DB (`lease`); 9 tables created
- [x] Connection helper reading DATABASE_URL from `.env` (`app/db/connection.py`)
- [x] Repository: `Offer`/issues/exceptions ↔ tables + JSONB (`app/db/repository.py`)
- [x] Serialise `ProvenanceValue`/`ResultEnvelope` to/from JSONB (round-trip verified in e2e)
- [x] `reference_policies` seeding (`seed_policy`) + policy-version pin on offer
- [x] Audit-event writer (append-only) — creation event written
- [x] DB integrity verified live: four-eyes, policy-pin, append-only audit, stale-result invalidation
- [x] End-to-end runner (`python -m scripts.e2e`) — 5 personas persisted + round-tripped
- [ ] Persist scenarios (table exists; writer pending Phase 3)
- [ ] Migration tooling (alembic or numbered SQL migrations) for schema evolution
- [ ] Update flow: `replace_offer()` for re-runs (works with the invalidation trigger)

## Phase 3 — Scenario engine  ✅ built
- [x] Generate valid term variants within policy constraints (`app/engine/scenario.py`)
- [x] Re-run residual → funding → margin → calc per scenario (band reused for term/mileage variation)
- [x] Scenario comparison payload (`compare()`)
- [x] Select-scenario → promotes results to the Offer (`select_scenario()`)
- [x] Persist scenarios + selected id (`repository._save_scenarios`/`_load_scenarios`)
- [x] Tests: generation, longer-term-cheaper, compare shape, selection, RED→none, determinism
- [x] e2e prints comparison + selects (24M→60M: €806→€620 for the BMW); 12 scenarios in DB
- [ ] Scenarios that vary special payment (re-score exposure) — deferred until needed

## Phase 4 — Workflow & human review  ✅ built via LangGraph (hybrid model)
- [x] Workflow = LangGraph `StateGraph` (`app/graph/build.py`); transitions are graph edges
- [x] Nodes call the existing engine (`app/graph/nodes.py`) — no logic rewrite
- [x] Human-in-the-loop via `interrupt()`/`Command(resume=)`: scenario selection + review
- [x] Native persistence + resume via `PostgresSaver` on Neon (no hand-rolled workflow code)
- [x] Single projection writer `repository.upsert_offer` (hybrid: checkpoint=workflow, tables=record)
- [x] Removed the stale-invalidation DB trigger (superseded by the single writer)
- [x] Maker-checker four-eyes: checked at API before resume (recoverable 409) + DB trigger backstop
- [x] Return path → RETURNED; approve → final validation → generate
- [x] Tests `tests/test_graph.py` (interrupt→resume→generate; RED→blocked)
- [ ] Authority €/band limits per role at review (four-eyes done; limits TODO)
- [ ] Exception soft-override flow (override → audit before/after) — TODO

## Phase 5 — Final validation & Offer PDF (EN/DE)
- [ ] Final-validation decision: READY / REQUIRES_ACTION / BLOCKED (docs/06 §3)
- [ ] Freeze validated Offer JSON snapshot → `offer_outputs`
- [ ] EN/DE controlled templates (fixed labels/statuses; disclaimer verbatim, docs/05 §6)
- [ ] HTML → PDF generation (local library); sections per docs/05 §6
- [ ] Localization tables for controlled enums (READY/BLOCKED/GREEN/YELLOW/RED)
- [ ] Tests: PDF built only from a frozen snapshot; blocked offers cannot generate

## Phase 6 — API layer (FastAPI)  ✅ built (collapsed into Phase 4)
- [x] `app/api/server.py`: `POST /offers`, `GET /offers/{id}`, `POST /offers/{id}/select`,
      `POST /offers/{id}/review`, `GET /offers` (business read-model), CORS enabled
- [x] Graph compiled with `PostgresSaver` on Neon; endpoints drive create / resume / read
- [x] Four-eyes enforced at API (409) before resume
- [x] Verified over HTTP end-to-end (create→select→review→generate; 409 recovery)
- [ ] AuthN/AuthZ (mocked personas per role) — emails→users now; real auth TBD
- [ ] Enforce "agent permissions ≤ current user's permissions" (Phase 7)

## Phase 7 — Agent (LLM via OpenRouter)  ✅ built
- [x] LLM client `app/agent/llm.py` (OpenRouter, OpenAI-compatible; model/key from .env; no-key fallback)
- [x] Understand: NL → `ExtractedIntent` (INFERRED); fuzzy make/model + company resolved to
      catalogue keys deterministically (`app/agent/resolve.py`) — LLM never invents identifiers
- [x] Confirm-intake interrupt: INFERRED → CONFIRMED before the engine consumes (gate reused)
- [x] Explain: grounded pricing + scenario/advisory text (EN/DE); numbers must exist in the
      ResultEnvelope or it falls back to a deterministic template (`app/agent/explain.py`)
- [x] LLM nodes wired into the SAME graph (understand, confirm_intake, explain_pricing, explain_scenarios)
- [x] API: `POST /offers/nl` + `POST /offers/{id}/confirm`; explanations surfaced in snapshots
- [x] Guardrails: LLM never calculates/scores/decides/selects; tests forced deterministic
      (`AGENT_DISABLE_LLM`); grounding check on every explanation
- [x] `scripts/agent_check.py` to verify OpenRouter connectivity after adding the key
- [ ] Reviewer-facing AI review summary at human_review (nice-to-have)
- [ ] Clarify node phrasing of missing-field questions (currently confirm handles it)

## Phase 8 — Orchestration (LangGraph)  ✅ skeleton built (LLM nodes pending)
- [x] Graph exists with deterministic nodes calling engine services (not the LLM)
- [x] State = the Offer (working copy); LangGraph owns transitions + resume
- [ ] Add LLM nodes (understand/explain) in Phase 7; insert into the existing graph

## Phase 9 — Workbench UI (React/Next.js) — *awaiting your references*
- [ ] One workbench, ~7 views of one Offer Case (inbox, intake, customer, asset+product,
      pricing+scenarios, credit/approval, review+output) (docs/01, source Turn 1 §11)
- [ ] Each screen answers: where am I / what do we know / what needs attention / what next
- [ ] Provenance + exceptions surfaced; EN/DE toggle

## Phase 10 — Negative flows (must demo)
- [ ] Missing customer/vehicle info · invalid asset/product combo · calculation unavailable
- [ ] Yellow scoring → review · Red economic → alternatives → recalc · Red compliance → blocked
- [ ] Unauthorized approval attempt · reviewer returns offer · scenario change → recalculation
- [ ] Special payment too high · term/mileage out of range · low RV confidence

## Phase 11 — Demo hardening
- [ ] End-to-end happy path scripted + bilingual demonstration
- [ ] Seed data set covering all personas/branches
- [ ] Traceability walk-through (audit trail + provenance for one offer)
- [ ] Explicit disclaimer surfaced: `DE_PKW_V1` = MVP reference policy, not production policy

## Cross-cutting / ongoing
- [ ] Verify external-API/legal claims before any LIVE adapter or compliance statement (docs/08 §4)
- [ ] Keep `DE_PKW_V1` versioned; bump to V2 when real client policy arrives (offers pin version)
- [ ] B2C path (affordability scoring, GDPR Art.22 / §506 BGB controls) — only if scope expands
- [ ] Keep tests deterministic; no randomness anywhere in engines/mocks
