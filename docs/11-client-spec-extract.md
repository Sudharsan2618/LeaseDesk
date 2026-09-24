# 11 — Client Specification: Full Readable Extract

> **Source:** `Agentic_Offer_Creation_MVP_Anonymized V1.0.pdf` — 95 pages, the *original client
> requirements document* (anonymized). This file is a faithful, readable transcription of its
> business content, organized by the document's own section numbering. Client-specific names,
> systems and channels were generalized in the PDF; those placeholders are kept here.
>
> **Status:** THIS is the authoritative business source of truth. Where earlier docs (02–10) or the
> current BE/FD code conflict with this, this document wins. Gaps are catalogued in
> [12-business-logic-bookmark.md](12-business-logic-bookmark.md).

---

## 1. Executive Summary

**1.1 The Opportunity.** The Offer Creation journey spans multiple business capabilities:
customer & partner context, product & asset selection, assessment, calculation, scoring,
validation and document generation. The opportunity is to move beyond documenting the current
state and demonstrate a *materially simpler* Offer Creation experience.

**1.2 The MVP Mission.** Demonstrate a future-state **Agentic Offer Creation experience** that
takes a leasing requirement through the key stages of Offer Creation, buildable in **2–3 weeks**.
It proves the experience and functional approach — it does **not** replace the wider leasing
platform.

**1.3 What the MVP must demonstrate** (seven objectives):

| Objective | What must be demonstrated |
|---|---|
| Intent-led | User expresses the leasing requirement without navigating the underlying application landscape |
| Context-aware | Relevant customer, partner, product and asset information is assembled when required |
| Agent-assisted | Agent identifies gaps, coordinates activities, compares scenarios and explains outcomes |
| Controlled | Rules, calculations and material decisions remain appropriately governed |
| Human-directed | User reviews, confirms and makes the required decisions |
| Decision-ready | The journey produces a validated Offer outcome |
| Traceable | Material Offer activity can be followed through the audit trail |

**1.5 Agentic Responsibility.** Use Agentic AI for interpretation, information assembly,
coordination, comparison and explanation. **Deterministic calculations, business rules and
material financial or credit decisions remain controlled and are NOT delegated to the Agent.**

**1.6 MVP Boundary.** The MVP **ends with a completed and validated Offer** that is generated or
made ready for downstream processing. Contract creation and contract lifecycle are **out of
scope**. The MVP does not predetermine whether existing capabilities are retained, modernized,
replaced or migrated.

---

## 2. Why Offer Creation Needs to Evolve

- **2.1** Offer Creation is a cross-system **business journey** assembling one business outcome from
  multiple capabilities (Customer/Partner, Product, Asset, Credit & Scoring, Document services,
  downstream).
- **2.3 Five friction areas:** Data assembly (info distributed across capabilities); System
  dependency (many specialized apps); Decision paths (scoring can be automated or manual); Missing
  information / exceptions (interrupt the journey); Downstream handoff (Offer feeds later
  processing).
- **2.4** Required shift: **from a system-driven user journey to an intelligently orchestrated Offer
  Creation experience, keeping the user in control of material decisions.**

**2.5 What the Agent should do:**

| Agent responsibility | MVP behaviour |
|---|---|
| Understand | Interpret the user's Offer requirement |
| Retrieve / assemble | Bring together relevant information required for the journey |
| Identify gaps | Highlight missing or inconsistent information |
| Orchestrate | Coordinate the required Offer Creation activities |
| Compare | Present relevant Offer scenarios for review |
| Recommend | Prepare recommendations based on available information and applicable rules |
| Explain | Make outcomes and recommendations understandable to the user |

The Agent must **not** independently determine pricing, eligibility, credit policy or approval.

**2.6 The governing motto — repeated throughout the document:**

> **AI assists. Rules decide. Humans govern.**

---

## 3. Current (AS-IS) Offer Creation Process

- **3.3 Three sales / Offer Creation channels (entry points):**
  1. **Internal Sales User** channel
  2. **Partner Sales** channel
  3. **Credit Partner** channel

- **3.4 Customer / Partner Identification** — established *before* the commercial Offer is
  constructed; approach differs by channel:
  - **Offer Partner** — created as an entity with the *minimum attributes* required to initiate and
    construct the Offer (available directly from the process; not fetched externally for initial
    creation).
  - **Business Partner** — loaded directly into the system and made available for the Offer.
  - The distinction depends on the entry channel.
  - Partner search by partner number or attributes (name, address). Partner creation manually, via
    search, or via web services.

- **3.5 Product Selection & Offer Parameters** — the Offer is constructed against the relevant
  **Business Line** and **Leasing Product**. The selected Business Line + Leasing Product
  **determine the applicable Offer Parameters and product-specific rules**. Offer Parameters may
  include: commercial parameters; permitted term & payment conditions; product eligibility
  conditions; applicable calculation inputs; scenario constraints; other product-specific
  conditions. **The Agent does not define or modify these parameters** — they come from controlled
  Offer Reference Data / rules.

- **3.6 Asset / Object Selection** — the Offer is associated with the leased asset/object.
  **Documented asset categories:**
  - **PKW** (passenger cars)
  - **Equipment**
  - **NFZ** (commercial vehicles)
  - **ITK** (IT & communications)

  Different asset info sources depending on object type. Object attributes captured as part of Offer
  construction *before* calculation.

- **3.7 Asset Assessment** — where applicable, the selected asset proceeds through an assessment
  process (external assessment service for applicable object types; ITK handled internally). An
  unavailable assessment dependency can prevent progression.

- **3.8 Lease Calculation** — once customer, business line, product and asset info are established,
  the Offer proceeds to lease calculation. Determines the commercial result; supports parameter
  changes (e.g. lease tenure). A **lease rental plan** is generated from business line + asset
  selection and can be recalculated following customer requests.

- **3.9 Customer Review, Documentation and Agreement** — the customer can: agree; request changes;
  review documentation; or require corrections that trigger **recalculation and/or document
  regeneration**. Changed parameters ⇒ recalc + updated documentation *before* proceeding.

- **3.11 Credit Scoring** — two patterns:
  - **Automatic Scoring** — parameters match the predefined automatic process ⇒ scored
    automatically, no manual intervention.
  - **Manual Scoring / Intervention** — parameters do not match ⇒ manual review, resulting status
    notified back.
  - Outcome returned as **Green, Yellow or Red**, which determines the subsequent Offer path.

- **3.12 Scoring Outcome** — **Red prevents the current Offer from proceeding** through the normal
  path and requires a new Offer or variant. **Yellow handling is under-specified** and should be
  validated with the client, not assumed.

- **3.13 Offer Validation & Status** — the Offer progresses through identifiable activities/statuses
  (Product selection, Customer selection, Object/calculation, Validation/proofing, Scoring) — not
  just a final calculated value.

- **3.14–3.20** Bank/supplier info; document generation (Offer document, SEPA mandate,
  legal/supporting docs, payment plan); signature & return; submission with validation; manual
  verification workflow (four areas; standard checklist; missing info ⇒ follow-up tasks); recurring
  verification loop; completion ⇒ handoff to downstream Contract platform (**out of MVP scope**).

---

## 4. Current Technology Landscape (reference only — mocked in MVP)

Principal Offer-relevant capabilities: **Offer Management Platform** (origination core: offer mgmt,
product config, object handling, calculation, scoring interaction, submission); **Customer &
Partner Platform** (partner search/create, address, bank, hierarchy, rating, sync); **Credit &
Scoring Service** (auto + manual scoring, external credit sources A/B); **Asset Assessment Service**
(Equipment/NFZ; ITK separate); **Print Services / DMS** (doc generation, output, archival);
**Contract Management Platform** (downstream boundary — not built). Wider estate: CRM, DWH.

**4.14 Technology boundary for the MVP:**

| Technology area | MVP treatment |
|---|---|
| MVP user experience | **Build** |
| Agentic orchestration capability | **Build** |
| Customer / partner data | Controlled data / simulation |
| Offer and calculation behaviour | Controlled simulation or service interaction |
| Scoring behaviour | Controlled simulation |
| Asset assessment | Controlled simulation for selected scenario |
| Document output | Controlled simulation / representative output |
| Manual verification | Represent the workflow and decision points |
| Contract creation, DWH, downstream | **Defer** |
| Enterprise-wide modernization | Out of scope |

---

## 5. Friction → MVP Opportunity — the SIX interventions

The whole MVP is built around six interventions (this is the functional backbone):

1. **UNDERSTAND** — capture the requirement; translate to structured Offer info; identify what can't
   yet be established; ask for clarification. *(Agent interprets; does not decide eligibility.)*
2. **ASSEMBLE** — assemble relevant info; show what's being used; distinguish available vs still
   required; avoid manual reconstruction of context.
3. **VALIDATE** — identify missing / incomplete / inconsistent info; show *why* required; identify
   what the user must provide/resolve; **prevent progression where a required condition is not
   satisfied.** *(Surface issues + evidence; never invent missing info.)*
4. **ORCHESTRATE** — maintain journey state; determine next required activity; initiate the
   applicable capability; receive status/output; move to next valid state; surface blocked/pending
   activities.
5. **COMPARE** — support alternative scenarios; calculate each with the deterministic engine;
   present side-by-side; show what changed; let user select. *(Agent structures scenarios; the
   financial result comes from the calculation capability.)*
6. **EXPLAIN** — explain inputs used, calculation outcome, scenario differences, missing info,
   scoring/status outcome, required next action. *(Explains without changing the underlying
   decision.)*

**5.4 Priority** — all six interventions are **HIGH / Build**. Explicitly **NOT MVP**: autonomous
pricing decision, autonomous credit decision, contract creation, enterprise-wide platform
replacement.

**5.5 Decision Authority & Controlled Offer Reference Data.** The Agent becomes aware of business
rules and Offer Parameters through a **controlled reference data set** (mock/curated for the MVP).
It uses this to identify applicable rules/params, determine required info, identify gaps, support
scenario generation *within permitted parameters*, explain conditions, and prepare the Offer for
deterministic calculation, validation and human review. The Agent does **not** autonomously:
determine credit approval, override pricing, change business rules, approve outside authority, or
create the downstream contract.

---

## 6. Industry Benchmark → Seven Design Principles

Benchmark (Odessa, Alfa primary; FIS/Solifi/CGI secondary) → market pattern is **connected
origination journeys**, not isolated quotation. Seven principles carried into the MVP:

1. **Guided, not form-heavy**
2. **Context before data entry**
3. **Scenario-based quoting**
4. **Deterministic pricing underneath** (Agent is not the pricing engine)
5. **Explainable outcomes**
6. **Workflow-driven progression** (current state + next action explicit)
7. **Human control**

Do **not** claim to copy a vendor's AI feature. Create original MVP screens using verified market
patterns.

---

## 7. Target Experience — Intent → Decision-Ready Offer

**7.3 Six target-experience principles:** Intent-led · Context-first · Guided · Scenario-based ·
Exception-led · Explainable.

**7.4 Five connected experience states:** *Intent → Context → Exploration → Review →
Decision-ready Offer.*

**7.5 A single Offer context** — the user stays oriented around **one Offer context**; can always
understand the Offer as a whole.

**7.6 From data entry to guided completion** — distinguish four states of every piece of Offer
information:

- ✓ **Established**
- ✓ **Confirmed**
- ◐ **Requires confirmation**
- ⚠ **Missing / needs action**

**7.8 Exceptions** are a first-class, visible, actionable state (missing info; requires
confirmation; outcome requires review; outside expected condition; decision requires human
intervention) — never an unexplained interruption.

**7.9 Human review** — human judgement is deliberately retained at consequential decision points;
the transition from assisted preparation to human decision is explicit.

**7.10 Decision-ready Offer** — a coherent view where relevant information, outcomes and outstanding
considerations are clear enough for the responsible user to decide. Does not imply contract
activities are done.

---

## 8. MVP Scope & Objectives

**8.1 Delivery approach — four treatments:**

- **BUILD** — capabilities essential to the demonstration.
- **MOCK** — controlled representations where external dependency creates delivery risk.
- **SIMULATE** — deterministic responses for selected business/decision services.
- **DEFER** — capabilities not required to prove the target experience.

**8.3 Five outcomes to demonstrate:** Intent · Intelligence · Orchestration · Control · Offer.

**8.4 BUILD floor** (minimum credible MVP): **Offer workbench, case state, Agent orchestration, LLM
capability, rules/threshold controls, audit trail.**

**8.5 MOCK list:** Customer/partner lookup · Product catalogue · **User authorization sets /
role-based behaviour** · Offer Reference Data / Business Rules / Offer Parameters · Asset catalogue ·
Credit/risk response · Document generation output · E-sign / delivery · Workflow approval backend ·
**Bilingual UI / workflow messaging** (limited demonstration).

**8.6 SIMULATE:** Pricing/calculation (deterministic) · Risk/scoring (representative response) ·
Asset assessment (representative scenario) · Validation/business rules (defined MVP rules &
thresholds) · Document output (representative artifact). Principle: *simulate the business outcome
where necessary; do not simulate the user experience.*

**8.7 DEFER / not demonstrated:** Full contract creation, contract admin, portfolio servicing, full
migration, platform replacement, full DWH/DMS transformation, full portals, broader lifecycle. Also
**not**: autonomous credit approval, autonomous pricing override, full production integration,
enterprise integration modernization.

**8.8 Explicit stop point:** the MVP stops at the **completed, validated, generated / decision-ready
Offer**.

**8.10 Success dimensions:** Experience · Intelligence · Scenarios · Decision support · Control ·
Output · Traceability · Delivery (within 2–3 weeks).

---

## 9. End-to-End MVP Process — the single spine

**Channel positioning:** Primary MVP = **Sales / internal-user-led** Offer Creation. Customer
self-service / B2C is a *future extension, not in scope*.

**The ten process steps:**

| # | Step | What happens |
|---|---|---|
| 01 | **Initiate Offer** | Start from a leasing requirement (structured input, natural language, or both). User need not know the underlying activity sequence. |
| 02 | **Establish Context** | Bring in customer/partner, product, asset/object, and initial commercial requirements. Where info can't be established confidently ⇒ **confirmation / information-required state.** |
| 03 | **Configure Offer** | User completes info needed to form the Offer; distinguish known/inferred/needs-confirmation/missing. One representative Offer scenario is sufficient for the demo. |
| 04 | **Check Completeness** | Before calculation/decision: check required info for the selected scenario. **A material gap must NOT be silently filled** — identify missing/inconsistent info and return to the user. |
| 05 | **Calculate / Assess** | Obtain controlled outcomes: commercial calculation, asset/object assessment, risk/scoring, validation. Agent does not determine material financial/credit/policy outcomes. |
| 06 | **Generate Scenarios** | Generate a *limited* number of alternatives from the user's objective. Not unrestricted optimization. Each scenario is subject to the same controlled calculation + validation. |
| 07 | **Review Outcomes** | User compares alternatives; selects a scenario. **A material parameter change repeats the calc + validation cycle before progressing.** |
| 08 | **Human Review** | Reviewer receives full Offer context + outcomes in one place. A material change or unresolved issue returns the Offer to an earlier stage. **Controlled iteration — not a terminal screen.** |
| 09 | **Validate Offer** | Final validation: sufficiently complete; internally consistent; within MVP rules/thresholds; supported by required outcomes; ready to represent as final artifact. **No Offer is decision-ready while a material unresolved condition remains.** |
| 10 | **Generate Offer** | Produce output containing customer info, product/asset info, commercial terms, selected scenario, status/outcomes, supporting explanation/review info. |

**End state:** `configured → validated → reviewed → generated` ⇒ decision-ready / downstream
handoff. Contract creation is outside.

**9.14 Process control model — three control types:**

| Control | Role |
|---|---|
| **Agentic assistance** | Understand, assemble, coordinate, identify gaps, prepare scenarios, explain |
| **Deterministic control** | Perform defined calculations, rules, validations, controlled decision logic |
| **Human decision** | Review material outcomes, resolve exceptions, approve progression where required |

---

## 10. MVP Screens — The Offer Workbench

**Design intent:** ONE stateful Offer workbench. **Structured UI, not chatbot-only** — conversation
can aid intake/clarification/explanation, but Offer information, commercial outcomes, validation
states and decisions must remain visible in structured UI.

**10.2 Every screen answers four questions:** *Where am I? · What do I know? · What needs attention?
· What can I do next?*

**User Authorization & Role-Based Behaviour** *(mocked/simulated for MVP)* — the experience respects
the logged-in user's **authorization set**. Example roles: **View · Edit · Review · Approve ·
Restricted actions**. The Agent does not grant, extend or bypass authorization.

**Negative Workflows:** clear, actionable, context-specific messages — **WHAT happened → WHY →
WHAT is required next** (missing info; validation failure; authorization restriction; scoring/decision
block).

**Bilingual Experience:** support the Offer experience in **two languages** (labels, guidance, status
messages, validation messages, Agent explanations). Language selection stays consistent through the
journey. Controlled translated set for the MVP.

**The seven core screens + one optional:**

| Screen | Purpose | Primary actions | Agent assistance |
|---|---|---|---|
| **01 — Offer Inbox** | Starting point: view existing Offers + start new | Open, Start New, Search, Filter, Resume | Highlight Offers needing attention; urgency/expiry; suggest next action |
| **02 — New Offer / Intake** | Start from a leasing requirement (conversational + structured) | Enter requirement, Select/create customer, **Confirm extracted info**, Continue | Interpret request; extract; prefill known fields; identify ambiguity; ask for missing |
| **03 — Customer Context** | Consolidated customer context before configuration | Review, **Confirm**, Resolve issue, Continue | Summarize context; **identify duplicate matches**; highlight history; flag info needing confirmation |
| **04 — Asset + Product** | Establish asset + product configuration | Select asset, Select product, Modify config, Resolve missing, Continue | Map descriptions to structured asset info; suggest product structures; identify missing specs; **flag incompatible combination** |
| **05 — Pricing + Scenarios** | Understand commercial outcome + compare alternatives (**most important screen**) | Modify params, Generate scenarios, Compare, Select scenario, Return to config | Prepare scenarios; explain differences; highlight trade-offs; recommend. **Values come from controlled calculation.** |
| **06 — Credit / Approval** | Present risk/scoring outcome + human review/approval path | Review outcome, Review exceptions, **Approve where authorized**, Return for correction, Continue | Summarize outcome; highlight missing evidence; prepare review info; explain. **Agent does not approve credit or override conditions.** Approval states: auto-approved / pending approval / referred / declined. Exceptions: missing documents / policy breach / over-limit. |
| **07 — Offer Review + Output** | Final consolidated view + produce Offer output | Review, Preview, Correct, **Generate Offer**, Return | Prepare Offer narrative; summarize assumptions; highlight outstanding issues; prepare review checklist. Content: Offer summary, assumptions, document preview, disclosure checklist, generation controls. |
| **08 — Activity / Audit** *(optional)* | Traceability of activity + decisions | Filter history, View change, Compare versions, Export | Summarize history in plain language; underlying record is the source of truth. Content: activity timeline, decision log, version history, comments. |

**10.11 Screen ↔ experience mapping:** Intent→02 · Context→03 · Configuration→04 · Exploration→05 ·
Decision→06 · Decision-ready→07 · Traceability→08.

**10.12** These are **not** eight independent apps — they are **views/interaction states within one
Offer workbench.** **10.13 Screen boundary:** `Validated Offer → Generated Offer → Decision-Ready
Output`. No screens for contract creation/admin/servicing/lifecycle/platform admin.

---

## 11. Functional Requirements (FR-01 … FR-63)

### 11.1 Offer Intake & Intent
- **FR-01** Enter a new leasing requirement in natural language and/or structured info.
- **FR-02** Identify relevant Offer information in the requirement.
- **FR-03** Present the interpreted requirement for user confirmation.
- **FR-04** Identify ambiguous/unclear information requiring confirmation.
- **FR-05** Correct or add information before proceeding.

### 11.2 Customer, Product & Asset Context
- **FR-06** Identify and confirm the customer / partner associated with the Offer.
- **FR-07** Present relevant customer / partner information available for the Offer.
- **FR-08** Select or confirm the relevant **product**.
- **FR-09** Select or provide the relevant **asset / object** information.
- **FR-10** Identify information that is missing or requires confirmation.
- **FR-11** Correct information presented by the MVP.

### 11.3 Offer Completeness & Validation
- **FR-12** Identify mandatory information not provided.
- **FR-13** Identify incomplete or inconsistent information.
- **FR-14** Distinguish complete / requires-confirmation / missing / invalid.
- **FR-15** Identify the action required to resolve a material issue.
- **FR-16** **Prevent progression where a mandatory requirement remains unresolved.**
- **FR-17** When info is corrected/added, reassess the affected requirement.

### 11.4 Offer Calculation & Assessment
- **FR-18** Produce the commercial calculation required for the Offer.
- **FR-19** Provide the applicable asset-assessment outcome for the selected scenario.
- **FR-20** Provide the applicable risk / scoring outcome.
- **FR-21** Clearly distinguish Offer inputs from resulting outcomes.
- **FR-22** Identify when a required calculation/assessment/scoring outcome is unavailable or needs
  action.
- **FR-23** Review the inputs contributing to a material outcome.

### 11.5 Scenario Comparison
- **FR-24** Create alternative scenarios by changing relevant parameters.
- **FR-25** Present a **limited** set of viable scenarios for comparison.
- **FR-26** Show key assumptions and outcomes for each scenario.
- **FR-27** Clearly show material differences between scenarios.
- **FR-28** Select a preferred scenario.
- **FR-29** A material change to the selected scenario triggers recalculation + assessment before
  proceeding.

### 11.6 Outcome Explanation
- **FR-30** Explain key inputs used to produce an outcome.
- **FR-31** Explain material differences between selected scenarios.
- **FR-32** Explain missing information or validation issues.
- **FR-33** Present the scoring/status outcome in understandable terms.
- **FR-34** Identify the next action when an Offer cannot progress.

### 11.7 Human Review & Decision
- **FR-35** Reviewer reviews complete Offer context, selected scenario and outcomes.
- **FR-36** Reviewer reviews outstanding exceptions and validation results.
- **FR-37** Reviewer approves where requirements are satisfied.
- **FR-38** Reviewer returns the Offer for correction.
- **FR-39** Reviewer makes permitted changes to Offer information.
- **FR-40** A material change during review causes reassessment before finalization.
- **Decision boundary:** the MVP shall not independently approve material credit decisions, override
  controlled commercial outcomes, or bypass mandatory validation.

### 11.8 Final Offer Validation
- **FR-41** Confirm required Offer information is complete.
- **FR-42** Confirm material inconsistencies/exceptions resolved.
- **FR-43** Confirm required calculation/assessment/scoring outcomes are available.
- **FR-44** Confirm required human review completed.
- **FR-45** Clearly indicate whether the Offer is **Ready / Requires Action / Blocked**.
- **FR-46** Prevent final generation when a mandatory requirement is unresolved.

### 11.9 Offer Generation
- **FR-47** Contains customer / partner information.
- **FR-48** Contains selected product and asset information.
- **FR-49** Contains selected commercial scenario and applicable terms.
- **FR-50** Contains relevant calculation and assessment outcomes.
- **FR-51** Contains the applicable scoring / status outcome.
- **FR-52** Identifies material assumptions and resolved exceptions where applicable.
- **FR-53** Represents the final reviewed and validated Offer.

### 11.10 Offer Status & Traceability
- **FR-54** Show current Offer status and required next action.
- **FR-55** Show material changes made during creation.
- **FR-56** Retain the selected scenario and material scenario changes.
- **FR-57** Show material validation, review and decision actions.
- **FR-58** Understand how the final Offer was reached from history.

### 11.11 User Authorization & Language
- **FR-59** Apply the authorization set of the current user.
- **FR-60** Make actions unavailable/blocked where the user is not authorized.
- **FR-61** The Agent shall not grant or bypass user authorization.
- **FR-62** Provide clear, actionable messages for material negative workflows.
- **FR-63** Support the defined two-language experience for core UI, workflow messages and
  Agent/user guidance.

**Backbone:** INTAKE → CONTEXT → COMPLETENESS → CALCULATION → SCENARIOS → EXPLANATION → HUMAN
REVIEW → VALIDATION → OFFER.

---

## 12. MVP Business Rules & Decision Controls (BR-01 … BR-19)

### 12.1 Information Handling
- **BR-01** Distinguish user-provided info from inferred/suggested info.
- **BR-02** Do not treat missing information as confirmed.
- **BR-03** Ambiguous info requires user confirmation before use in a material outcome.
- **BR-04** Conflicting info is surfaced to the user for resolution.
- **BR-05** Material changes trigger reassessment of affected outcomes.

### 12.2 Commercial & Offer Controls
- **BR-06** Commercial calculations based on controlled business inputs and outcomes.
- **BR-07** Agent shall not independently alter a calculated commercial outcome.
- **BR-08** Agent shall not override applicable pricing or eligibility conditions.
- **BR-09** Alternative scenarios stay within permitted Offer parameters.
- **BR-10** A scenario is not presented as viable when a required business condition is unmet.

### 12.3 Risk & Scoring Controls
- **BR-11** Risk/scoring outcomes presented as received/established through the process.
- **BR-12** Agent explains a scoring/status outcome but shall not reinterpret it as a different
  decision.
- **BR-13** A missing/unresolved required scoring outcome prevents the Offer being fully validated.
- **BR-14** Agent shall not independently approve or reject a material credit decision.

### 12.4 Human Decision Controls
- **BR-15** Human review required before final Offer generation.
- **BR-16** Material exceptions require human resolution where rules can't establish a valid outcome.
- **BR-17** Reviewer can approve, return or correct within the permitted process.
- **BR-18** A material change following review requires reassessment.
- **BR-19** The MVP shall not bypass mandatory human review or validation.

### 12.5 Offer Readiness Rules
An Offer is **READY** only when: required info complete; material inconsistencies resolved; required
commercial outcomes available; required assessment/scoring outcomes available; material exceptions
resolved; required human review completed; selected scenario confirmed. **REQUIRES ACTION** = a
correctable issue remains. **BLOCKED** = a mandatory condition prevents progression.

### 12.6 Agent Decision Boundary

| Agent **may** | Agent **shall not** |
|---|---|
| Understand the request | Make unsupported assumptions |
| Assemble information | Override business outcomes |
| Identify gaps | Override pricing |
| Suggest scenarios | Make autonomous credit decisions |
| Compare alternatives | Bypass mandatory validation |
| Explain outcomes | Approve material exceptions independently |
| Prepare human review | Generate a final Offer before required controls are satisfied |
| Identify next actions | Commit the business to an unapproved Offer |

---

## 13. MVP Acceptance Criteria

**13.1 End-to-end** — the user can: 1) initiate from a requirement; 2) confirm interpreted customer/
product/asset/commercial context; 3) identify & resolve missing/inconsistent info; 4) obtain
calculation/assessment/scoring outcomes; 5) create & compare a limited number of scenarios; 6) select
a preferred scenario; 7) understand outcomes & exceptions; 8) submit for human review; 9) resolve
review actions; 10) complete final validation; 11) generate a decision-ready Offer.

**13.2 Functional AC (AC-01 … AC-18)** — includes: start without navigating unrelated activities;
capture material info from the requirement; confirm/correct/complete; clearly identify missing/
incomplete/inconsistent; cannot progress with an unresolved mandatory requirement; outcomes
available; evaluate multiple scenarios; compare & select; material changes trigger reassessment;
understand assumptions/outcomes/exceptions; human reviewer can approve/return; final validation says
Ready/Requires-Action/Blocked; generate the validated Offer; generated Offer reflects final selected
scenario; changes/review/decisions are traceable; **authorization respected**; **bilingual** core
screens + selected messages.

**13.3 Agentic behaviour acceptance** — success = understands requirement; reduces manual assembly;
identifies gaps/inconsistencies; assists scenario creation & comparison; explains outcomes; prepares
human review; identifies next action. *Not successful merely for providing a conversational
interface — value must be a measurable reduction in user effort.*

**13.4 Control acceptance** — unsupported assumptions not silently accepted; controlled commercial
outcomes not overridden by Agent; scoring outcomes not reinterpreted; mandatory validation not
bypassed; material decisions remain under human review; an incomplete/blocked Offer cannot be
presented as completed.

**13.5 Completion test:** `USER REQUIREMENT → UNDERSTOOD OFFER → COMPLETE CONTEXT →
CALCULATED/ASSESSED OUTCOMES → COMPARED SCENARIOS → HUMAN REVIEW → FINAL VALIDATION → GENERATED,
DECISION-READY OFFER`. The acceptance point is the **decision-ready Offer**.
