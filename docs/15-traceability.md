# 15 — Traceability Matrix (FR / BR / AC → status → implementation → test)

> The backbone of the validate loop in [14-build-plan.md](14-build-plan.md). Every VALIDATE gate
> updates this file. A requirement is only `verified` when a test (or an explicit manual check)
> proves it.
>
> **Status legend:** `❌ not-started` · `🟡 partial` · `✅ built` (code exists, not yet proven) ·
> `✔ verified` (a test/check proves it).
>
> **Baseline (Phase 0, 2026-09-23):** BE `33 passed`; FD `tsc` clean. Statuses below reflect the
> **pre-generalization build** (PKW-only, single-actor workspace) measured against the client spec —
> so much is `🟡`/`❌` by design; the build plan closes them phase by phase.

---

## Functional Requirements (FR-01 … FR-63)

### 11.1 Intake & Intent — Phase 3
| ID | Requirement | Status | Where | Proof |
|---|---|---|---|---|
| FR-01 | Enter requirement in NL and/or structured | ✅ | `agent_nodes.intake_process`, `/offers/nl` | — |
| FR-02 | Identify relevant Offer info in the requirement | ✅ | flexible `ExtractedIntent` (slots + asset_filters + constraints) + `_merge` | `test_extract` |
| FR-03 | Present interpreted requirement for confirmation | ✅ | per-step confirm gates | `test_graph` walk |
| FR-04 | Identify ambiguous info needing confirmation | ✅ | `Ambiguity` slot surfaced in gates | `test_extract` (budget currency/basis) |
| FR-05 | Correct/add info before proceeding | ✅ | step overrides + free-text merge | `test_graph` |

### 11.2 Customer, Product & Asset Context — Phases 1–2
| ID | Requirement | Status | Where | Proof |
|---|---|---|---|---|
| FR-06 | Identify **and confirm** customer/partner | ✅ | `select_partner_node` + `search_partners` (dedupe) + confirm gate | `test_graph` (walk + block-without-partner) |
| FR-07 | Present relevant partner info | 🟡 | partner step candidates + snapshot provenance | — |
| FR-08 | Select/confirm the **product** | ✅ | `select_product_node` (business line + product from reference data) + confirm gate | `test_graph` walk |
| FR-09 | Select/provide **asset/object** info | ✅ | `select_asset_node` (category-generic + `_filter_catalogue`) + confirm gate | `test_graph` walk |
| FR-10 | Identify missing/needs-confirmation info | 🟡 | interrupt `missing` | — |
| FR-11 | Correct info presented | 🟡 | intake overrides | — |

### 11.3 Completeness & Validation — Phase 2/4
| ID | Requirement | Status | Where | Proof |
|---|---|---|---|---|
| FR-12 | Identify mandatory info not provided | 🟡 | `CONSUMABLE_STATUSES` gate | — |
| FR-13 | Identify incomplete/inconsistent info | 🟡 | eligibility checks | — |
| FR-14 | Distinguish complete/confirm/missing/invalid (4 states) | ✅ | `core.types.info_state` + `_pv` | `test_info_state` |
| FR-15 | Identify action to resolve a material issue | 🟡 | exception `next_action` | — |
| FR-16 | **Prevent progression** on unresolved mandatory | ✅ | `_step_router` advances only on confirm∧valid | `test_step_blocks_without_mandatory_field` |
| FR-17 | Reassess affected requirement on change | ✅ | correction loop | `test_out_of_range_triggers_correction_loop` |

### 11.4 Calculation & Assessment — Phases 5–6
| ID | Requirement | Status | Where | Proof |
|---|---|---|---|---|
| FR-18 | Produce commercial calculation | ✔ | `engine/calculator.py` | `test_engine` |
| FR-19 | Asset-assessment outcome | ✔ | `engine/asset_assessment.py` → `offer.asset_assessment` (distinct `AssetAssessmentOutcome`) | `test_scoring` (available_for_pkw) |
| FR-20 | Risk/scoring outcome | ✔ | `engine/risk.py` G/Y/R band + auto/manual `ScoringPattern` | `test_scoring` |
| FR-21 | Distinguish inputs from outcomes | ✅ | `ResultEnvelope` | — |
| FR-22 | Identify when an outcome is unavailable/needs action | ✔ | `ASSESSMENT_UNAVAILABLE` (blocking) on UNAVAILABLE dependency | `test_scoring` (unavailable_blocks) |
| FR-23 | Review inputs behind a material outcome | ✅ | calc breakdown panel | — |

### 11.5 Scenario Comparison — Phase 6
| ID | Requirement | Status | Where | Proof |
|---|---|---|---|---|
| FR-24 | Create alternatives by changing params | ✅ | term sweep + budget-constraint fit (`engine/budget.py`) | `test_budget` |
| FR-25 | Present limited viable set | ✅ | ScenarioCards | — |
| FR-26 | Show assumptions/outcomes per scenario | ✅ | ScenarioCards | — |
| FR-27 | Show material differences | ✅ | compare() incl. fits_budget/headroom | `test_budget` |
| FR-28 | Select preferred scenario | ✔ | `/select` | `test` graph select |
| FR-29 | Material change → recalc + reassess | ✅ | gate adjust loop | — |

### 11.6 Explanation — Phase 4/6
| ID | Requirement | Status | Where | Proof |
|---|---|---|---|---|
| FR-30 | Explain key inputs | 🟡 | `explain_pricing` | — |
| FR-31 | Explain scenario differences | 🟡 | `explain_scenarios` | — |
| FR-32 | Explain missing info/validation | ❌ | — | Phase 3/4 |
| FR-33 | Present scoring/status understandably | ✅ | band + pattern + assessment status in `explain._facts` (grounded) | Phase 7 UI |
| FR-34 | Identify next action when blocked | ✅ | `BlockedPanel` WHAT→WHY→NEXT + Next bar | FD |

### 11.7 Human Review & Decision — Phase 4
| ID | Requirement | Status | Where | Proof |
|---|---|---|---|---|
| FR-35 | Review full context/scenario/outcomes | ✅ | `human_review_node` interrupt payload | `test_graph` review |
| FR-36 | Review exceptions/validation | ✅ | review payload `exceptions` + `outcome` | `test_graph` review |
| FR-37 | Approve where satisfied | ✅ | review `decision=confirm` (can_generate) | `test_gate_select_review_then_generate` |
| FR-38 | Return for correction | ✅ | review `decision=return` → workspace_gate | `test_review_return_goes_back_to_gate` |
| FR-39 | Make permitted changes | ✅ | mutable gate + adjust→wizard | — |
| FR-40 | Material change → reassess before finalize | ✅ | return→gate→adjust re-runs pipeline; route_after_final | `test_graph` |

### 11.8 Final Validation — Phase 4
| ID | Requirement | Status | Where | Proof |
|---|---|---|---|---|
| FR-41 | Confirm required info complete | 🟡 | `final_validation_node` | — |
| FR-42 | Confirm inconsistencies/exceptions resolved | 🟡 | final_validation | — |
| FR-43 | Confirm calc/assessment/scoring available | ✅ | unavailable asset-assessment/scoring → blocking → `compute_final_outcome` BLOCKED | `test_scoring` |
| FR-44 | Confirm required **human review** completed | ✅ | `human_review` gate mandatory before generate | `test_graph` review |
| FR-45 | Indicate Ready/Requires-Action/Blocked | ✔ | `compute_final_outcome`; Yellow/Manual→REQUIRES_ACTION, compliance-Red/assessment-unavailable→BLOCKED | `test_scoring` |
| FR-46 | Prevent generation on unresolved mandatory | ✅ | review `can_generate≠BLOCKED` + route_after_final | — |

### 11.9 Offer Generation — Phase 8
| ID | Requirement | Status | Where | Proof |
|---|---|---|---|---|
| FR-47 | Contains customer/partner info | 🟡 | generate_offer summary | artifact TBD |
| FR-48 | Contains product+asset info | 🟡 | summary | product TBD |
| FR-49 | Contains selected scenario+terms | ✅ | summary | — |
| FR-50 | Contains calc+assessment outcomes | 🟡 | summary | assessment TBD |
| FR-51 | Contains scoring/status outcome | 🟡 | summary | — |
| FR-52 | Identifies assumptions/resolved exceptions | ❌ | — | Phase 8 |
| FR-53 | Represents final reviewed+validated Offer | 🟡 | OFFER_GENERATED | — |

### 11.10 Status & Traceability — Phase 8
| ID | Requirement | Status | Where | Proof |
|---|---|---|---|---|
| FR-54 | Show current status + next action | ✅ | StatusSpine, snapshot | — |
| FR-55 | Show material changes | ✅ | audit trail | — |
| FR-56 | Retain selected scenario + changes | ✅ | offer state | — |
| FR-57 | Show validation/review/decision actions | ✅ | audit trail | — |
| FR-58 | Understand how final Offer was reached | 🟡 | AuditTimeline | — |

### 11.11 Authorization & Language — Phases 2/9
| ID | Requirement | Status | Where | Proof |
|---|---|---|---|---|
| FR-59 | Apply user authorization set | ❌ | (single actor) | out of scope per decision |
| FR-60 | Block unauthorized actions | ❌ | — | out of scope per decision |
| FR-61 | Agent doesn't grant/bypass authorization | ✔ | n/a (no auth) | — |
| FR-62 | Clear negative-workflow messages | ✅ | `lib/negative.ts` (WHAT→WHY→NEXT) + BlockedPanel + review | FD |
| FR-63 | Two-language experience | ❌ | English only | Phase 9 |

---

## Business Rules (BR-01 … BR-19)

| ID | Rule | Status | Where | Proof |
|---|---|---|---|---|
| BR-01 | Distinguish provided vs inferred info | ✅ | `ProvenanceValue.status` | — |
| BR-02 | Missing ≠ confirmed | ✔ | `CONSUMABLE_STATUSES` gate | intake tests |
| BR-03 | Ambiguous requires confirmation | ✅ | `Ambiguity` slot; surfaced in gates, not auto-resolved | `test_extract` |
| BR-04 | Conflicting info surfaced | 🟡 | `_merge` reset logic | — |
| BR-05 | Material change → reassess | ✅ | correction/adjust loops | — |
| BR-06 | Calc from controlled inputs | ✔ | engine | `test_engine` |
| BR-07 | Agent can't alter calc outcome | ✔ | `grounding_check` | agent tests |
| BR-08 | Agent can't override pricing/eligibility | ✔ | engine-only pricing | — |
| BR-09 | Scenarios within permitted params | ✅ | scenarios use product policy; eligibility-gated terms | `test_budget`/`test_scenarios` |
| BR-10 | No non-viable scenario shown as viable | ✅ | eligibility check skips invalid terms; budget-fit flags over-budget | `test_scenarios` |
| BR-11 | Scoring presented as established | ✔ | scoring/assessment are engine `ResultEnvelope`s (engine+policy+digest) | `test_scoring` (engine_envelopes) |
| BR-12 | Agent explains, doesn't reinterpret scoring | ✔ | grounding; band/pattern surfaced verbatim | — |
| BR-13 | Missing scoring blocks full validation | ✔ | scoring/assessment unavailable → blocking → not validated | `test_scoring` |
| BR-14 | Agent no autonomous credit decision | ✔ | engine-only | — |
| BR-15 | Human review before generation | ✅ | `human_review` gate on the generate path | `test_graph` review |
| BR-16 | Material exceptions → human resolution | ✅ | review shows exceptions; blocked can't confirm | `test_graph` |
| BR-17 | Reviewer approve/return/correct | ✅ | review decision confirm/return | `test_graph` |
| BR-18 | Post-review change → reassess | ✅ | return→gate→adjust re-runs pipeline | `test_graph` |
| BR-19 | No bypass of review/validation | ✅ | generate can't set finalize; only review does | `test_graph` |

---

## Acceptance Criteria (AC-01 … AC-18) — verified in Phase 10

| ID | Criterion | Status |
|---|---|---|
| AC-01 | Start without navigating unrelated activities | 🟡 |
| AC-02 | Capture material info from requirement | 🟡 |
| AC-03 | Confirm/correct/complete interpreted info | 🟡 |
| AC-04 | Missing/incomplete/inconsistent clearly identified | 🟡 |
| AC-05 | Can't progress with unresolved mandatory | 🟡 |
| AC-06 | Required commercial/asset/scoring outcomes available | 🟡 |
| AC-07 | Evaluate multiple controlled scenarios | ✅ |
| AC-08 | Compare + select preferred scenario | ✅ |
| AC-09 | Material changes trigger reassessment | ✅ |
| AC-10 | Understand assumptions/outcomes/exceptions | 🟡 |
| AC-11 | Human reviewer approve/return | ❌ |
| AC-12 | Final validation says Ready/Requires-Action/Blocked | 🟡 |
| AC-13 | Generate validated Offer as output | 🟡 |
| AC-14 | Generated Offer reflects final selected scenario | ✅ |
| AC-15 | Changes/review/decisions traceable | ✅ |
| AC-16 | Authorization respected | ❌ (out of scope per decision) |
| AC-17 | Authorization respected (dup in spec) | ❌ (out of scope per decision) |
| AC-18 | Bilingual core screens + messages | ❌ (Phase 9) |

---

## Rollup (Phase 0 baseline)

- **FR:** ✔ 8 · ✅ 11 · 🟡 33 · ❌ 11  (of 63)
- **BR:** ✔ 7 · ✅ 3 · 🟡 8 · ❌ 1  (of 19)
- **AC:** ✅ 5 · 🟡 10 · ❌ 3  (of 18)

The strong core (deterministic engine, grounding guardrails, scenario compare, audit, reassessment
loops) is already `✔/✅`. The gaps cluster exactly where doc 12 predicted: **product/asset generality,
per-step confirm gates, ambiguity handling, the human-review gate, scoring G/Y/R, asset assessment,
the offer artifact, and i18n** — which is the order the build plan attacks them.
