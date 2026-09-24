# 07 — Data Model (PostgreSQL + JSONB)

> Your stated preference: **JSONB-based data modules on PostgreSQL.** The strategy is a **thin
> relational spine** (identity, foreign keys, status, timestamps, things you query/join/index on)
> plus **JSONB payloads** for the rich, evolving, provenance-wrapped structures. This keeps the
> 2–3 week MVP flexible while staying queryable.
>
> This is a proposal to validate against [02](02-domain-entities.md); nothing here is built yet.

---

## 1. What goes relational vs JSONB

**Relational columns (promote to first-class):** primary keys, foreign keys, `workflow_status`,
`readiness`, `customer_type`, `language`, `policy_version`, `created_by`, timestamps, monetary
totals you sort/filter by (e.g. `offer_value_eur`), and the scoring `band`. These drive the inbox,
authority checks, and reporting.

**JSONB payloads (keep flexible):** every `ProvenanceValue`-wrapped field, the full
`CommercialRequirement`, the `CalculationResult` / `AssessmentResult` / `ScoringResult`
`ResultEnvelope`s, scenario parameters, exception lists, and the frozen Offer snapshot for PDF.

**Rule of thumb:** if you filter/join/aggregate on it → column. If you read it whole and it
evolves → JSONB. Promote a JSONB path to a generated column only when a query needs it.

---

## 2. Core tables

```sql
-- ── identity & auth ────────────────────────────────────────────────────────
CREATE TABLE users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         text UNIQUE NOT NULL,
  display_name  text,
  role          text NOT NULL CHECK (role IN
                  ('SALES','REVIEWER','APPROVER','SENIOR_APPROVER','POLICY_ADMIN')),
  authorization jsonb NOT NULL DEFAULT '{}'::jsonb,   -- derived limits per role
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ── reference policy (versioned; the DE_PKW_V1 object) ──────────────────────
CREATE TABLE reference_policies (
  policy_id   text PRIMARY KEY,          -- 'DE_PKW_V1'
  status      text NOT NULL DEFAULT 'ACTIVE',
  config      jsonb NOT NULL,            -- the full master policy config from doc 05
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- ── the aggregate root ──────────────────────────────────────────────────────
CREATE TABLE offers (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reference            text UNIQUE NOT NULL,               -- 'OFF-0001'
  workflow_status      text NOT NULL DEFAULT 'DRAFT',
  readiness            text NOT NULL DEFAULT 'MISSING',
  customer_type        text CHECK (customer_type IN ('B2B','B2C')),
  language             text NOT NULL DEFAULT 'en' CHECK (language IN ('en','de')),
  policy_version       text NOT NULL REFERENCES reference_policies(policy_id),
  created_by           uuid NOT NULL REFERENCES users(id),
  offer_value_eur      numeric(12,2),                      -- promoted for authority/inbox
  scoring_band         text CHECK (scoring_band IN ('GREEN','YELLOW','RED')),
  selected_scenario_id uuid,                               -- FK added after scenarios table
  -- flexible payloads (all ProvenanceValue-wrapped inside):
  commercial_context   jsonb NOT NULL DEFAULT '{}'::jsonb, -- CommercialRequirement
  customer_context     jsonb NOT NULL DEFAULT '{}'::jsonb, -- Customer/Partner (+ kyc/sanctions/credit cache)
  vehicle_context      jsonb NOT NULL DEFAULT '{}'::jsonb, -- Vehicle/Asset
  agent_context        jsonb NOT NULL DEFAULT '{}'::jsonb, -- extraction, explanations, next-action hints
  calculation_result   jsonb,                              -- ResultEnvelope (current)
  assessment_result    jsonb,                              -- ResultEnvelope (current)
  scoring_result       jsonb,                              -- ResultEnvelope (current)
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);

-- ── scenarios (each with its own results) ───────────────────────────────────
CREATE TABLE scenarios (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id           uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  label              text,                                 -- 'A' / '36M' ...
  parameters         jsonb NOT NULL,                       -- {term, mileage, special_payment, ...}
  calculation_result jsonb,                                -- ResultEnvelope
  assessment_result  jsonb,
  scoring_result     jsonb,
  monthly_gross_eur  numeric(12,2),                        -- promoted for the comparison view
  scoring_band       text,
  created_at         timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE offers
  ADD CONSTRAINT fk_selected_scenario
  FOREIGN KEY (selected_scenario_id) REFERENCES scenarios(id);

-- ── validation issues (queryable) ───────────────────────────────────────────
CREATE TABLE validation_issues (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id    uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  field       text NOT NULL,
  type        text NOT NULL,          -- MISSING/INVALID/INCONSISTENT/REQUIRES_CONFIRMATION
  blocking    boolean NOT NULL DEFAULT false,
  detail      jsonb NOT NULL DEFAULT '{}'::jsonb,   -- why / what_must_happen / who_acts
  resolved_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- ── exceptions (typed) ───────────────────────────────────────────────────────
CREATE TABLE exceptions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id        uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  code            text NOT NULL,        -- SANCTIONS_MATCH / RISK_YELLOW / ...
  severity        text NOT NULL,        -- GREEN/YELLOW/RED
  blocking        boolean NOT NULL,
  override_allowed boolean NOT NULL,
  required_role   text,
  next_action     text,
  status          text NOT NULL DEFAULT 'OPEN',   -- OPEN/OVERRIDDEN/RESOLVED
  detail          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- ── reviews (maker-checker) ──────────────────────────────────────────────────
CREATE TABLE reviews (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id    uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  reviewer_id uuid NOT NULL REFERENCES users(id),
  decision    text NOT NULL CHECK (decision IN ('APPROVE','RETURN','CORRECT')),
  comments    text,
  detail      jsonb NOT NULL DEFAULT '{}'::jsonb,   -- exceptions_addressed[], overrides[]
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (reviewer_id IS NOT NULL)
  -- four-eyes (reviewer_id <> offers.created_by) enforced in app + trigger
);

-- ── offer output (frozen snapshot → PDF) ──────────────────────────────────────
CREATE TABLE offer_outputs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id      uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  language      text NOT NULL,
  format        text NOT NULL DEFAULT 'PDF',
  offer_snapshot jsonb NOT NULL,        -- the frozen validated Offer JSON used to render
  file_ref      text,                   -- path/URL to the generated PDF
  generated_at  timestamptz NOT NULL DEFAULT now()
);

-- ── audit (append-only) ───────────────────────────────────────────────────────
CREATE TABLE audit_events (
  id         bigserial PRIMARY KEY,
  offer_id   uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  event      text NOT NULL,             -- SCENARIO_SELECTED / VALIDATION_FAILED / ...
  actor      uuid REFERENCES users(id), -- null when system/agent
  actor_kind text NOT NULL DEFAULT 'USER',  -- USER/AGENT/SYSTEM
  before     jsonb,
  after      jsonb,
  reason     text,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

Customer/vehicle live **inside the Offer** as JSONB for the MVP (`customer_context`,
`vehicle_context`). Promote them to their own tables only if reuse across offers becomes real.

---

## 3. The `ProvenanceValue` shape inside JSONB

Every material field in `commercial_context` / `customer_context` / `vehicle_context` is stored as:
```jsonc
"term_months": { "value": 36, "status": "CONFIRMED", "source": "USER",
                 "source_type": "USER_INPUT", "confidence": null,
                 "retrieved_at": "2026-09-23T10:00:00Z" }
```
And every result column is a `ResultEnvelope` (see [02](02-domain-entities.md) §1.2).

---

## 4. Indexing

```sql
CREATE INDEX idx_offers_status     ON offers (workflow_status);
CREATE INDEX idx_offers_created_by ON offers (created_by);
CREATE INDEX idx_offers_band       ON offers (scoring_band);
CREATE INDEX idx_scenarios_offer   ON scenarios (offer_id);
CREATE INDEX idx_issues_offer_open ON validation_issues (offer_id) WHERE resolved_at IS NULL;
CREATE INDEX idx_exc_offer_open    ON exceptions (offer_id) WHERE status = 'OPEN';
CREATE INDEX idx_audit_offer       ON audit_events (offer_id, created_at);

-- JSONB: GIN for containment queries, or expression indexes for hot paths
CREATE INDEX idx_offers_commercial_gin ON offers USING gin (commercial_context jsonb_path_ops);
-- example promoted path if you query by requested term often:
CREATE INDEX idx_offers_term ON offers (((commercial_context->'term_months'->>'value')::int));
```

---

## 5. Integrity rules enforced in the DB (not only the app)

- **Four-eyes:** trigger rejects a `reviews` row with `decision='APPROVE'` where
  `reviewer_id = offers.created_by`.
- **Authority limit:** trigger/check that an APPROVE respects the role's GREEN/YELLOW €-limit and band.
- **Stale-result guard:** on any change to `commercial_context`/`vehicle_context`/`customer_context`,
  a trigger nulls `calculation_result`/`assessment_result`/`scoring_result` and sets
  `workflow_status` back to the correct re-entry state (mirrors [06](06-state-model.md) §5).
- **Append-only audit:** revoke UPDATE/DELETE on `audit_events`.
- **Policy pin:** `offers.policy_version` is set once at creation and never changed.

---

## 6. Why this holds up for the MVP

- **Flexible:** the evolving, provenance-heavy structures live in JSONB, so schema churn during the
  2–3 weeks doesn't mean migrations for every field.
- **Queryable:** the inbox, authority checks, and comparison view read promoted columns; GIN
  indexes cover ad-hoc JSONB filtering.
- **Auditable:** results carry policy versions + `inputs_digest`; audit is append-only; provenance
  is on every field — together they satisfy the "never silently convert uncertainty" and
  traceability requirements.
- **Replaceable:** bump `reference_policies.policy_id` to introduce real client policy without
  disturbing existing offers (they keep their pinned version).
