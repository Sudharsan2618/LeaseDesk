# 00 — Source of Truth (Original Chat History)

> **Purpose:** This file is the *frozen, immutable record* of the research conversation that
> gave rise to this project. Nothing here is edited for correctness. All other documents in
> this repo are **derived** from this file. If a derived doc ever conflicts with a business
> decision, this file is the reference for "what was originally said and why".
>
> **Captured:** 2026-09-23
> **Conversation participants:** Client-side developer (you) ↔ research assistant (prior chat)
> **Underlying artifact discussed:** a 95-page "Agentic Offer Creation MVP Requirements" PDF (not included; only the assistant's reading of it is captured here).

---

## Turn 1 — Assistant: Reading of the 95-page requirements PDF

**Central thesis:** This is **not a chatbot project** and **not a replacement of the leasing
platform**. It is a 2–3 week proof of a *controlled, agent-assisted Offer Creation journey*.

**One-sentence summary of the whole document:**
Build a **stateful Agentic Offer Creation Workbench** where a sales/internal user describes a
leasing requirement, the system understands and structures it, assembles
customer/product/asset context, identifies missing information, invokes controlled
calculations/scoring/assessment, creates and compares scenarios, explains outcomes, routes
through human review, validates, and finally generates a **decision-ready Offer**.

**The agent helps with:** Understand → Assemble → Validate → Orchestrate → Compare → Explain.
**But the governing rule:** AI assists → deterministic rules decide → humans govern.
Calculations, business rules, financial decisions and credit decisions must **not** be
delegated to the LLM.

### Mental model
Not `User → ChatGPT → Answer`.
Instead: `User → Offer Case → Agent/Orchestrator → Controlled Services → Human Decision → Validated Offer`.

The **Offer Case** is the heart of the application. Everything belongs to one Offer:
User/Sales Channel · Customer/Partner · Business Line · Leasing Product · Asset/Object ·
Commercial Requirements · Offer Parameters · Completeness/Validation · Calculation ·
Asset Assessment · Credit/Scoring · Scenarios (A/B/C) · Exceptions · Human Review ·
Final Validation · Generated Offer · Audit/Activity History.

### The 6 agent capabilities (the 95 pages reduce to these)
1. **Understand** — turn NL request into structured data. May interpret; may NOT decide eligibility. Never invent a missing material field.
2. **Assemble** — auto-pull customer + partner + product + asset + offer parameters + rules + existing offer info, instead of manual multi-system search.
3. **Validate** — classify every important field as `ESTABLISHED / CONFIRMED / REQUIRES_CONFIRMATION / MISSING / INVALID / INCONSISTENT`, and for each issue give: Problem · Why it matters · What must happen · Who acts · Whether progression is blocked. **Never use the LLM to invent a missing material field.**
4. **Orchestrate** — the genuinely *agentic* part: understand current Offer state, determine the next activity. It is coordinating an Offer state machine, not returning chat messages.
5. **Compare** — build 2–3 scenarios (differing term/etc.), but the *numbers come from the deterministic calculation service*, not the LLM.
6. **Explain** — explain the rental, blockers, differences, scoring, missing info, next steps — without becoming a decision override.

### Three engines inside the MVP
- **AGENT/AI** → understand, assemble, clarify, orchestrate, compare, explain, recommend (advisory).
- **RULES/ENGINE** → calculate, validate, apply policy, enforce, score.
- **HUMAN** → review, correct, approve, resolve exceptions.

Mental model: `LLM = reasoning/interface assistant`, `Workflow Engine = process authority`,
`Rule/Calculation Engine = business authority`, `Human = consequential decision authority`.
Do not place all three inside LangGraph/LLM prompts.

### Build vs Mock vs Simulate
- **BUILD (real):** Offer Workbench UI, Offer Case/State, Agent interaction, orchestration, completeness/validation flow, scenario experience, human review, final validation, offer generation, audit/traceability.
- **MOCK / controlled data:** customer/partner service, product catalogue, asset catalogue, user authorization, offer reference data, business rules/offer parameters, credit response, workflow approval backend, e-sign/delivery.
- **SIMULATE DETERMINISTICALLY:** pricing, asset assessment, credit/risk, validation, business rules. "Simulated" must **not** mean `random.choice([...])`; it must mean a predictable rule (`if amount <= 50000 and rating == "A": GREEN ...`) so demos and tests are repeatable.

### Canonical Offer state model
`DRAFT → UNDERSTANDING → CONTEXT_REQUIRED → CONTEXT_COMPLETE → VALIDATION_REQUIRED →
READY_FOR_CALCULATION → CALCULATED → SCENARIOS_AVAILABLE → SCENARIO_SELECTED →
PENDING_HUMAN_REVIEW → APPROVED/RETURNED → FINAL_VALIDATION → READY/REQUIRES_ACTION/BLOCKED →
OFFER_GENERATED`.

Keep **workflow status** separate from **validation state**
(`COMPLETE / MISSING / REQUIRES_CONFIRMATION / INCONSISTENT / INVALID`). Do not mix the two.

### Main domain entities
User(Role, AuthorizationSet); Offer(Customer/Partner, BusinessLine, Product, Asset,
CommercialRequirement, OfferParameter[], ValidationIssue[], CalculationResult,
AssessmentResult, ScoringResult, Scenario[]→CalculationResult, SelectedScenario,
Exception[], Review[], OfferOutput, AuditEvent[]).

### Suggested component model (assistant's translation, not prescribed by the PDF)
Frontend (Offer Workbench) → FastAPI (Offer Case API) → {Agent Layer, Workflow/State Machine,
Offer Service} → {Reference Data/RAG, Rules/Validation, Audit} → {Customer/Product/Asset mocks,
Calculation Engine, Scoring mock} → Offer Generator (PDF/JSON).
Natural stack fit: **FastAPI + PostgreSQL + LangGraph + React/Next.js**.

### What LangGraph should/shouldn't control
LangGraph nodes: interpret_requirement → retrieve_offer_context → check_completeness
(missing→request_information→user_input→re-check | complete) → apply_business_rules →
request_calculation → request_asset_assessment → request_scoring → generate_scenarios →
explain_results → scenario_selection → human_review (return→correction→reassess | approve) →
final_validation → generate_offer → END.
A node calls `calculation_service.calculate(...)`, **never** `llm.invoke("calculate lease price")`.

### UI: ~7 screens (one Workbench, many views of one Offer Case)
1. Offer Inbox · 2. New Offer/Intake · 3. Customer Context · 4. Asset+Product ·
5. Pricing+Scenarios · 6. Credit/Approval · 7. Offer Review+Output · 8. Activity/Audit (optional).
Every screen answers: Where am I? What do we know? What needs attention? What can I do next?

### The executable happy path (21 steps)
1 start Offer · 2 type requirement · 3 AI extracts customer/product/asset/amount/term/intent ·
4 user confirms/corrects · 5 system loads customer/product/asset/rules · 6 validation detects
gaps · 7 user resolves gaps · 8 completeness reached · 9 deterministic services return
calculation + asset assessment + scoring · 10 agent explains · 11 generate 2–3 scenarios ·
12 calc engine calculates each · 13 UI compares · 14 user selects one · 15 reviewer reviews
context/exceptions/calc/scoring/scenario · 16 approve/return/correct · 17 if modified →
recalc/reassess/revalidate · 18 final validation → READY/REQUIRES_ACTION/BLOCKED · 19 READY →
generate Offer · 20 store audit trail · 21 stop. **DO NOT CREATE CONTRACT.**

### The most important business rule
> **Never silently convert uncertainty into business truth.**
Every field carries origin/provenance: `{value, status, source, confidence?}` where status ∈
`CONFIRMED / INFERRED / MISSING` and source ∈ `USER / AGENT / <service> / null`.

### Audit (architecturally mandatory even if the screen is optional)
Record events with before/after/actor/timestamp/reason: Offer created, requirement interpreted,
field confirmed/corrected, validation failed/resolved, calculation executed, scoring received,
scenario generated/changed/selected, submitted for review, reviewer returned/approved, final
validation executed, offer generated.

### Documentation inconsistencies flagged
- Summary says "58 functional requirements" but IDs extend to **FR-63** (authorization/language likely added without updating the count).
- **AC-16** and **AC-17** appear to state the same authorization acceptance requirement — treat AC-17 as a probable duplicate until confirmed.

### Section 16 — Major requirement gaps to clarify with the client (18 items)
1 representative MVP leasing scenario (which Business Line/Product/Asset) · 2 mandatory offer
parameters · 3 deterministic calculation formula · 4 scoring behaviour (Green/Yellow/Red
conditions) · 5 Yellow handling (must be validated, not assumed) · 6 which asset flow · 7
scenario controls (term/deposit/mileage/residual/asset/product) · 8 which rules block an Offer ·
9 human roles (Sales/Reviewer/Approver — what each can do) · 10 approval authority · 11 which two
languages · 12 generated Offer format · 13 mock customer fields · 14 audit expectations · 15
negative flows (3–5 exceptions) · 16 doc generation (representative vs reproduce template) · 17
authentication (real vs mocked personas) · 18 any real enterprise API expected in 2–3 weeks.

### Six requirement packages to ask the client for
A. one representative Offer example (done manually today) · B. master/reference data
(products, asset categories, offer parameters, business lines) · C. business rules (mandatory
fields, eligibility, blocking, scenario constraints) · D. deterministic logic (pricing,
assessment, scoring) · E. user/approval model (roles, permissions, review rules) · F. output
(expected final Offer template).

### Minimum data model to begin with (consolidate via JSONB in a 2–3 week MVP)
users, roles, offers, offer_fields, customers, products, assets, offer_rules, offer_parameters,
offer_validations, calculations, assessment_results, scoring_results, scenarios,
scenario_parameters, scenario_results, reviews, exceptions, offer_outputs, audit_events.
Example: `offers(id, reference, status, readiness_status, created_by, customer_id, product_id,
asset_id, commercial_context JSONB, agent_context JSONB, selected_scenario_id, created_at,
updated_at)`.

### Suggested implementation order (do NOT start with the LLM)
Phase 1 Offer engine (works with no AI) → Phase 2 Workbench → Phase 3 Agent → Phase 4
Orchestration → Phase 5 Negative flows → Phase 6 Offer generation + demo hardening.

### First phase = requirement crystallization, not coding
Turn the 95 pages into four artifacts: (1) Canonical Requirement Document (~10–15 pages),
(2) Requirement Clarification/Gap Sheet, (3) Technical Design, (4) Development Backlog.

---

## Turn 2 — User: Scope decisions + instruction to research public data/APIs

- Section 16's gaps are things to identify. **Start with car leasing.**
- For offer parameters, calculation, partner, assets, scoring behaviour, controls, rules and all
  required data: **never assume from trained data.** First check whether any **public
  data / API provider** supplies the required information; validate each one-by-one for
  usefulness; do the **end-to-end research** and report findings.
- **Languages: English + German. Output: PDF.**

---

## Turn 3 — Assistant: End-to-end public/commercial data & API research (jurisdiction = Germany, PKW)

**Clarification:** "Section 16" referred to section 16 of the *previous summary* (the unresolved
requirements list), not the PDF. Three items now fixed for the MVP: **Asset = passenger cars /
PKW**, **Languages = EN + DE**, **Output = PDF**.

**Key result:** A large portion of *supporting data* can come from external
authoritative/commercial sources, **but the core leasing calculation, eligibility rules,
approval thresholds and pricing policy cannot safely come from public data** — those are
client-specific controlled business rules. Research jurisdiction assumed = **Germany** (still to
be confirmed with client as "Primary operating country = Germany?").

### What one car-leasing Offer needs (dependency tree)
CUSTOMER/PARTNER (identity, address, company/person, registration, VAT ID, representatives,
beneficial owners, bank details, KYC/AML, credit/risk) · VEHICLE/ASSET (make, model,
variant/trim, VIN/HSN/TSN, engine/powertrain, equipment/options, MSRP/list, actual acquisition
price, CO₂/WLTP, registration, residual value) · LEASING PRODUCT (type, allowed term, mileage
bands, special payment, fees, interest/funding, margin, RV policy, taxes, eligibility, scenario
constraints) · CALCULATION (acquisition cost, residual, financing cost, margin, fees, taxes,
payments, rounding) · SCORING (bureau data, internal data, exposure, policy thresholds,
Green/Yellow/Red) · CONTROLS (mandatory fields, KYC/AML, sanctions, eligibility, approval
authority, exception handling, human review) · OUTPUT (EN/DE, PDF, commercial terms,
assumptions, scoring/status, audit).

The key question for each node: **where does its truth come from?**

### Vehicle/Asset data — largely externalizable
| Requirement | Possible source | Access | Finding |
|---|---|---|---|
| Make/model/HSN/TSN | KBA / GovData | Free/open | Useful baseline |
| Model/trim/specs | JATO | Commercial API | Excellent |
| Options/packs/colours | JATO | Commercial API | Excellent |
| OEM build compatibility | JATO Build Rules | Commercial API | Excellent |
| MSRP/option pricing | JATO | Commercial API | Strong |
| Incentives | JATO Incentives | Commercial API | Strong |
| VIN decoding | JATO / DAT | Commercial | Strong |
| Residual value | DAT / Autovista | Commercial | Excellent |
| Used-market benchmark | mobile.de API | Account/auth | Optional |
| German vehicle classification | KBA | Open | Good |

- **KBA (GovData):** open HSN/TSN + manufacturer/trade-name dataset (CSV; updated Jan 2026). Good as an **authoritative/free reference layer**, not a configurator (no trim/options/price/RV).
- **JATO:** developer APIs — Index, Specs, Build Rules, Incentives, VINView; 1,000+ data points/vehicle, 50+ markets, Germany covered; documented leasing-configurator use case. Gives vehicle/config/pricing data — **not** the client's margin/credit/rental formula.
- **DAT / SilverDAT:** FleetForecast RV forecasts up to 72 months / 200,000 km; VIN identify/decode; also vehicle valuations and **vehicle-finance calculations** via interfaces; has an LFM Leasing & Finance module. **Very high** MVP relevance for residual value. Never ask an LLM to predict RV.
- **Autovista:** Forecast/Identification/Specification/Valuation/Vehicle-Search APIs — a credible alternative RV/valuation path. Don't need both DAT and Autovista.
- **mobile.de:** Search API by make/model/mileage/price/condition (needs dealer/API account; some reference endpoints unauthenticated). Useful only as *market evidence* (asking prices ≠ transaction prices). Optional.

**Proposed asset architecture:** CAR SEARCH → {KBA reference/fallback, JATO primary catalogue} →
VEHICLE CONFIGURATION → VEHICLE ID → {JATO specs, DAT residual, client/dealer quote} → ASSET CONTEXT.

### Customer/Partner data — partly external; separate B2B vs B2C (important client question)
- **Unternehmensregister (German Company Register):** Handelsregister extracts, structured "SI"
  register content is **XML** for automated processing; retrieval free since Aug 2022. **No
  general public REST search API** found comparable to JATO → commercial providers may be easier for automation.
- **VIES (EU VAT validation):** interactive + **SOAP** applicative interface → VALID/INVALID + identity info. **High** usefulness, easy for MVP.
- **Transparency Register (UBO):** has an automated interface but it is **restricted** to authorities/eligible obligated entities, requires registration + accredited software. Client-eligibility question. Not a free public API.
- **KYC as a service:** e.g. **CRIF KYC More** (web + API) — company data, representatives, shareholders, UBO, PEP, sanctions, adverse media — one integration instead of many.

### Credit / scoring — commercial APIs exist
| Provider | B2B | B2C | Integration | MVP |
|---|---|---|---|---|
| Creditreform | ✅ | ✅ | API (Business Product API; RisikoCheck, eCrefo) | High |
| SCHUFA | ✅ | ✅ | Integrated services (index, PD, recommended limit) | High |
| CRIF | ✅ | ✅ | API/interface (+ Open Banking risk) | High |

**Critical distinction:** a bureau returns `{score, default_probability, recommended_limit}` —
it does **not** tell the app GREEN/YELLOW/RED or approve/review/decline. SCHUFA itself says the
*business* using the score sets the contract conditions; the score is an *input*, not the
decision. So `EXTERNAL PROVIDER → CLIENT POLICY ENGINE → GYR → approve/review/block`. **The
mapping must come from the client.** And **Yellow treatment** is explicitly under-specified in
the source PDF and must be validated, not assumed.

### Leasing calculation — the biggest client dependency
Externally obtainable **inputs:** vehicle list price / options price / OEM incentives / vehicle
identity (JATO), residual value (DAT/Autovista), market benchmark (mobile.de), VAT rate (German
law / EU TEDB), benchmark interest rates (Bundesbank/ECB), vehicle tax (Zoll), credit risk
(SCHUFA/Creditreform/CRIF). But there is **no universal "correct German leasing rate API"** — the
final Offer needs proprietary funding rate + margin + dealer discount treatment + RV policy +
risk premium + fees + special-payment policy + mileage policy + product structure + service +
insurance + rounding + tax treatment. So: `EXTERNAL DATA → CLIENT OFFER PARAMETERS → CALCULATION
ENGINE → MONTHLY RENTAL`. **The LLM must never be in the calculation box.** (DAT could also
provide finance calculations if the client already uses it — worth asking.)

### Reference data that is public/deterministic
- **Interest rates:** Bundesbank/ECB CSV/SDMX (deposit, marginal lending, refinancing). A *reference* rate, **not** the client's funding rate — no `ECB + 2%` unless the client says so.
- **VAT:** Germany standard **19%** (§12 UStG); EU TEDB SOAP service for rates by state/date/category. Rate can be external; *which components are taxable* is a client rule.
- **Vehicle tax:** Zoll publishes CO₂ + engine-capacity rules (relevant only if the lease package includes vehicle tax / full-service / TCO).
- **Bank/payment:** Bundesbank bank sort codes (TXT/CSV/XML) + IBAN→BIC derivation. Validates that a bank exists/routing — **not** that customer X owns account Y.
- **Sanctions:** EU consolidated financial-sanctions list (free). MATCH/NO MATCH for customer/director/UBO. Sanctions ≠ full KYC; PEP/adverse-media need extra sources.

### Legal/business controls (Germany)
- **Finanzierungsleasing** = a financial service under §1 KWG; §32 requires authorization for commercial provision; BaFin treats financial leasing as regulated. → Client must state the exact product (financial/operating/full-service/kilometre/residual-value; B2B/B2C) — it changes calculation, risk, required data, disclosures, approval, PDF.
- **AML/KYC:** GwG §10 duties (identify party + representative, establish UBO/control, understand purpose, PEP). Controlled workflow possible, but don't hard-code as mandatory until client confirms.
- **B2C adds controls:** GDPR Art. 22 (automated decisions with legal/similar effect → human intervention safeguards); EU AI Act Annex III (creditworthiness/credit scoring of natural persons). Reinforces AI-assists-not-decides. §506 BGB may pull some leasing structures into consumer-credit rules. **B2B vs B2C must be settled early.**

### Localization + PDF (already resolved)
`language → {en, de} → {labels, statuses, validation, PDF text}`. Controlled values
(READY/BLOCKED/GREEN/YELLOW/RED) get translation labels, not per-call LLM translation; LLM may
generate *explanations* in the selected language. PDF: `Validated Offer JSON → controlled PDF
template → EN or DE → Final Offer PDF` (never `LLM → "write me a lease offer" → PDF`).

### The four source classes (most important research result)
- 🟢 **Open/official:** KBA, Company Register, VIES, EU sanctions, Bundesbank, VAT/TEDB, Zoll.
- 🔵 **Commercial external API:** JATO, DAT, Autovista, Creditreform, SCHUFA, CRIF.
- 🟣 **Client-controlled:** leasing parameters, pricing formula, margins, eligibility, approval rules.
- 🟠 **User / Offer-specific:** desired car, mileage, term, budget, special payment.
Every material field should carry `{value, source, source_type, retrieved_at, status}`.

### External vs client — summary
Externally obtainable (✅, no client needed): make/model, trim/version, specs, options,
build compatibility (JATO), VIN identification, used-market reference, company legal identity,
VAT-ID validation, sanctions, bank routing info, VAT rate, benchmark rate. Provider-dependent:
residual forecast, MSRP (maybe dealer-specific), beneficial owner (access), PEP/adverse media,
company/consumer credit data.
**Must come from client (❌ external):** actual funding rate, commercial margin, lease
calculation formula, allowed terms, mileage bands, special-payment rules, residual-value policy,
eligibility rules, Green/Yellow/Red mapping, Yellow treatment, approval limits, role permissions,
exception/override rules, required documents, final PDF legal text.

### Provider combination to investigate first
Vehicle=JATO · Residual/valuation=DAT · Customer/KYC=official registers + VIES + EU sanctions ·
Credit=client's existing provider (SCHUFA/Creditreform/CRIF) · Rules/pricing=CLIENT controlled
reference data · Output=our EN/DE PDF. First ask: **which providers do you already license?**

### 10 precise client questions
1 market & customer (Germany only? B2B/B2C/both) · 2 exact leasing product · 3 existing data
vendors (+ sandbox access) · 4 offer parameters (mandatory fields, terms, mileage, special
payment/deposit, value limits, fees, scenario variables) · 5 calculation spec (formula/service,
funding source, margin, residual treatment, fees, VAT, rounding, recalc behaviour) · 6 credit
policy (inputs, GYR thresholds, Yellow workflow, hard declines, manual review, exposure limits) ·
7 product/eligibility rules · 8 approval controls (roles, limits, four-eyes, overrides, routing) ·
9 KYC (B2B/B2C requirements, documents, UBO/PEP/sanctions, existing providers) · 10 PDF
(template, mandatory wording, EN/DE approved text, branding, fields/statuses shown).
**Biggest blocker = client's Offer Reference Data + calculation logic + scoring policy + approval matrix.**

---

## Turn 4 — User: Vendors are NOT a blocker; build the client-controlled logic ourselves

- Vendors/partners are **not a pain point** for an MVP. The point of the API research was to get a
  **public structure for the required data** instead of assuming the data model.
- Build it **end-to-end using free credentials, trials, sandboxes**. For KYC/credit/etc., we only
  need to **understand the dataflow** and do a **mock/sandbox** version.
- The **client-controlled items will not be provided.** Based on our understanding, **we must put
  context-aware logic behind them, with all edge cases covered.** (The ❌/YES list: funding rate,
  commercial margin, lease calculation formula, allowed terms, mileage bands, special-payment
  rules, residual-value policy, eligibility rules, Green/Yellow/Red mapping, Yellow treatment,
  approval limits, role permissions, exception/override rules, required documents, final PDF legal
  text.)

---

## Turn 5 — Assistant: The MVP Reference Policy strategy (DE-PKW-V1)

**Principle:**
> We are not modelling "the client's actual leasing product." We are building a credible German
> passenger-car leasing **reference implementation** whose every business rule is deterministic,
> explainable, configurable and replaceable later.

Consistent with the source PDF: the MVP may use controlled mock/reference data for offer
parameters, business rules, customer/partner lookup and credit responses, and controlled
simulation for pricing/scoring/assessment/document output — while the Agent still must not
define/modify controlled offer parameters by itself. The ❌/YES items become **our MVP design
responsibility**, not blockers.

### Revised MVP architecture (3 layers, every integration has LIVE/SANDBOX/MOCK modes)
USER/AGENT → OFFER ORCHESTRATOR → {PUBLIC DATA ADAPTERS, SANDBOX/MOCK APIs, MVP POLICY ENGINE} →
DETERMINISTIC ENGINE (calculation, residual, risk, eligibility, validation) → SCENARIOS →
HUMAN REVIEW → EN/DE PDF. Every adapter: `mode ∈ {LIVE, SANDBOX, MOCK}` without changing the workflow.

### Free/public vehicle model (no JATO/DAT needed for MVP)
- **KBA/GovData:** free HSN/TSN + manufacturer/trade-name (no key).
- **EEA CO₂ passenger-car dataset:** country, manufacturer, OEM manufacturer, type-approval
  number, type/variant/version, make, commercial name, vehicle category, mass, WLTP, CO₂, fuel
  type, engine capacity, engine power, electric consumption — downloadable + **SQL REST endpoint**
  (no key). → gives an **official public structure** for the Asset object. Price is one field to
  seed/mock where no authoritative public price exists. Purpose = correct **domain structure and dataflow**.

### Free/trial stack the MVP is built around
| Capability | MVP source | Cost/auth | Treatment |
|---|---|---|---|
| German car reference | KBA/GovData | Free, no key | Live |
| Detailed EU vehicle structure | EEA CO₂ dataset/SQL | Free, no key | Live |
| VIN decoding | NHTSA vPIC | Free, no key | Optional/fallback |
| Reference funding rate | Bundesbank/ECB SDMX | Free, no key | Live |
| VAT rate | EU TEDB | Free SOAP | Live |
| VAT validation | VIES | Free | Live |
| Company information | Unternehmensregister XML | Retrieval free | Fixture/mock |
| EU sanctions | EU consolidated CSV/XML | Public | Live/local cache |
| Sanctions/PEP fuzzy | OpenSanctions | 30-day business trial | Sandbox/trial |
| Credit/KYC | CRIF Developer UAT | Free sandbox | Sandbox |
| Alternative credit sandbox | Creditsafe | Trial/test DB + OpenAPI | Sandbox |
| Residual value | our deterministic mock engine | Free | Simulated |
| Leasing calculation | our deterministic engine | Free | Simulated |
| Approval | our policy engine | Free | Simulated |
| PDF | local HTML→PDF library | Free | Real |

### Solving the ❌/YES fields as **MVP Car Leasing Reference Policy — DE-PKW-V1** (config/DB, not prompt)

**Funding rate (context-aware):** `funding_rate = reference_rate + term_spread + asset_uncertainty_spread`.
- Reference: latest Bundesbank/ECB series.
- Term spread: 12–24m +0.35% · 25–36m +0.50% · 37–48m +0.70% · 49–60m +0.90%.
- Asset spread: new/high-RV-confidence +0.00% · used/medium +0.30% · low RV confidence +0.60%.
- Spreads are synthetic MVP policy, explainable.

**Commercial margin:** `customer_finance_rate = funding_rate + base_margin + risk_adjustment + deal_adjustment`.
- Base margin 1.50%. Risk: Green +0.25% · Yellow +1.00% · Red not priced.
- Deal size: <€20k +0.25% · €20–60k 0.00% · €60–100k −0.10% · >€100k manual review.
- Total commercial margin floor 1.00%, cap 3.50%.

**Lease calculation formula (amortisation-to-residual):**
- `NetCap = acquisition_price + financed_fees − discounts/incentives − special_payment`.
- `r = annual_customer_rate / 12`.
- `PV_RV = residual_value / (1+r)^n`.
- `base_lease = (NetCap − PV_RV) × r / (1 − (1+r)^(−n))`.
- `monthly_net = base_lease + recurring_service_fees`.
- `monthly_gross = monthly_net × (1 + VAT)`.
- If `r == 0`: `(NetCap − residual) / months` (no divide-by-zero). Handles balloon/residual naturally.

**VAT:** Germany 19% now; use EU TEDB as reference config keyed by country+date; store the actual rate used in the Offer.

**Allowed terms:** absolute 12–60 months, step 6, preferred [24,36,48,60].
Context: new 12–60 · used 12–48 · annual km>30,000 → max 48 · low RV confidence → max 48 ·
vehicle age at lease end >8 years → BLOCK. Implement `allowed_terms(vehicle, mileage, rv_confidence)`.

**Mileage policy:** baseline 15,000 km/yr; selections 5k–40k step 5k. Validation: <5,000 → manual
review · 5k–40k supported · >40,000 out of standard policy. `contract_mileage = annual × term/12`.

**Mileage → residual adjustment:** reference 15,000 km/yr. Per +5,000 km/yr: RV −2.5pp; per
−5,000 km/yr: RV +1.5pp (asymmetric — conservative). Caps: max uplift +5pp, max penalty −15pp.
(e.g. 36m/15k base 58% → 20k 55.5% → 25k 53% → 10k 59.5%.)

**Residual value policy (Mock Residual Service):** base new-PKW table 12m 80% · 24m 68% · 36m 58%
· 48m 49% · 60m 41%. `RV% = base_term_RV + mileage_adj + vehicle_age_adj + market/asset_adj`,
clamped 20%–80%. Attach `{residual_value_pct, confidence, source:"MVP_RV_POLICY_V1", assumptions[]}`.
These are **MVP simulation values**, not presented as DAT/Autovista forecasts.

**Residual confidence:** HIGH (new, term≤48, km≤25k, complete data) · MEDIUM (60m term OR 25–35k
OR used ≤3y) · LOW (used >3y OR >35k km/yr OR unusual config OR missing specs). LOW → YELLOW → review.

**Special payment / Sonderzahlung:** 0–20% standard · >20–30% allowed but YELLOW/review · >30%
BLOCK (against acquisition cost). Edge case: if `adjusted_capital_cost ≤ PV_RV` → return
`SPECIAL_PAYMENT_TOO_HIGH` and ask user to reduce (never silently change the payment).

**Mileage settlement (kilometre leasing):** tolerance ±2,000 km; per-km rate: ≤€30k €0.10 ·
€30–60k €0.15 · >€60k €0.20 (same rate for excess and under-mileage). Appears in PDF terms.

**Eligibility engine.**
- Vehicle: category M1; price €10,000–€150,000; term ≤60; annual mileage ≤40,000; age at end ≤8y.
- Customer B2C: age≥18, identity verified, address, credit info, not sanctioned.
- Customer B2B: company identified, registration data, authorized representative, UBO/KYC status, credit info, not sanctioned.
- Offer: calculation success, residual available, risk≠RED, mandatory data complete, human review where required.
- Note: vehicle price >€100k → **not** blocked → YELLOW/manual approval.

**Credit scoring — do NOT emulate SCHUFA. Define our own MVP Risk Score 0–100.**
- B2C weights: credit/bureau mock 40% · debt-burden/affordability 25% · income stability 15% · existing exposure 10% · identity/KYC confidence 10%. Affordability ratio = (existing monthly debt + new gross lease) / net monthly income → ≤30% strong · 30–40% acceptable · 40–50% weak · >50% high risk.
- B2B weights: external/mock credit quality 40% · financial strength 25% · exposure vs limit 15% · company age/stability 10% · payment history 10%. Exposure/limit → ≤50% strong · 50–100% moderate · >100% weak.
- Hard blocks (skip weighted score → RED directly): confirmed sanctions match, fraud flag, identity failure, company inactive/insolvent flag, required credit outcome unavailable, unresolved material data conflict.
- Bands: **GREEN** ≥75 & no hard exception · **YELLOW** 55–74.99 OR soft policy exception · **RED** <55 OR hard blocking condition.

**Yellow treatment (source PDF left this open — now defined):** YELLOW → manual review required;
reviewer sees reason codes + scoring factors + offer + exceptions + alternatives → approve or
return for modification. **Yellow can never go directly to PDF.**

**Red treatment (two kinds):** *Economic Red* (excess exposure/poor affordability/very high
amount) → agent may suggest cheaper car / higher special payment / different term / lower mileage
→ recalculate → rescore. *Compliance Red* (sanctions confirmed / identity failure / fraud) → no
alternatives → BLOCKED.

**Approval limits (maker-checker):**
| Role | Authority |
|---|---|
| Sales User | create/edit/submit |
| Reviewer | review exceptions; GREEN ≤ €75k |
| Approver | standard approvals; GREEN ≤ €100k, YELLOW ≤ €50k |
| Senior Approver | higher-value/Yellow; GREEN/YELLOW ≤ €150k |
| Policy Admin | manage rules/reference data |
`> €150k` outside MVP/blocked. **Creator cannot approve their own Offer.**

**Role permissions:** Sales (view/create/edit/generate scenarios/submit; ❌approve) · Reviewer
(view/comment/return/resolve soft exceptions/review; ❌change pricing engine) · Approver
(review/approve within authority/return) · Senior Approver (same + higher limits + permitted soft
overrides) · Policy Admin (manage reference policy/mock rules; ❌approve own deals).
**Agent permissions ≤ current human user's permissions.**

**Exception/override framework — formal exception classes:** DATA_MISSING · DATA_CONFLICT ·
ASSET_UNSUPPORTED · PRODUCT_INELIGIBLE · TERM_OUT_OF_RANGE · MILEAGE_OUT_OF_RANGE ·
SPECIAL_PAYMENT_HIGH · RESIDUAL_LOW_CONFIDENCE · RISK_YELLOW · RISK_RED · SANCTIONS_MATCH ·
KYC_FAILED · AUTHORIZATION_DENIED · CALCULATION_FAILED · EXTERNAL_SERVICE_UNAVAILABLE ·
DOCUMENT_MISSING · PDF_GENERATION_FAILED. Each carries
`{code, severity, blocking, override_allowed, required_role, next_action}`.

**Hard vs soft override.** Never override: confirmed sanctions, KYC failure, fraud, RED
compliance, missing required calculation, missing mandatory approval, unauthorized user, final
validation failure. Can be reviewed: high-value vehicle, low RV confidence, new company, high
mileage, special payment 20–30%, minor data uncertainty, economic YELLOW. Every override records
who/when/reason/before/after/rule → audit event.

**Required documents (contextual).** B2C: identity, address, credit result, vehicle
quote/config; income evidence only when risk policy requires. B2B: company identity/register
result, authorized representative, UBO/KYC result, credit result, vehicle quote/config; financial
info when risk requires. Vehicle: **new** → VIN optional (car may not exist yet), use
make/model/type/variant/version/config ID/dealer quote; **used** → VIN required + registration
date + mileage + condition/valuation.

**KYC/credit dataflow (mock/sandbox):** Customer → KYC Adapter → Identity Result → Sanctions
Adapter → Sanctions Result → Credit Adapter → Credit Result → MVP Risk Engine. Sandbox = CRIF UAT
or Creditsafe; if credentials are slow, same adapter → local fixture JSON (no workflow change).

**PDF:** Final Validated Offer → Offer JSON → language template (EN/DE) → HTML → PDF. Sections:
offer reference, customer, vehicle, leasing product, term, mileage, special payment, monthly rate
net/gross, residual assumption, fees, mileage settlement, scoring status, conditions/exceptions,
approval, offer validity, assumptions, disclaimer.

**Final PDF legal text (MVP — non-binding illustrative offer):**
- EN: "**Illustrative Offer** — This document is a non-binding leasing offer generated as part of
  the MVP demonstration. The stated terms are based on the information, reference data and
  calculation parameters recorded in the Offer at the time of generation. Final contractual terms
  remain subject to the required verification, approval and separate contractual documentation."
- DE: "**Unverbindliches Angebot** — Dieses Dokument ist ein unverbindliches Leasingangebot, das
  im Rahmen der MVP-Demonstration erstellt wurde. Die dargestellten Konditionen basieren auf den
  zum Zeitpunkt der Erstellung im Angebot hinterlegten Informationen, Referenzdaten und
  Berechnungsparametern. Endgültige Vertragskonditionen stehen unter dem Vorbehalt der
  erforderlichen Prüfung, Genehmigung und gesonderten Vertragsdokumentation."
Do not generate a full German leasing contract.

**Provenance on every calculated result:**
`{monthly_payment_gross, calculation:{engine:"MVP_LEASE_CALC_V1", funding_policy:"DE_PKW_FUNDING_V1",
margin_policy:"DE_PKW_MARGIN_V1", residual_policy:"DE_PKW_RV_V1", risk_policy:"DE_PKW_RISK_V1",
tax_source:"EU_TEDB", reference_rate_source:"BUNDESBANK"}}`. Agent explains it, cannot alter it.

**Complete policy config skeleton — `DE_PKW_V1`** (country DE, EUR; product M1 KILOMETER_LEASING;
term {min12,max60,step6,preferred[24,36,48,60]}; mileage {baseline15000,min5000,max40000,step5000};
special_payment {standard_max_pct20, review_max_pct30}; residual {12:80,24:68,36:58,48:49,60:41,
extra_5000km_penalty_pp2.5, lower_5000km_bonus_pp1.5, minimum_pct20, maximum_pct80}; risk
{green_min75, yellow_min55, red_max54.99}; offer_limit {standard_max_eur100000,
absolute_mvp_max_eur150000}; output {languages[en,de], format PDF}).

**Therefore these are removed from the blocking client-question list** (funding rate, margin,
lease formula, terms, mileage bands, special-payment rules, residual policy, eligibility, GYR,
Yellow treatment, approval limits, roles, exceptions, required documents, PDF wording) — with the
explicit note in the technical docs: *"These rules constitute the controlled MVP reference policy
used to demonstrate the Agentic Offer Creation process and do not represent the production
commercial/credit policy of the leasing company."*

**Remaining genuine project choice:** primary product = **German passenger-car kilometre
leasing** (clear vehicle→term→annual-mileage→residual→monthly-rate relationship); residual-value
leasing as a second type only if time permits.

**The buildable MVP spine:** USER → AGENT (extract intent) → VEHICLE SEARCH (KBA/EEA) → VEHICLE
CONTEXT → CUSTOMER (mock/company structure) → KYC (CRIF sandbox/fixture) → SANCTIONS
(EU/OpenSanctions trial) → CREDIT (sandbox/deterministic mock) → MVP RISK ENGINE (G/Y/R) →
REFERENCE RATE (Bundesbank) → FUNDING POLICY → RESIDUAL POLICY → LEASE CALCULATOR → SCENARIOS
(24/36/48…) → AGENT EXPLAINS → USER SELECTS → HUMAN REVIEW → FINAL VALIDATION → EN/DE OFFER PDF.
Buildable without vendor agreements or hidden client pricing rules, while the Agent reasons and
explains and deterministic services stay authoritative.

---

## Provenance note on the external sources cited above
All external providers/regulations named in Turns 3 and 5 (KBA/GovData, JATO, DAT/SilverDAT,
Autovista, mobile.de, EEA CO₂ dataset, NHTSA vPIC, Unternehmensregister, VIES, Transparency
Register, CRIF, Creditreform, SCHUFA, Creditsafe, OpenSanctions, Bundesbank/ECB, EU TEDB, EU
sanctions list, Zoll, §12 UStG, §1/§32 KWG, BaFin, GwG §10, GDPR Art. 22, EU AI Act Annex III,
§506 BGB, ADAC, CFPB) were asserted by the prior research chat with citations. **They have not
been re-verified in this repo.** Before relying on any specific API capability, pricing tier,
field list, or legal claim, verify it against the live provider/regulatory source. See
[08-open-questions-and-verification.md](08-open-questions-and-verification.md).
