-- Agentic Offer Creation MVP — PostgreSQL schema (docs/07)
-- Thin relational spine + JSONB payloads. Requires PostgreSQL 13+ (gen_random_uuid via pgcrypto).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── identity & auth ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         text UNIQUE NOT NULL,
  display_name  text,
  role          text NOT NULL CHECK (role IN
                  ('SALES','REVIEWER','APPROVER','SENIOR_APPROVER','POLICY_ADMIN')),
  authorization_set jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ── versioned reference policy (DE_PKW_V1 object) ────────────────────────────
CREATE TABLE IF NOT EXISTS reference_policies (
  policy_id  text PRIMARY KEY,
  status     text NOT NULL DEFAULT 'ACTIVE',
  config     jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ── aggregate root ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS offers (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reference            text UNIQUE NOT NULL,
  workflow_status      text NOT NULL DEFAULT 'DRAFT',
  readiness            text NOT NULL DEFAULT 'MISSING',
  customer_type        text CHECK (customer_type IN ('B2B','B2C')),
  language             text NOT NULL DEFAULT 'en' CHECK (language IN ('en','de')),
  policy_version       text NOT NULL REFERENCES reference_policies(policy_id),
  created_by           uuid NOT NULL REFERENCES users(id),
  offer_value_eur      numeric(12,2),
  scoring_band         text CHECK (scoring_band IN ('GREEN','YELLOW','RED')),
  selected_scenario_id uuid,
  commercial_context   jsonb NOT NULL DEFAULT '{}'::jsonb,  -- CommercialRequirement (ProvenanceValues)
  customer_context     jsonb NOT NULL DEFAULT '{}'::jsonb,  -- Customer + kyc/sanctions/credit cache
  vehicle_context      jsonb NOT NULL DEFAULT '{}'::jsonb,  -- Vehicle
  agent_context        jsonb NOT NULL DEFAULT '{}'::jsonb,  -- extraction/explanations/next-action
  calculation_result   jsonb,                               -- ResultEnvelope (lease calc)
  assessment_result    jsonb,                               -- ResultEnvelope (residual value, §3.8)
  asset_assessment_result jsonb,                            -- ResultEnvelope (asset assessment, §3.7)
  scoring_result       jsonb,                               -- ResultEnvelope
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);

-- ── scenarios (each with its own results) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS scenarios (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id           uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  label              text,
  parameters         jsonb NOT NULL,
  calculation_result jsonb,
  assessment_result  jsonb,
  scoring_result     jsonb,
  monthly_gross_eur  numeric(12,2),
  scoring_band       text,
  created_at         timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE offers DROP CONSTRAINT IF EXISTS fk_selected_scenario;
ALTER TABLE offers ADD CONSTRAINT fk_selected_scenario
  FOREIGN KEY (selected_scenario_id) REFERENCES scenarios(id);

-- ── validation issues ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS validation_issues (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id    uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  field       text NOT NULL,
  type        text NOT NULL,
  blocking    boolean NOT NULL DEFAULT false,
  detail      jsonb NOT NULL DEFAULT '{}'::jsonb,
  resolved_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- ── typed exceptions ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exceptions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id         uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  code             text NOT NULL,
  severity         text NOT NULL,
  blocking         boolean NOT NULL,
  override_allowed boolean NOT NULL,
  required_role    text,
  next_action      text,
  status           text NOT NULL DEFAULT 'OPEN',   -- OPEN/OVERRIDDEN/RESOLVED
  detail           jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at       timestamptz NOT NULL DEFAULT now()
);

-- ── reviews (maker-checker) ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reviews (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id    uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  reviewer_id uuid NOT NULL REFERENCES users(id),
  decision    text NOT NULL CHECK (decision IN ('APPROVE','RETURN','CORRECT')),
  comments    text,
  detail      jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- ── offer output (frozen snapshot -> PDF) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS offer_outputs (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id       uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  language       text NOT NULL,
  format         text NOT NULL DEFAULT 'PDF',
  offer_snapshot jsonb NOT NULL,
  file_ref       text,
  generated_at   timestamptz NOT NULL DEFAULT now()
);

-- ── audit (append-only) ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_events (
  id         bigserial PRIMARY KEY,
  offer_id   uuid NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  event      text NOT NULL,
  actor      uuid REFERENCES users(id),
  actor_kind text NOT NULL DEFAULT 'USER',
  before     jsonb,
  after      jsonb,
  reason     text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ── indexes ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_offers_status     ON offers (workflow_status);
CREATE INDEX IF NOT EXISTS idx_offers_created_by ON offers (created_by);
CREATE INDEX IF NOT EXISTS idx_offers_band       ON offers (scoring_band);
CREATE INDEX IF NOT EXISTS idx_scenarios_offer   ON scenarios (offer_id);
CREATE INDEX IF NOT EXISTS idx_issues_offer_open ON validation_issues (offer_id) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_exc_offer_open    ON exceptions (offer_id) WHERE status = 'OPEN';
CREATE INDEX IF NOT EXISTS idx_audit_offer       ON audit_events (offer_id, created_at);
CREATE INDEX IF NOT EXISTS idx_offers_commercial_gin ON offers USING gin (commercial_context jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_offers_term
  ON offers (((commercial_context->'term_months'->>'value')::int));
