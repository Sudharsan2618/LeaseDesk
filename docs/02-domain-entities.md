# 02 — Domain Entities & Interconnections

> This is the **data-structure layer**: the objects, their fields, their relationships, and the
> shared building blocks that appear everywhere. This is what to validate *before* any
> LangGraph/AI/UI work. Storage mapping (PostgreSQL + JSONB) is in
> [07-data-model-jsonb-postgres.md](07-data-model-jsonb-postgres.md); this doc is
> storage-agnostic and focuses on *meaning and connections*.

---

## 1. The two building blocks that appear on almost every field

Everything else is built out of these two envelopes. Get them right first.

### 1.1 `ProvenanceValue<T>` — every material field is wrapped in this

The source's most important rule ("never silently convert uncertainty into business truth")
becomes a single reusable shape:

```jsonc
{
  "value": 36,                       // the actual value (any type T), or null when MISSING
  "status": "CONFIRMED",             // ESTABLISHED | CONFIRMED | REQUIRES_CONFIRMATION | MISSING | INVALID | INCONSISTENT | INFERRED
  "source": "USER",                  // USER | AGENT | KBA | EEA | BUNDESBANK | EU_TEDB | VIES | CRIF | DE_PKW_V1 | ...
  "source_type": "USER_INPUT",       // USER_INPUT | AGENT_INFERENCE | OPEN_OFFICIAL | EXTERNAL_PROVIDER | CONTROLLED_REFERENCE_DATA
  "confidence": 0.91,                // only meaningful when source=AGENT (INFERRED); else null
  "retrieved_at": "2026-09-23T10:00:00Z"
}
```

Status vocabulary (unified from the two lists in the source):
- `ESTABLISHED` — came from an authoritative source (open/official, provider, or reference data).
- `CONFIRMED` — a human explicitly confirmed it.
- `REQUIRES_CONFIRMATION` — present but needs a human to confirm (e.g. agent-inferred, or a proposed default).
- `INFERRED` — the agent proposed it from the NL request (always carries `confidence`, always also needs confirmation).
- `MISSING` — no value yet.
- `INVALID` — present but fails a format/domain check (e.g. VAT ID malformed).
- `INCONSISTENT` — conflicts with another field (e.g. term implies age-at-end > 8y).

> **Rule:** the calculation/scoring/eligibility engines may only consume fields whose status is
> `ESTABLISHED` or `CONFIRMED`. Anything else must first be resolved. This is enforced by the
> completeness check, not by the LLM.

### 1.2 `ResultEnvelope<T>` — every engine output carries policy provenance

Every deterministic result (calculation, residual, scoring) is wrapped so the Agent can *explain*
it and the audit can *trace* it, without anyone being able to alter it:

```jsonc
{
  "value": { /* the CalculationResult / AssessmentResult / ScoringResult payload */ },
  "engine": "MVP_LEASE_CALC_V1",
  "policies": {
    "funding_policy": "DE_PKW_FUNDING_V1",
    "margin_policy": "DE_PKW_MARGIN_V1",
    "residual_policy": "DE_PKW_RV_V1",
    "risk_policy": "DE_PKW_RISK_V1",
    "tax_source": "EU_TEDB",
    "reference_rate_source": "BUNDESBANK"
  },
  "inputs_digest": "sha256:…",       // hash of the exact inputs → makes results reproducible/cacheable
  "assumptions": ["new_vehicle", "36_month_term", "20000_km_annual"],
  "computed_at": "2026-09-23T10:05:00Z"
}
```

---

## 2. Entity catalogue

Legend for source class (see [01-knowledge-graph.md](01-knowledge-graph.md) §3):
🟢 open/official · 🔵 commercial (mock/sandbox in MVP) · 🟣 client-controlled (our MVP policy) · 🟠 user input · ⚙️ system-generated.

### 2.1 `User` ⚙️ / 🟠
| Field | Type | Notes |
|---|---|---|
| id | uuid | |
| email | string | your session identity for authorship/attribution |
| display_name | string | |
| role | enum | `SALES` · `REVIEWER` · `APPROVER` · `SENIOR_APPROVER` · `POLICY_ADMIN` |
| authorization_set | object | derived limits per role (see [05](05-mvp-reference-policy.md) §approval) |

Relationships: a `User` **creates** many `Offer`s; **acts on** `Review`s; is the `actor` on `AuditEvent`s.
Rule: **agent effective permissions = min(agent policy, current user's permissions)**.

### 2.2 `Offer` (aggregate root) ⚙️
| Field | Type | Notes |
|---|---|---|
| id | uuid | |
| reference | string | human code e.g. `OFF-0001` |
| workflow_status | enum | one value from the workflow axis ([06](06-state-model.md)) |
| readiness | enum | `COMPLETE` / `MISSING` / `REQUIRES_CONFIRMATION` / `INCONSISTENT` / `INVALID` (rollup) |
| customer_type | enum | `B2B` · `B2C` (drives required data, KYC, risk weights, legal controls) |
| language | enum | `en` · `de` |
| created_by | uuid → User | |
| policy_version | string | `DE_PKW_V1` — pins which reference policy this Offer used |
| created_at / updated_at | timestamp | |

Holds (composition — each belongs to exactly one Offer): CommercialRequirement (1),
CustomerRef (1), VehicleRef (1), ProductRef (1), ValidationIssue[], CalculationResult (1, current),
AssessmentResult (1, current), ScoringResult (1, current), Scenario[], SelectedScenario (0..1),
Exception[], Review[], OfferOutput (0..1), AuditEvent[].

### 2.3 `Customer` / `Partner` 🔵 (mock/sandbox) + 🟢 (VIES/sanctions live)
Split by `customer_type`.

**B2B fields:** legal_company_name, registered_address, register_number, legal_form,
authorized_representatives[], vat_id (🟢 VIES-validated), beneficial_owners[] (🔵 UBO/KYC),
bank_info, creditworthiness (🔵), kyc_status, sanctions_result (🟢), pep_result (🔵).
**B2C fields:** full_name, date_of_birth (age≥18 check), address, identity_verification,
bank_info, credit_info (🔵), income (only when risk policy requires), sanctions_result (🟢).

Each field is a `ProvenanceValue`. Relationships: referenced by one Offer; feeds SCORING and
ELIGIBILITY and the KYC/sanctions/credit dataflow ([03](03-data-sources-and-integration.md) §KYC).

### 2.4 `Vehicle` / `Asset` 🟢 (structure) + 🔵 (RV/price in production)
Structure comes from the **EEA CO₂ dataset** (the public shape) + **KBA** (HSN/TSN reference):

| Field | Type | Source | Notes |
|---|---|---|---|
| make | string | 🟢 EEA/KBA | |
| commercial_name | string | 🟢 EEA | e.g. "X1" |
| type / variant / version | string | 🟢 EEA | type-approval identity |
| type_approval_number | string | 🟢 EEA | |
| hsn / tsn | string | 🟢 KBA | German reference |
| vehicle_category | enum | 🟢 EEA | must be `M1` for eligibility |
| fuel_type | enum | 🟢 EEA | |
| engine_capacity_cc / engine_power_kw | int | 🟢 EEA | |
| mass_kg | int | 🟢 EEA | |
| wltp_co2_g_km | int | 🟢 EEA | (vehicle-tax input if used) |
| electric_consumption_wh_km | int? | 🟢 EEA | |
| vin | string? | 🟢 NHTSA (used only) | **new → optional; used → required** |
| list_price_net / list_price_gross | money | 🔵/seed | seeded/mocked where no public price |
| acquisition_price | money | 🟠/🔵 | actual price used in NetCap |
| residual_value | ResultEnvelope | ⚙️ DE_PKW_RV_V1 | computed, not stored as a fact from a provider |
| registration_date | date? | used only | |
| condition / mileage_now | mixed | used only | |

Relationships: referenced by one Offer; feeds CALCULATION (price), ASSESSMENT (residual), and
ELIGIBILITY (category/price/age).

### 2.5 `LeasingProduct` 🟣 (our MVP policy)
For the MVP there is effectively **one product**: German passenger-car **kilometre leasing**
(`KILOMETER_LEASING`). Fields are *policy*, not per-offer data: allowed terms, mileage bands,
special-payment rules, fee schedule, funding policy ref, margin policy ref, residual policy ref,
eligibility ruleset, scenario constraints. All resolve to `DE_PKW_V1` — see
[05-mvp-reference-policy.md](05-mvp-reference-policy.md). (Residual-value leasing is a possible
second product only if time permits.)

### 2.6 `CommercialRequirement` 🟠 (the per-offer input)
The user's actual ask, each field a `ProvenanceValue`:
| Field | Type | Notes |
|---|---|---|
| term_months | int | validated against allowed_terms(vehicle, mileage, rv_confidence) |
| annual_mileage_km | int | validated against mileage bands |
| special_payment | money or pct | validated against special-payment rules |
| target_monthly_rental | money? | the objective ("as low as possible") — advisory, drives scenario suggestions |
| budget_total? | money? | optional |
| objective | enum? | e.g. `MINIMIZE_MONTHLY` |

### 2.7 Results bundle (all ⚙️, wrapped in `ResultEnvelope`)
- **`CalculationResult`** — funding_rate, customer_finance_rate, netcap, pv_residual, base_lease,
  monthly_net, monthly_gross, vat_rate, fee_breakdown, mileage_settlement_terms, rounding.
- **`AssessmentResult`** — residual_value_pct, residual_value_amount, residual_confidence
  (`HIGH`/`MEDIUM`/`LOW`), assumptions[].
- **`ScoringResult`** — mvp_risk_score (0–100), band (`GREEN`/`YELLOW`/`RED`), red_kind
  (`ECONOMIC`/`COMPLIANCE`/null), factor_breakdown{}, hard_blocks[].

### 2.8 `Scenario` ⚙️ + 🟠 (user may tweak the varied parameter)
A scenario is a *variation* of the CommercialRequirement (typically term, sometimes mileage /
special payment). Each scenario **owns its own** CalculationResult + AssessmentResult +
ScoringResult (recomputed for its parameters). `SelectedScenario` = the one the user chose; it is
what final validation and the PDF use.

```
Offer ──1..*── Scenario ──1── CalculationResult
                       ├──1── AssessmentResult
                       └──1── ScoringResult
Offer ──0..1── SelectedScenario (→ one Scenario)
```

### 2.9 Governance bundle
- **`ValidationIssue`** ⚙️ — `{field, type(MISSING/INVALID/INCONSISTENT/REQUIRES_CONFIRMATION), why, what_must_happen, who_acts, blocking:bool}`.
- **`Exception`** ⚙️/🟣 — typed: `{code, severity(GREEN/YELLOW/RED), blocking, override_allowed, required_role, next_action}`. Codes listed in [01](01-knowledge-graph.md) §7 and [05](05-mvp-reference-policy.md).
- **`Review`** ⚙️/🟠 — `{reviewer_id, decision(APPROVE/RETURN/CORRECT), comments, exceptions_addressed[], created_at}`; enforces maker-checker (creator ≠ approver) and authority limits.
- **`OfferOutput`** ⚙️ — `{language, format:"PDF", file_ref, offer_json_snapshot, generated_at}`; built from a frozen snapshot of the validated Offer JSON.
- **`AuditEvent`** ⚙️ — `{event, offer_id, actor, timestamp, before, after, reason}`; append-only.

---

## 3. The full relationship map (ER-style, text)

```
User 1───* Offer
User 1───* AuditEvent (actor)
User 1───* Review (reviewer)

Offer 1───1 CommercialRequirement
Offer 1───1 Customer            (Customer 1───* Offer allowed later; MVP: 1─1 is fine)
Offer 1───1 Vehicle
Offer 1───1 LeasingProduct(ref → DE_PKW_V1 policy)
Offer 1───1 CalculationResult   (current/top-level)
Offer 1───1 AssessmentResult    (current/top-level)
Offer 1───1 ScoringResult       (current/top-level)
Offer 1───* Scenario
Offer 0───1 SelectedScenario ──→ Scenario
Offer 1───* ValidationIssue
Offer 1───* Exception
Offer 1───* Review
Offer 0───1 OfferOutput
Offer 1───* AuditEvent

Scenario 1───1 CalculationResult
Scenario 1───1 AssessmentResult
Scenario 1───1 ScoringResult

Customer *───1 SanctionsResult / KycResult / CreditResult  (adapter outputs, cached on Customer)
Vehicle  uses  DE_PKW_RV_V1 → AssessmentResult
CalculationResult uses DE_PKW_FUNDING_V1 + DE_PKW_MARGIN_V1 + DE_PKW_RV_V1 + VAT + reference_rate
ScoringResult uses DE_PKW_RISK_V1
```

---

## 4. Data-flow contracts to lock down first (the "check every I/O" list)

Before building anything, pin down these input→output contracts. Each is detailed in
[03](03-data-sources-and-integration.md) (external) or [04](04-calculation-logic.md) (engines).

| # | Producer | Input | Output |
|---|---|---|---|
| 1 | Agent: Understand | NL string | partial CommercialRequirement + refs, all `INFERRED` w/ confidence |
| 2 | Vehicle search (KBA/EEA) | make/model query | Vehicle candidates (structure), each field `ESTABLISHED` |
| 3 | VIES | vat_id | `{valid:bool, name?, address?}` |
| 4 | Sanctions (EU/OpenSanctions) | name(s) | `{match:bool, hits[]}` |
| 5 | KYC adapter | customer ref | IdentityResult |
| 6 | Credit adapter | customer ref + exposure | `{score, default_probability, recommended_limit}` (raw bureau) |
| 7 | Reference rate (Bundesbank) | as-of date, series | reference_rate (%) |
| 8 | VAT (EU TEDB) | country, date | vat_rate (%) |
| 9 | Funding policy | reference_rate, term, rv_confidence | funding_rate |
| 10 | Margin policy | funding_rate, risk band, deal size | customer_finance_rate |
| 11 | Residual policy | vehicle, term, mileage, age | AssessmentResult |
| 12 | Lease calculator | NetCap inputs, r, n, RV, fees, VAT | CalculationResult |
| 13 | Risk engine | customer + credit + exposure + affordability | ScoringResult (G/Y/R) |
| 14 | Eligibility | vehicle + customer + offer | pass / ValidationIssue[] / Exception[] |
| 15 | PDF generator | validated Offer JSON + language | PDF file |

**Design principle for every producer:** it returns a `ProvenanceValue` (data lookups) or a
`ResultEnvelope` (engine computations) — never a bare number — and it declares its `source` /
`source_type` so the Agent can explain and the audit can trace.
