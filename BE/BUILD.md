# Phase 1 — Deterministic Foundation (build guide)

Entities + integration adapters + engine + DB schema. **No AI, no UI** (by design — see
[docs/08 §6](docs/08-open-questions-and-verification.md)). Everything is deterministic and tested.

## Layout
```
app/
  core/        types.py (ProvenanceValue, ResultEnvelope, enums) · policy.py (DE_PKW_V1 loader)
  config/      de_pkw_v1.json                (the MVP reference policy — docs/05)
  domain/      entities.py                   (Offer aggregate + all entities — docs/02)
  integration/ base.py (adapter protocol + registry, LIVE/SANDBOX/MOCK)
               vehicle/reference_rate/vat/vies/sanctions/kyc/credit.py  (MOCK adapters — docs/03)
               fixtures/ vehicles.json, companies.json   (deterministic personas — docs/03 §5)
  engine/      residual · funding · margin · calculator · risk · eligibility
               exceptions_registry · orchestrator  (the pipeline — docs/04)
  service/     offer_factory.py              (assemble a B2B offer from primitives)
db/            schema.sql · triggers.sql      (Postgres + JSONB — docs/07)
tests/         test_engine.py                 (docs/04 §10 checklist + persona flows)
```

## Run
```bash
python -m pip install -r requirements.txt
python -m pytest -q                # 18 tests, all deterministic
```

Quick demo:
```bash
python -c "from app.integration.base import build_default_registry,AdapterMode; from app.service.offer_factory import build_b2b_offer; from app.engine.orchestrator import run_pipeline,compute_final_outcome; r=build_default_registry(AdapterMode.MOCK); o=run_pipeline(build_b2b_offer(r,vehicle_key='bmw-x1-sdrive18i',register_number='HRB-1001',term_months=36,annual_mileage_km=20000),r); c=o.calculation.value; print(o.scoring.value.band.value, c.monthly_gross_eur,'EUR/mo', compute_final_outcome(o).value)"
```

## Personas (drive every branch)
| register_number | persona | result |
|---|---|---|
| HRB-1001 | clean company | GREEN → priced → READY |
| HRB-2002 | new company | YELLOW → priced → REQUIRES_ACTION |
| HRB-3003 | over-exposed | RED (economic) → not priced → BLOCKED (reworkable) |
| HRB-4004 | sanctions hit | RED (compliance) → BLOCKED |
| HRB-5005 | KYC fail | RED (compliance) → BLOCKED |

Vehicles: `bmw-x1-sdrive18i` (37,800), `vw-passat-variant-20tdi` (42,100),
`porsche-taycan` (104,600 → high-value review).

## Key invariants (verified by tests)
- LLM is nowhere in this layer. Every number comes from `DE_PKW_V1` + the deterministic engine.
- Every result carries a `ResultEnvelope` (engine + policy versions + `inputs_digest`).
- Same inputs → identical outputs (`test_determinism`).
- `r==0` safe; `NetCap ≤ PV(residual)` → `SpecialPaymentTooHigh`; RED never priced; blocking
  exceptions stop auto-pricing; hard-compliance blocks bypass the weighted score.

## DB (Phase 2 — wired to Neon)
Schema + triggers are applied to the Neon `lease` database. `DATABASE_URL` lives in `.env`
(gitignored). Re-apply or bootstrap elsewhere:
```bash
psql "$DATABASE_URL" -f db/schema.sql
psql "$DATABASE_URL" -f db/triggers.sql
```
End-to-end through the real LangGraph flow (create → scenarios → review → generate, persisted):
```bash
python -m scripts.graph_demo
```
Persistence layer: `app/db/connection.py` (reads `.env`) + `app/db/repository.py`
(`seed_policy`, `ensure_user`, `upsert_offer` (the single projection writer), `load_offer`,
`record_review`, `save_output`, `write_audit`, `audit_trail`).

**LangGraph is the single source of truth for the flow.** All offers are created through the graph
(API `/offers/nl` or `/offers`); nothing writes offers outside it. DB-level integrity verified live:
four-eyes, policy-pin, append-only audit.

## Phase 4/6 — LangGraph workflow + FastAPI (hybrid model)
The workflow is a LangGraph `StateGraph` (`app/graph/`) whose nodes call the existing engine.
Human-in-the-loop uses `interrupt()`/`Command(resume=)`; persistence + resume are native via
`PostgresSaver` on the same Neon DB. Our tables stay the queryable record via ONE projection
writer, `repository.upsert_offer` (the stale-invalidation trigger was removed as redundant).

Graph shape: `run_pipeline → scenarios → select_scenario(interrupt) → human_review(interrupt) →
final_validation → generate_offer`. RED/blocked offers route straight to `final_validation`.

Drive it headless:
```bash
python -m scripts.graph_demo        # full HITL flow + a blocked RED offer, on Neon
```
Serve it (UI attaches here, same shape as the Agentic Ticket FE):
```bash
python -m uvicorn app.api.server:app --port 8100
# POST /offers → pauses at select; POST /offers/{id}/select → pauses at review;
# POST /offers/{id}/review → approve (four-eyes: reviewer≠creator, else 409) → OFFER_GENERATED
# GET /offers (business read-model), GET /offers/{id} (live workflow snapshot)
```
Four-eyes is checked at the API before resuming (clean 409, thread stays paused) with the DB
trigger as backstop. No LLM yet — nodes are deterministic; LLM slots into understand/explain in
Phase 7.

## Phase 7 — LLM agent (OpenRouter)
The LLM is used in exactly 4 graph nodes: `understand` (NL → structured, INFERRED), `confirm_intake`
(interrupt → CONFIRMED), `explain_pricing`, `explain_scenarios` (grounded, EN/DE). It NEVER prices,
scores, decides, or selects. Add to `.env` (see `.env.example`):
```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-6-luna       # exact OpenRouter slug
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1   # optional
```
Verify connectivity: `python -m scripts.agent_check`. Without a key everything still runs —
`understand` yields nothing (user confirms fields explicitly) and explanations use deterministic
templates. Tests force this fallback via `AGENT_DISABLE_LLM=1` (set in `conftest.py`) so the suite
is deterministic even with a key present.

NL API flow: `POST /offers/nl {nl_request}` → pauses at `confirm_intake` (proposed fields) →
`POST /offers/{id}/confirm {vehicle_key, register_number, term_months, annual_mileage_km}` →
`/select` → `/review`. Grounding check: any number the LLM writes must exist in the results or the
template is used instead.

## Adapter modes
All adapters ship in `MOCK` (deterministic fixtures). `build_default_registry(AdapterMode.LIVE)`
is the switch point for real free/official calls later; response schemas stay identical so the
engine does not change (docs/03 §1).
