export type Band = "GREEN" | "YELLOW" | "RED";
export type Outcome = "READY" | "REQUIRES_ACTION" | "BLOCKED";

export interface ScenarioRow {
  id?: string;
  scenario: string;
  term_months: number;
  annual_mileage_km: number;
  monthly_net_eur: string;
  monthly_gross_eur: string;
  quantity?: number;
  total_monthly_gross_eur?: string;
  residual_pct: string;
  customer_finance_rate_pct?: string;
  band: Band;
  service_maintenance?: boolean;
  service_tyres?: boolean;
  insurance?: boolean;
  fits_budget?: boolean | null;
  budget_headroom_eur?: string | number | null;
}

export interface CalcBreakdown {
  reference_rate_pct: string;
  funding_rate_pct: string;
  commercial_margin_pct: string;
  customer_finance_rate_pct: string;
  netcap_eur: string;
  residual_value_amount_eur: string;
  pv_residual_eur: string;
  base_lease_eur: string;
  service_maintenance_eur?: string;
  service_tyres_eur?: string;
  insurance_eur?: string;
  monthly_net_eur: string;
  vat_pct: string;
  monthly_gross_eur: string;
  quantity?: number;
  total_monthly_net_eur?: string;
  total_monthly_gross_eur?: string;
  contract_mileage_km: number;
  mileage_settlement_per_km_eur: string;
  policies: Record<string, string | null>;
}

export interface ScoringFactor {
  name: string;
  weight: string;
  score: string;
  contribution: string;
}

export interface ScoringDetail {
  score: string;
  band: Band;
  red_kind: string | null;
  hard_blocks: string[];
  factors: ScoringFactor[];
}

export interface ReviewFeedback {
  decision: "approve" | "return";
  comments: string | null;
  reviewer_id: string | null;
}

export interface Proposed {
  make?: string | null;
  model?: string | null;
  vehicle_key?: string | null;
  company_hint?: string | null;
  register_number?: string | null;
  term_months?: number | null;
  annual_mileage_km?: number | null;
  quantity?: number | null;
  special_payment_eur?: number | null;
  service_maintenance?: boolean | null;
  service_tyres?: boolean | null;
  insurance?: boolean | null;
  colour?: string | null;
  objective?: string | null;
  channel?: string | null;
  business_line?: string | null;
  leasing_product?: string | null;
  asset_category?: string | null;
  filters?: Record<string, string>;
  constraints?: { kind: string; value?: number | null; currency?: string | null; basis?: string | null }[];
  ambiguities?: { field: string; reason: string; options?: string[] }[];
  confidence?: number;
}

export interface ExceptionRow {
  code: string;
  severity: string;
  blocking: boolean;
  next_action?: string | null;
  detail?: Record<string, unknown>;
}

export interface OfferSummary {
  reference: string;
  workflow_status: string;
  readiness: string;
  band: Band | null;
  final_outcome: Outcome;
  monthly_net_eur: string | null;
  monthly_gross_eur: string | null;
  scenarios: ScenarioRow[];
  selected_scenario_id: string | null;
  exceptions: ExceptionRow[];
  selected_scenario_label?: string | null;
  proposed?: Proposed | null;
  transcript?: ChatMessage[];
  explanation_pricing?: string | null;
  explanation_scenarios?: string | null;
  last_review?: ReviewFeedback | null;
  calc?: CalcBreakdown | null;
  residual?: { pct: string; amount_eur: string; confidence: string; assumptions: string[] } | null;
  scoring_detail?: ScoringDetail | null;
  provenance?: Record<string, ProvenanceField | null>;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  /** "confirm" = a human decision recorded from the wizard (single source of truth); else a message. */
  kind?: "message" | "confirm" | "action";
  title?: string;   // confirm: the step label (e.g. "Customer")
  detail?: string;  // confirm: the value that was confirmed
  edited?: boolean; // confirm: the human changed the agent's proposal
}

export type StepKey = "channel" | "partner" | "product" | "asset" | "commercial";

export interface RefOption {
  key: string;
  name_en?: string;
  name_de?: string;
  label?: string;
  description_en?: string;
  status?: string;
  business_line?: string;
  asset_category?: string;
}
export interface PartnerCandidate { register_number: string; legal_name: string; legal_form?: string; label: string; }
export interface Ambiguity { field: string; reason: string; options?: string[]; }
export interface ConstraintRow { kind: string; value?: number | null; currency?: string | null; basis?: string | null; note?: string | null; }

export type FieldStatus = "unset" | "proposed" | "confirmed" | "stale";
export interface FieldRow {
  field: string;
  label: string;
  status: FieldStatus;
  value: string | number | boolean | null;
  option_key?: string | null;
  required: boolean;
}

export interface Interrupt {
  type: "confirm_step" | "human_review" | "workspace_gate" | "agent_turn";
  reference: string;
  proposed?: Proposed;
  transcript?: ChatMessage[];
  missing?: string[];
  // agent_turn (state-driven intake)
  field_state?: FieldRow[];
  pending?: string[];
  focus?: string | null;
  // confirm_step
  step?: StepKey;
  title?: string;
  prompt?: string;
  options?: RefOption[];                 // channel
  business_lines?: RefOption[];
  products?: RefOption[];
  candidates?: PartnerCandidate[];       // partner dedupe / directory
  partner_kind?: string;                 // business_partner | offer_partner
  is_search?: boolean;                   // candidates are search matches (vs the full directory)
  catalogue?: CatalogueVehicle[];        // asset
  attribute_schema?: { key: string; label_en: string; type: string; filterable?: boolean }[];
  filters?: Record<string, string>;
  value?: unknown;
  selected?: string | null;
  selected_label?: string | null;
  colour?: string | null;
  constraints?: ConstraintRow[];
  ambiguities?: Ambiguity[];
  // human_review
  outcome?: Outcome;
  can_generate?: boolean;
  exceptions?: ExceptionRow[];
  selected_scenario_label?: string | null;
  // workspace_gate
  scenarios?: ScenarioRow[];
  generated?: boolean;
}

export interface ProvenanceField {
  value: string | number | null;
  status: string;
  info_state?: "established" | "confirmed" | "requires_confirmation" | "needs_action";
  source: string | null;
  confidence: number | null;
}

export interface CatalogueVehicle {
  key: string;
  make: string;
  commercial_name: string;
  model_family?: string;
  variant?: string;
  body_type?: string;
  fuel_type?: string;
  transmission?: string;
  engine_capacity_cc?: number;
  engine_power_kw?: number;
  engine_power_hp?: number;
  seats?: number;
  wltp_co2_g_km?: number;
  co2_class?: string;
  consumption_l_100km?: number;
  consumption_kwh_100km?: number;
  colours?: string[];
  list_price_net: string;
  label: string;
}

export interface CatalogueCustomer {
  register_number: string;
  legal_name: string;
  legal_form?: string;
  label: string;
}

export interface Snapshot {
  thread_id: string;
  next: string[];
  status: "awaiting_input" | "complete";
  step?: StepKey | null;
  field_state?: FieldRow[] | null;
  interrupts: Interrupt[];
  offer: OfferSummary | null;
}

export interface BudgetFitRow {
  vehicle_key: string;
  priced: boolean;
  band?: Band | null;
  monthly_gross_eur?: string | number;
  total_monthly_gross_eur?: string | number;
  contract_total_eur?: string | number;
  budget_metric_eur?: string | number;
  budget_headroom_eur?: string | number;
  fits_budget?: boolean;
}

export interface BudgetFit {
  budget: { value: string; basis: string; currency: string | null } | null;
  filters: Record<string, string>;
  candidates: BudgetFitRow[];
}

export interface ReferenceData {
  version: string;
  channels: RefOption[];
  business_lines: RefOption[];
  leasing_products: RefOption[];
  asset_categories: { key: string; name_en: string; status: string }[];
}

export interface OfferListRow {
  id: string;
  reference: string;
  workflow_status: string;
  readiness: string;
  band: Band | null;
  customer: string | null;
  vehicle: string | null;
  quantity: number;
  fleet_monthly_eur: string | null;
}

export interface AuditAllRow {
  event: string;
  actor_kind: string;
  reason: string | null;
  at: string;
  offer_id: string;
  reference: string;
  customer: string | null;
}

export interface FeedEvent {
  kind: "node" | "await" | "snapshot" | "done" | "error";
  node?: string;
  label?: string;
  band?: Band;
  score?: string;
  detail?: string;
  snapshot?: Snapshot;
  detailText?: string;
}
