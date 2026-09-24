# 01 — Knowledge Graph (deduplicated, everything connected)

> Derived from [00-source-of-truth.md](00-source-of-truth.md). This is the single connected
> picture of the whole problem, with the repetition removed. Read this first to get the shape;
> read the numbered docs after it to get the detail.

---

## 0. The one law that governs every node

```
AI ASSISTS  →  DETERMINISTIC RULES DECIDE  →  HUMANS GOVERN
```

Corollaries that appear over and over in the source, collapsed into three:
1. **Never silently convert uncertainty into business truth** — every field carries provenance.
2. **The LLM is never inside a calculation, scoring, or eligibility decision** — it only reads/explains their output.
3. **Agent permissions ≤ the current human user's permissions.**

Everything below is an application of these three.

---

## 1. The central node: the OFFER CASE

The Offer Case is the aggregate root. Every other entity hangs off exactly one Offer.

```
                                   OFFER CASE
                                (aggregate root)
                                       │
    ┌──────────┬──────────┬───────────┼───────────┬──────────┬──────────┐
    ▼          ▼          ▼           ▼           ▼          ▼          ▼
 ACTOR     CUSTOMER    VEHICLE     LEASING     COMMERCIAL   RESULTS    GOVERNANCE
 (user/    /PARTNER    /ASSET      PRODUCT     REQUIREMENT  bundle     bundle
  role)                                        (term,
                                                mileage,
                                                budget,
                                                special
                                                payment)
                                                   │
                          ┌────────────────────────┼───────────────────────┐
                          ▼                         ▼                       ▼
                    RESULTS bundle           SCENARIOS[A,B,C]        GOVERNANCE bundle
                    - CalculationResult      each →                 - ValidationIssue[]
                    - AssessmentResult         its own              - Exception[]
                    - ScoringResult (G/Y/R)    CalculationResult    - Review[]
                                             + one SelectedScenario - AuditEvent[]
                                                                    - OfferOutput (PDF)
```

**Key insight (repeated across the source):** the real system is *one Offer Workbench showing many
views of one Offer Case* — not eight independent modules. The 7–8 UI screens are lenses on this
single object.

---

## 2. The horizontal flow (the executable spine)

This is the deduplicated merge of: the Turn-1 "knowledge graph", the Turn-1 "21-step happy path",
the Turn-1 "condensed developer brain", and the Turn-5 "buildable MVP spine". They are all the
same pipeline.

```
USER INTENT (natural language)
      │  ┌─ AGENT: Understand ── extract {customer, vehicle, term, mileage, budget, intent}
      ▼  │
STRUCTURED OFFER CASE
      │  ┌─ AGENT: Assemble ──── pull customer + vehicle + product + rules + parameters
      ▼  │
CONTEXT ASSEMBLED
      │  ┌─ RULES: Validate ──── classify every field; surface gaps/conflicts
      ▼  │        │
COMPLETENESS CHECK ├── MISSING/INCONSISTENT → back to USER (resolve) ──┐
      │            │                                                    │
      │            └── COMPLETE ◄─────────────────────────────────────┘
      ▼
CONTROLLED SERVICES (deterministic, parallel)
      ├── CALCULATION  (funding rate → margin → lease formula → monthly net/gross)
      ├── ASSESSMENT   (residual value + residual confidence)
      └── SCORING      (MVP risk score → GREEN / YELLOW / RED)
      │
      ▼
OFFER OUTCOMES ──► AGENT: Explain (why this rental / why blocked / why Yellow)
      │
      ▼
SCENARIO GENERATION (24/36/48/60 …) ──► each scenario re-runs CALCULATION + ASSESSMENT + SCORING
      │
      ▼
SCENARIO COMPARISON ──► AGENT: Explain differences ──► USER SELECTS one scenario
      │
      ▼
HUMAN REVIEW ── approve │ return │ correct
      │            │ (if modified → recalc → reassess → revalidate ──┐
      │            └────────────────────────────────────────────────┘
      ▼
FINAL VALIDATION ──► READY  │  REQUIRES_ACTION  │  BLOCKED
      │
      ▼ (READY only)
GENERATE OFFER (Offer JSON → EN/DE template → PDF)
      │
      ▼
AUDIT + HANDOFF BOUNDARY
      │
   ══ MVP ENDS ══   ✗  no contract creation (explicitly out of scope)
```

---

## 3. The vertical dimension: where each fact's truth comes from (SOURCE CLASSES)

This axis is orthogonal to the flow above. Every field flowing through the spine belongs to one
of four source classes, and the Agent **must not mix them**.

```
🟢 OPEN / OFFICIAL         🔵 COMMERCIAL API        🟣 CLIENT-CONTROLLED       🟠 USER / OFFER-SPECIFIC
   (free, authoritative)      (paid; sandbox/trial     (NOT provided by client     (per-offer input)
                               for MVP)                 → we build MVP policy)
   ─────────────────          ─────────────────        ─────────────────          ─────────────────
   KBA / GovData              JATO (catalogue)         funding rate               desired car
   EEA CO₂ dataset            DAT / SilverDAT (RV)     commercial margin          annual mileage
   NHTSA vPIC (VIN)           Autovista (RV)           lease formula              term
   VIES (VAT validate)        mobile.de (market)       allowed terms              budget / target rental
   EU sanctions list          CRIF (KYC/credit)        mileage bands              special payment
   Bundesbank/ECB (rate)      Creditreform (credit)    special-payment rules
   EU TEDB (VAT rate)         SCHUFA (credit)          residual-value policy
   Zoll (vehicle tax)         Creditsafe (credit)      eligibility rules
   Unternehmensregister       OpenSanctions (PEP)      Green/Yellow/Red mapping
   Bundesbank (bank codes)                             Yellow treatment
                                                       approval limits + roles
                                                       exception/override rules
                                                       required documents
                                                       final PDF legal text
```

**Two decisions from Turns 4–5 that reshape this axis for the MVP:**
- 🔵 Commercial APIs are **not a blocker** — for the MVP we replace them with **free/trial/sandbox
  data + a public data *structure*** (esp. EEA CO₂ dataset for the vehicle shape). The value of
  the API research was the *structure*, not the paid access.
- 🟣 Client-controlled rules **will not be provided** — so we author them ourselves as the
  **MVP Reference Policy `DE_PKW_V1`**: deterministic, versioned, explainable, and replaceable
  later by real client policy. This is the single biggest body of work.

So for the MVP the practical source classes collapse to:
**🟢 live free data + 🟠 user input** feed **🟣 our own MVP policy engine**, with **🔵 vendors
mocked/sandboxed** behind adapters that expose a `LIVE / SANDBOX / MOCK` switch.

---

## 4. The three engines (who is allowed to do what)

```
        ┌──────────────────────┬───────────────────────┬────────────────────────┐
        │      AGENT / AI      │    RULES / ENGINE      │        HUMAN           │
        │  reasoning + UI      │   business authority   │  consequential decision│
        ├──────────────────────┼───────────────────────┼────────────────────────┤
        │ Understand           │ Calculate              │ Confirm                │
        │ Assemble             │ Validate               │ Correct                │
        │ Clarify              │ Apply policy / enforce │ Review                 │
        │ Orchestrate*         │ Score (G/Y/R)          │ Decide                 │
        │ Compare (build only) │ Residual / eligibility │ Approve                │
        │ Explain              │                        │ Resolve exceptions     │
        │ Recommend (advisory) │                        │ Override (soft only)   │
        └──────────────────────┴───────────────────────┴────────────────────────┘
        * Orchestration = coordinating the state machine; the workflow engine, not the LLM,
          is the process authority. The Agent proposes the next step; it does not own state.
```

Mapping: `LLM = reasoning/interface` · `Workflow Engine = process authority` ·
`Rule/Calculation Engine = business authority` · `Human = decision authority`.

---

## 5. Two independent status axes (do NOT merge them)

```
WORKFLOW STATUS (where the Offer is in the process)          VALIDATION / READINESS (data health)
─────────────────────────────────────────────────           ────────────────────────────────────
DRAFT → UNDERSTANDING → CONTEXT_REQUIRED →                   per-field status:
CONTEXT_COMPLETE → VALIDATION_REQUIRED →                       ESTABLISHED / CONFIRMED /
READY_FOR_CALCULATION → CALCULATED →                           REQUIRES_CONFIRMATION /
SCENARIOS_AVAILABLE → SCENARIO_SELECTED →                      MISSING / INVALID / INCONSISTENT
PENDING_HUMAN_REVIEW → APPROVED | RETURNED →
FINAL_VALIDATION → READY | REQUIRES_ACTION | BLOCKED →        offer readiness (rollup):
OFFER_GENERATED                                                COMPLETE / MISSING /
                                                               REQUIRES_CONFIRMATION /
                                                               INCONSISTENT / INVALID
```

An Offer has **one** workflow status and **many** field validation states; the readiness rollup is
derived from the field states. Example: `offer_status=CONTEXT_REQUIRED, readiness=REQUIRES_ACTION,
issues=[{field:"customer.address", type:MISSING, blocking:true}]`. Full detail in
[06-state-model.md](06-state-model.md).

---

## 6. The calculation dependency chain (deduplicated)

Every "calculation" mention across the source reduces to this single chain. It is the heart of
the deterministic engine and the main thing to validate before any AI/UI work.

```
🟢 reference_rate (Bundesbank/ECB)
        └─► + term_spread + asset_uncertainty_spread  ──►  FUNDING RATE          [DE_PKW_FUNDING_V1]
                                                                │
🟣 base_margin + risk_adjustment(G/Y/R) + deal_size_adjustment ─┘
                                                                ▼
                                                    CUSTOMER FINANCE RATE (r/yr) [DE_PKW_MARGIN_V1]
                                                                │
🟠 vehicle price, term(n), mileage, special payment             │
🟣 fees, discounts/incentives                                   │
        │                                                       │
        ▼                                                       │
   NetCap = price + financed_fees − discounts − special_payment │
        │                                                       │
🟣 base_term_RV + mileage_adj + age_adj + market_adj  ──► RESIDUAL VALUE + CONFIDENCE [DE_PKW_RV_V1]
        │                                                       │
        ▼                                                       ▼
        └──────────►  PV_RV = RV / (1+r/12)^n   ◄───────────────┘
                                │
                                ▼
        base_lease = (NetCap − PV_RV) × (r/12) / (1 − (1+r/12)^(−n))     [MVP_LEASE_CALC_V1]
                                │   (r==0 → (NetCap − RV)/n)
                                ▼
        monthly_net = base_lease + recurring_service_fees
                                │
🟢 VAT rate (EU TEDB / §12 UStG, DE 19%)
                                ▼
        monthly_gross = monthly_net × (1 + VAT)
```

**Feedback edges (why recalculation exists):** residual confidence LOW → YELLOW → review; risk
band changes the margin's `risk_adjustment` → changes `r` → changes the rental; any human
correction to term/mileage/special payment re-enters at the top. Full detail in
[04-calculation-logic.md](04-calculation-logic.md).

---

## 7. The risk / exception subgraph

```
INPUTS ──► MVP RISK ENGINE (0–100, B2B or B2C weights)
   │             │
   │             ├── hard-block condition present? ──► RED (compliance) ──► BLOCKED (no alternatives)
   │             │
   │             └── else band by score:
   │                    ≥75  ──► GREEN  ──► may proceed
   │                    55–74.99 ──► YELLOW ──► HUMAN REVIEW (never straight to PDF)
   │                    <55 ──► RED (economic) ──► agent may suggest cheaper car / higher
   │                                                special payment / different term / lower
   │                                                mileage → recalc → rescore
   │
   └── every deviation raises a typed EXCEPTION
         {code, severity, blocking, override_allowed, required_role, next_action}
         hard (never override): SANCTIONS_MATCH, KYC_FAILED, fraud, RED-compliance,
                                CALCULATION_FAILED(missing), missing approval, AUTHORIZATION_DENIED,
                                final-validation failure
         soft (reviewable):     PRODUCT_INELIGIBLE(high value), RESIDUAL_LOW_CONFIDENCE,
                                new company, MILEAGE_OUT_OF_RANGE, SPECIAL_PAYMENT_HIGH(20–30%),
                                minor data uncertainty, RISK_YELLOW
```

Every override → an AuditEvent with `{who, when, reason, before, after, rule}`.

---

## 8. Governance & audit as a cross-cutting layer

Audit is not a screen; it is a spine that records **every material state change** with
before/after/actor/timestamp/reason. Events: offer created · requirement interpreted · field
confirmed/corrected · validation failed/resolved · calculation executed · scoring received ·
scenario generated/changed/selected · submitted for review · reviewer returned/approved · final
validation executed · offer generated · any override.

This layer is what makes the field-level provenance (`{value, source, source_type, status,
confidence}`) meaningful: provenance says *where a fact came from*; audit says *when and by whom it
changed*.

---

## 9. What is BUILT vs MOCKED vs SIMULATED (the effort map)

```
BUILD FOR REAL (this is the product)          SIMULATE DETERMINISTICALLY (our MVP policy)
────────────────────────────────────          ───────────────────────────────────────────
Offer Case + state machine                    pricing / lease calculation
completeness / validation engine               residual value + confidence
scenario engine                                 risk scoring (G/Y/R)
human review flow                               eligibility rules
final validation                                business rules / exceptions
audit + provenance                              approval matrix
EN/DE PDF generation                            (all = DE_PKW_V1, versioned, explainable)
agent interaction + orchestration
                                                MOCK / SANDBOX (behind LIVE/SANDBOX/MOCK adapters)
LIVE FREE DATA (real calls, no key)             ────────────────────────────────────────────────
────────────────────────────────────           customer/partner service (fixtures + VIES live)
KBA / GovData vehicle reference                 KYC (CRIF UAT / fixture)
EEA CO₂ vehicle structure                       credit bureau (CRIF/Creditsafe sandbox / mock)
Bundesbank/ECB reference rate                   workflow approval backend
EU TEDB VAT rate                                e-sign / delivery
EU sanctions list / OpenSanctions trial
```

---

## 10. Reading order after this graph

1. [02-domain-entities.md](02-domain-entities.md) — the objects and how they connect (data structures).
2. [03-data-sources-and-integration.md](03-data-sources-and-integration.md) — every integration piece, its I/O, and its MVP treatment.
3. [04-calculation-logic.md](04-calculation-logic.md) — the deterministic engine, step by step, with edge cases.
4. [05-mvp-reference-policy.md](05-mvp-reference-policy.md) — `DE_PKW_V1` as concrete config.
5. [06-state-model.md](06-state-model.md) — workflow status × validation state, transitions, guards.
6. [07-data-model-jsonb-postgres.md](07-data-model-jsonb-postgres.md) — the PostgreSQL + JSONB schema.
7. [08-open-questions-and-verification.md](08-open-questions-and-verification.md) — decided vs open, and what to verify.
