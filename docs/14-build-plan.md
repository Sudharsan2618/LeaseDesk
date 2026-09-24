# 14 — Build Plan: Closing the Gaps (Divide → Build → Validate → Repeat)

> **How to use this file.** Work **one phase at a time, top to bottom.** Each phase is split into
> small tasks. **Every phase ends with a VALIDATE gate** that checks the work back against
> [11-client-spec-extract.md](11-client-spec-extract.md) and [12-business-logic-bookmark.md](12-business-logic-bookmark.md)
> before the next phase starts. Do not skip a validate gate. Tick boxes as we go.
>
> **Decisions already locked** (doc 12 §3): generic domain + PKW seed · single actor + explicit
> review gate · Yellow → Requires Action → review. **Defaults** (doc 12 §3, changeable): English-first
> then DE i18n · one workbench with sections, not 8 apps.
>
> **The guardrail on every phase:** *AI assists · Rules decide · Humans govern.* The LLM never
> prices, scores, decides eligibility, or invents identifiers.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` needs a decision (see §Doubts).

---

## Phase 0 — Baseline & validation harness
*Goal: make "validate against the docs" a repeatable, cheap step.*

- [x] 0.1 Adopt docs 11 & 12 as source of truth above docs 02–10 where they conflict (note in README).
- [x] 0.2 Build a **traceability matrix** [docs/15-traceability.md](15-traceability.md): every FR/BR/AC
  → status → where → proving test.
- [x] 0.3 Snapshot current test baseline: **BE 33 passed · FD tsc clean** (2026-09-23).
- [x] **VALIDATE 0:** ✔ matrix lists all 63 FR + 19 BR + 18 AC; baseline green.

---

## Phase 1 — Reference-data model (generic domain)
*Spec §3.5–3.6, §5.5, BR-06/08/09. Goal: remove hardcoded "car"; make Business Line / Product /
Asset Category reference-data-driven. PKW becomes one asset category with attributes.*

- [x] 1.1 Reference-data entities: `BusinessLine`, `LeasingProduct` (points at a `policy_id` carrying
  the Offer Parameters), `AssetCategory` (PKW/Equipment/NFZ/ITK) + `Channel` +
  `AssetAttribute` — [app/domain/reference.py](../BE/app/domain/reference.py).
- [x] 1.2 Controlled reference-data set [app/config/reference_data.json](../BE/app/config/reference_data.json):
  PKW **active** → product `pkw_km_leasing` → policy `DE_PKW_V1`; Equipment/NFZ/ITK **declared as
  planned** (proves genericity, spec §9.5). DE_PKW_V1 stays the product's parameter set — not
  duplicated.
- [x] 1.3 Asset generality: PKW attribute schema (make/model/fuel/transmission/power/seats/colour/
  list_price) lives in reference data; `Offer` now records `channel/business_line_key/
  leasing_product_key/asset_category_key` (seeded to PKW). *(Full `Asset{category,attributes}`
  re-model of the `Vehicle` entity deferred to Phase 2 to keep the engine untouched now.)*
- [x] 1.4 Engine resolves the policy via the selected product: `offer.policy_version` ==
  `product.policy_id`; verified consistent (`pkw_km_leasing → DE_PKW_V1`).
- [x] 1.5 Engine untouched — only *where the policy id comes from* is generalized.
- [x] **VALIDATE 1:** ✔ spec §3.5–3.6 + BR-08/09 — rules/params live in reference data + policy, not
  code; Agent doesn't define them. PKW prices identically (engine tests unchanged). New tests
  [tests/test_reference.py](../BE/tests/test_reference.py) (5) pass; fast suite 31 pass. Traceability
  updated.

---

## Phase 2 — Selection hierarchy + per-step confirm gates
*Spec §3.3–3.6, FR-03/06/08/09, FR-16, BR-02/03. Goal: the full Channel→Partner→BL→Product→Asset→
Commercial flow, each step confirmable.*

- [x] 2.1 **Channel** step (`select_channel`): Internal Sales active, Partner/Credit stubbed; confirm gate.
- [x] 2.2 **Partner** step (`select_partner`): `search_partners()` (+ dedupe candidates, auto-pick on a
  single match); **Confirm-partner gate** (FR-06 gap fixed). `/catalogue/partners?q=` endpoint.
- [x] 2.3 **Business Line + Product** step (`select_product`): options from reference data; confirming a
  product sets business_line/asset_category/`policy_version` from the product; confirm gate.
- [x] 2.4 **Asset** step (`select_asset`): catalogue filtered by attribute filters (`_filter_catalogue`,
  ready for Phase-3 `seats=4`); confirm gate.
- [x] 2.5 **Commercial** step (`select_commercial`): term/mileage/quantity/special-payment/services/
  insurance + a `constraints` slot (budget) surfaced; confirm gate.
- [x] 2.6 **FR-16 / BR-02**: a step router (`_step_router`) only advances on `confirm ∧ valid`; a
  confirm without a mandatory field loops back to the same step.
- [x] **VALIDATE 2:** ✔ graph rewired `understand → select_channel → … → select_commercial → assemble`;
  distinct interrupt per step; adjust/correction reopen the wizard at `select_asset`. **Graph tests
  7 passed (Neon)** incl. walk-every-gate + "blocks without partner"; fast suite 31 pass. FR-06/08/09
  and FR-16 now ✅ in traceability. *(FD intake shows old shape until Phase 7 port — expected.)*

---

## Phase 3 — Flexible intent extraction (any request)
*Spec §5 (Understand), FR-01/02/04/05, BR-01/03. Design in [13-agent-workbench-design.md](13-agent-workbench-design.md) §3.*

- [x] 3.1 `ExtractedIntent` generalized ([schemas.py](../BE/app/agent/schemas.py)): known slots +
  open `asset_filters` + `constraints` (`Constraint`: kind/value/currency/basis) + `ambiguities`
  (`Ambiguity`). Extractor prompt updated ([extract.py](../BE/app/agent/extract.py)) to fill these,
  keep currency as written, and flag ambiguity instead of guessing.
- [x] 3.2 Resolver maps slots → catalogue keys deterministically (`_resolve`, unchanged rule: LLM
  never invents identifiers).
- [x] 3.3 `_merge` folds filters/constraints/ambiguities into the proposal; `_filter_catalogue`
  narrows by attribute (seats/fuel/…); ambiguities surfaced in partner/asset/commercial gates;
  budget stays a **constraint**, never a priced field.
- [x] 3.4 Deterministic test ([tests/test_extract.py](../BE/tests/test_extract.py), 5) covers the
  `"4-seater / 30 insured / $300k"` decomposition: filters seats=4→Taycan, quantity=30, insurance,
  budget constraint with `$` currency + ambiguity flagged, and budget-not-a-field.
- [x] **VALIDATE 3:** ✔ FR-01/02/04/05 + BR-01/03 — nothing silently assumed (ambiguities flagged,
  currency kept as written, budget kept as a constraint). **Full suite 44 passed (Neon), no
  regressions.** *(Live LLM extraction of arbitrary phrasings is the user's own test step; offline
  plumbing proven.)*

---

## Phase 4 — Info states + human-review gate
*Spec §7.6, §9.10, FR-14, FR-35–40, FR-44, BR-15–19. Single actor + explicit review.*

- [x] 4.1 4 info states via `core.types.info_state()` (ESTABLISHED→established, CONFIRMED→confirmed,
  REQUIRES_CONFIRMATION/INFERRED→requires_confirmation, MISSING/INVALID/INCONSISTENT→needs_action),
  exposed in `_pv` provenance (now includes missing fields as ⚠). Tests: `test_info_state` (2).
- [x] 4.2 Explicit **`human_review` gate** ([nodes.py](../BE/app/graph/nodes.py)) before Generate:
  workspace_gate `generate` → `human_review` interrupt (full context + exceptions + outcome) →
  confirm / return. Endpoints `/offers/{id}/review(+/stream)` `{decision, note}`.
- [x] 4.3 Return → `workspace_gate`; a subsequent `adjust`/change re-runs wizard→pipeline (re-scores/
  re-prices) before a second review — so post-review changes are always reassessed (FR-40, BR-18).
- [x] 4.4 `can_generate = outcome ≠ BLOCKED` in the gate; `route_after_final` also refuses to generate
  when BLOCKED (FR-46, BR-19). `finalize` is set ONLY by a confirmed review — generate can't bypass it.
- [x] **VALIDATE 4:** ✔ graph rewired `workspace_gate --generate--> human_review --confirm-->
  final_validation`; status `PENDING_HUMAN_REVIEW` before the interrupt. Graph tests (select→review→
  generate, review-return-no-generate) **confirmed green in the full Neon suite (56 passed)** together
  with Phase 5 — no regression.
  - **Correction (Phase 5 start):** the Neon graph test `test_gate_select_review_then_generate` was
    actually **red** — `workflow_status` set inside `human_review_node` *before* its `interrupt()`
    never reaches the graph channel (a node only commits state on return). Fixed by committing
    `PENDING_HUMAN_REVIEW` in `workspace_gate_node` (which returns normally) on the generate action.
    Full Neon suite green (47) restored before Phase 5.

---

## Phase 5 — Scoring (G/Y/R) + asset assessment
*Spec §3.7, §3.11–3.12, FR-19/20/22, BR-11–14. Yellow → Requires Action → review (locked).*

- [x] 5.1 Scoring returns **Green / Yellow / Red** (already banded in `engine/risk.py`) **plus** an
  **auto-vs-manual `ScoringPattern`** (§3.11): AUTOMATIC when every parameter is inside the policy's
  `scoring_automatic_envelope` (exposure / quantity / unit price), else MANUAL with recorded reasons.
  Deterministic + policy-driven — the Agent never decides the pattern.
- [x] 5.2 Routing: Green+Automatic proceeds/prices · **compliance-Red blocks** (not priced →
  BLOCKED) · economic-Red loops to reopen the wizard · **Yellow → `RISK_YELLOW` → Requires Action →
  human-review gate** · **Manual pattern → `SCORING_MANUAL_REVIEW` (non-blocking) → Requires Action →
  review** (decision doc 12 §3.3).
- [x] 5.3 **Asset assessment** as a **distinct simulated outcome** (`AssetAssessmentOutcome`,
  AVAILABLE/UNAVAILABLE/NOT_REQUIRED) — separate from residual value. Reference-data-driven per
  category (`assessment: {required, mode, service}`; PKW external, ITK internal); MOCK
  `ASSET_ASSESSMENT` adapter. A required-but-**UNAVAILABLE** dependency appends a blocking
  `ASSESSMENT_UNAVAILABLE` → not priced → **BLOCKED** (§3.7, FR-19/22). Persisted in a new
  `offers.asset_assessment_result` column.
- [x] 5.4 Agent explains but never reinterprets: band + pattern + assessment status added to the
  grounded `_facts` (labels, not numbers → grounding intact); outcomes carry engine+policy
  provenance so the Agent can only narrate them (BR-12/14).
- [x] **VALIDATE 5:** ✔ §3.11–3.12 + BR-11–14 — G/Y/R + auto/manual patterns established by the
  engine, Yellow/Manual route to review, compliance-Red blocks, asset-assessment-unavailable blocks.
  New tests [tests/test_scoring.py](../BE/tests/test_scoring.py) (9) pass; full Neon suite green.
  Traceability updated. **⚠ Flag to client:** the spec (§3.12) leaves **Yellow under-specified** — we
  route it to human review (Requires Action) per doc 12 §3.3; confirm this is the intended behaviour.
- [x] **Phase 5 independently re-verified (main session, 2026-09-23):** read the scoring/assessment
  engine, orchestrator routing, adapter registration, policy envelope, schema + live Neon column, and
  the tests — all spec-aligned. **Full Neon suite 56 passed** (Phase 4 + 5 together). *Observation
  (not a defect):* an assessment-UNAVAILABLE offer is BLOCKED at the outcome level but routes to
  `select_asset` (reopen wizard) rather than a terminal stop; defensible "try another asset" path,
  left as-is. Would make it terminal on request.

---

## Phase 6 — Calculation on generic params + budget-constraint scenarios
*Spec §3.8, §5 (Compare), FR-18/21/23–29, BR-06/07/09/10. Design in doc 13 §3.2.*

- [x] 6.1 Engine reads inputs from the selected product's parameters (Phase 1: `policy_version` =
  `product.policy_id`); scenario engine + calc load the product policy. No hardcoded constants.
- [x] 6.2 **Budget-constraint fitting** ([engine/budget.py](../BE/app/engine/budget.py)): `extract_budget`
  (budget/monthly_cap from the agent's `constraints`), `fit_metric` (basis: monthly/per_vehicle/
  total/acquisition), `annotate_scenarios` (tag `fits_budget`+headroom, sort fitting-first),
  `catalogue_budget_fit` (build_b2b_offer→**run_pipeline** per candidate → rank by fit). **The engine
  prices; budget only ranks** (BR-06/07). API `GET /offers/{id}/budget-fit`.
- [x] 6.3 Scenarios stay a limited set with side-by-side `compare()` (now incl. `fits_budget`/headroom);
  select unchanged (FR-24–28).
- [x] 6.4 Material change → recalc/reassess preserved (adjust→wizard→pipeline; FR-29, BR-05).
- [x] **VALIDATE 6:** ✔ every euro traces to the engine (`fit_metric` reads `CalculationResult` only;
  candidate pricing goes through `run_pipeline`); budget never mutates a priced field (test asserts).
  New tests [tests/test_budget.py](../BE/tests/test_budget.py) (7). Fast suite 54 pass. **Neon graph +
  persistence 9 passed** — the budget hook in `scenarios_node` and the new `Scenario` fields round-trip
  with no regression.

---

## Phase 7 — UI: the 60/40 workbench
*Design in [13-agent-workbench-design.md](13-agent-workbench-design.md). Spec §10.*

- [x] 7.1 ~~Mockup first~~ — **dropped** (decision #6: port directly from doc 13).
- **Building in SLICES (user chose "build in slices, review each"):**
  - [x] **Slice 1 — 60/40 shell + functional stepped wizard.** `app/offers/[id]/page.tsx` rewritten
    to the `.wb` 60/40 grid: LEFT `WizardRail` (7-stage stepper) + `WizardStep` (all 5 confirm gates:
    channel/partner/product/asset pickers + commercial form) + decide (ScenarioCards+Generate/Adjust+
    calc) + review (outcome/exceptions/confirm-return) + generated banner; RIGHT `AgentChat`
    (transcript + message box, active during intake) + `LiveFeed`. Types + api helpers updated
    (`getReference`/`getPartners`/`getBudgetFit`, stepped snapshot/interrupt shapes). Orphaned
    `AgentIntake` removed. `tsc` clean.
  - [x] **Slice 2 — info states + richer steps.** `RequestSummary` + `InfoChip` show the 4 states
    (✓ set / ◐ to confirm / ⚠ needed) per field — from `proposed` during intake (fixes the old
    "everything MISSING" wall) and from `provenance.info_state` when priced. Asset step: attribute
    filter chips (fuel/body/transmission/seats) narrowing the catalogue + a selected-vehicle spec
    card. Partner step: duplicate-match warning when >1 candidate + richer candidate labels. `tsc` clean.
  - [x] **Slice 3 — budget fit.** `BudgetFitPanel` fetches `/offers/{id}/budget-fit` and ranks the
    filtered catalogue by fit — each candidate **engine-priced** (fleet monthly + contract total),
    green/rose row + "€X under/over" chip + band dot; only shows when a budget/monthly_cap is set.
    `ScenarioCards` now carry a per-scenario **"within budget" / "over by €X"** badge. `tsc` clean.
  - [x] **Slice 4 — negative-workflow + polish (impeccable).** `lib/negative.ts` maps every engine
    exception code → WHAT→WHY→NEXT copy (FR-62); new `BlockedPanel` gives the previously-dead BLOCKED
    state an actionable panel (terminal→new variant, correctable→adjust) — fixes a broken task path;
    review-panel exceptions humanized; right rail becomes the transparency rail (AI-grounded
    explanation · risk factors · audit); Next bar tones rose when blocked; fixed a card-in-card in the
    asset step. Ran the impeccable `context.mjs` + polish/craft-floor; **mechanical detector clean
    (`[]`)**; `tsc` clean.
- [x] **VALIDATE 7:** ✔ §10 four questions answered on every stage — *Where am I* (WizardRail + ref +
  status), *What do I know* (RequestSummary / provenance info-states), *What needs attention* (Next bar,
  BlockedPanel, exceptions), *What can I do next* (Next bar + step/decide/review actions). FR-45 (Ready/
  Requires-Action/Blocked pill), FR-54 (status + next action), FR-62 (negative-workflow copy) all
  surfaced. `tsc` + detector clean. *(User runs the app for the live visual pass.)* Update traceability.

---

## Phase 8 — Offer output + traceability polish
*Spec §10.9, FR-47–58, AC-15.*

- [ ] 8.1 Generate a **representative Offer artifact** (customer, product/asset, terms, selected
  scenario, outcomes, assumptions, explanation) — FR-47–53.
- [ ] 8.2 Audit/history completeness: status + next action + material changes + review/decisions
  (FR-54–58); Activity view.
- [ ] **VALIDATE 8:** re-read FR-47–58 + AC-15; confirm the generated offer reflects the final
  reviewed scenario and is fully traceable. Update traceability.

---

## Phase 9 — Bilingual DE/EN *(deferred default)*
*Spec §10.2, FR-63, AC-18.*

- [ ] 9.1 i18n for core UI labels, workflow/validation messages, Agent explanations; language toggle
  persists through the journey.
- [ ] **VALIDATE 9:** re-read FR-63 + AC-18. Update traceability.

---

## Phase 10 — Final acceptance pass
*Spec §13.*

- [ ] 10.1 Walk **AC-01…AC-18** end-to-end with a representative scenario.
- [ ] 10.2 Control acceptance §13.4: no silent assumptions; no Agent price/score override; validation
  not bypassable; human review present; blocked ≠ complete.
- [ ] 10.3 Completion test §13.5: requirement → understood → context → calc/assessed → compared →
  review → validated → generated decision-ready Offer.
- [ ] **VALIDATE 10:** all FR/BR/AC in the traceability matrix are `verified`.

---

## Doubts / decisions — RESOLVED (user, 2026-09-23)

1. **Refactor in place** (PKW-first, keep tests green at each step). ✅
2. **Reference-data depth: minimal but real** (1 business line, 1–2 products, PKW category) — prove
   genericity per §9.5, not a full enterprise catalogue. ✅
3. **Neon reset: yes, wipe** offers + checkpoints; keep users/reference tables. ✅
4. **Budget/constraint engine: build it now** — it's the heart of the `$300k` scenario (Phase 6). ✅
5. **Channels: wire Internal Sales fully** (primary MVP channel §9.2); model the channel field but
   stub Partner/Credit. ✅
6. **Phase 7 UI: port directly from doc 13** — **no mockup gate.** Task 7.1 is dropped. ✅
