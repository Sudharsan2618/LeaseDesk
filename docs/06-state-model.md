# 06 — State Model (workflow status × validation state)

> Two **independent** axes. Never merge them into one enum. The workflow status says *where the
> Offer is in the process*; the validation state says *how healthy the data is*. LangGraph (later)
> orchestrates transitions, but the state model itself is deterministic and must be validated
> before any AI work.

---

## 1. Axis A — Workflow status (one value per Offer)

```
DRAFT
  │ user submits a requirement
  ▼
UNDERSTANDING              (agent extracts structured fields — all INFERRED)
  │ extraction done
  ▼
CONTEXT_REQUIRED  ◄──────────────┐   (missing/unconfirmed context)
  │ context assembled + confirmed │
  ▼                               │
CONTEXT_COMPLETE                  │
  │                               │
  ▼                               │
VALIDATION_REQUIRED               │   (run completeness/validation)
  │ issues? ── yes ───────────────┘   (back to CONTEXT_REQUIRED to resolve)
  │ no blocking issues
  ▼
READY_FOR_CALCULATION
  │ engines run (calc + assessment + scoring)
  ▼
CALCULATED
  │ build 2–3 scenarios
  ▼
SCENARIOS_AVAILABLE
  │ user picks one
  ▼
SCENARIO_SELECTED
  │ submit for review
  ▼
PENDING_HUMAN_REVIEW
  │            │            │
approve      return       correct
  │            │            │
  │            ▼            ▼
  │      (back to CONTEXT_REQUIRED / READY_FOR_CALCULATION → recalc → rescore → revalidate)
  ▼
APPROVED
  │
  ▼
FINAL_VALIDATION
  │        │              │
READY   REQUIRES_ACTION  BLOCKED
  │        │              │
  │        └── resolve ───┘ (back into the loop) / BLOCKED is terminal for this attempt
  ▼ (READY only)
OFFER_GENERATED            ← terminal (MVP ends; no contract creation)
```

`RETURNED` is a sub-state of the review step (reviewer sent it back); it routes to
`CONTEXT_REQUIRED` or `READY_FOR_CALCULATION` depending on what must change.

---

## 2. Axis B — Validation / readiness

**Per-field status** (on every `ProvenanceValue`, see [02](02-domain-entities.md) §1.1):
`ESTABLISHED · CONFIRMED · REQUIRES_CONFIRMATION · INFERRED · MISSING · INVALID · INCONSISTENT`.

**Offer readiness rollup** (derived from the fields, stored on `offers.readiness`):
`COMPLETE · MISSING · REQUIRES_CONFIRMATION · INCONSISTENT · INVALID`.

Rollup rule (first match wins, worst-first):
1. any material field `INVALID` → `INVALID`
2. any material field `INCONSISTENT` → `INCONSISTENT`
3. any material field `MISSING` → `MISSING`
4. any material field `REQUIRES_CONFIRMATION`/`INFERRED` → `REQUIRES_CONFIRMATION`
5. else → `COMPLETE`

"Material field" = one the calculation/scoring/eligibility engines consume (defined per policy).

---

## 3. The two axes together (example)

```jsonc
{
  "offer_status": "CONTEXT_REQUIRED",
  "readiness": "REQUIRES_ACTION",       // UI-facing rollup; maps from readiness + blocking issues
  "issues": [
    { "field": "customer.address", "type": "MISSING", "blocking": true },
    { "field": "commercial.term_months", "type": "INFERRED", "blocking": false }
  ]
}
```

The **final-validation outcomes** (`READY` / `REQUIRES_ACTION` / `BLOCKED`) are a *decision*
produced at the `FINAL_VALIDATION` step, computed from readiness + open exceptions:
- `BLOCKED` — any hard/blocking exception open (sanctions, KYC fail, RED-compliance, unauthorized, calc failed).
- `REQUIRES_ACTION` — no hard blocks, but open soft exceptions or non-`COMPLETE` readiness.
- `READY` — readiness `COMPLETE`, all required reviews/approvals done, no open exceptions.

---

## 4. Transition guards (what must be true to advance)

| From → To | Guard |
|---|---|
| DRAFT → UNDERSTANDING | a requirement text exists |
| UNDERSTANDING → CONTEXT_REQUIRED | extraction produced structured fields |
| CONTEXT_REQUIRED → CONTEXT_COMPLETE | all **material** fields ∈ {ESTABLISHED, CONFIRMED} |
| CONTEXT_COMPLETE → VALIDATION_REQUIRED | always (runs validation) |
| VALIDATION_REQUIRED → READY_FOR_CALCULATION | readiness = COMPLETE **and** no blocking ValidationIssue |
| READY_FOR_CALCULATION → CALCULATED | calc + assessment + scoring all returned (no CALCULATION_FAILED) |
| CALCULATED → SCENARIOS_AVAILABLE | ≥1 scenario built and each priced |
| SCENARIOS_AVAILABLE → SCENARIO_SELECTED | user selected one scenario |
| SCENARIO_SELECTED → PENDING_HUMAN_REVIEW | user submitted; submitter recorded |
| PENDING_HUMAN_REVIEW → APPROVED | reviewer within authority approved; reviewer ≠ creator; band/value within limit |
| PENDING_HUMAN_REVIEW → (RETURNED) | reviewer returned/corrected → route back, mark fields to change |
| APPROVED → FINAL_VALIDATION | always |
| FINAL_VALIDATION → OFFER_GENERATED | outcome = READY |

Any recalculation trigger (human correction, scenario change, risk-band change) **invalidates**
downstream results: it drops the Offer back to `READY_FOR_CALCULATION` (or `CONTEXT_REQUIRED` if
data changed) and clears the now-stale CalculationResult/AssessmentResult/ScoringResult, so nothing
stale ever reaches review or PDF.

---

## 5. Recalculation / invalidation rules (critical, easy to get wrong)

When any of these change, mark dependent results stale and re-run from the right point:
- term / mileage / special payment / vehicle / discounts changed → re-run **residual → funding →
  margin → calc → scoring → eligibility** (full pipeline).
- customer/credit/KYC/sanctions changed → re-run **scoring → margin(risk_adjustment) → calc →
  eligibility**.
- scenario switched → the selected scenario's own results become the Offer's current results.
- reference rate re-fetched (new as-of date) → re-run **funding → margin → calc**.

Never let a `SelectedScenario` or `OfferOutput` reference a stale result — the PDF is built from a
**frozen snapshot** of the validated Offer JSON at generation time.

---

## 6. Terminal & re-entry

- `OFFER_GENERATED` is terminal for the MVP (handoff boundary; no contract creation).
- `BLOCKED` at final validation is terminal *for the attempt*; a compliance block stays blocked;
  an economic block can be reworked (new scenario/inputs) which re-enters the loop as a new pass.
- Every transition emits an `AuditEvent` (before/after/actor/timestamp/reason).
