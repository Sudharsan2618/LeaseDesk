# 10 — Screen Redesign (draft flow + component map)

> Goal: a user-friendly, information-rich console. One workspace that changes **mode** with the
> offer's state, so each moment shows only what's relevant — no premature "MISSING", no duplicated
> panels, one clear place to complete inputs.

## Principle
The Offer Workspace has **one page, five modes** driven by workflow state. Provenance/price panels
appear only once there's something to be provenance/price *of*.

| Workflow state | Mode |
|---|---|
| DRAFT / UNDERSTANDING / CONTEXT_REQUIRED | **A · Intake** |
| (agent correction: out-of-range / economic-RED) | **A′ · Correction** (same shell, focused) |
| CALCULATED / SCENARIOS_AVAILABLE / SCENARIO_SELECTED | **B · Decide** |
| OFFER_GENERATED | **C · Generated** (B + generated banner, still editable) |
| FINAL_VALIDATION + compliance-RED | **D · Blocked** |

## Screens

### 1. Inbox
`Header (title + New offer)` · `Offers table` (reference · customer · vehicle thumb · status · band · €/mo · updated) · empty state. Row → Workspace.

### 2. New Offer
Just the NL prompt box + **Start**. Creates the offer, routes to its Workspace URL (refresh-safe). No form here.

### 3. Workspace — **Mode A · Intake** (fixes today's confusion)
Two columns. **No provenance panel. One vehicle card.**
```
┌ Header: OFF-xxxx · stepper(Intake active) · "Draft — complete the request"
├───────────────────────────────┬───────────────────────────┐
│ BUILD THE REQUEST (main)      │ AGENT (right rail)         │
│  • Vehicle hero: image+specs  │  • Live activity           │
│    +colour (ONE card)         │  • "What's still needed":  │
│  • Request form:              │      – customer  ✱         │
│    customer, term, mileage,   │      – term      ✱         │
│    quantity, special pmt,     │      – mileage   ✱         │
│    add-ons  → each missing    │    (checklist mirrors the  │
│    field marked ✱ needed      │     form's ✱ markers)      │
│  • "or tell the agent:" chat  │                            │
│    input + transcript         │                            │
│  • [ Confirm & price ]        │                            │
└───────────────────────────────┴───────────────────────────┘
```
- **The place to answer required inputs** = the Request form (with ✱ needed markers) **and** the chat — same panel, so there's never ambiguity. The right-rail checklist tells you exactly what's left.
- Vehicle hero shows the rich data (fuel, transmission, power, engine, body, seats, CO₂, colour swatches, image) — the data you asked to surface.

### 3. Workspace — **Mode B · Decide** (priced)
Three columns. Provenance now meaningful.
```
Header: band · outcome · €X/mo (per-vehicle) · €Y/mo (fleet) · stepper(Scenarios/Review)
┌ SUMMARY (left)        ┬ DECIDE (center)              ┬ WHY (right) ┐
│ vehicle (compact)     │ Scenario cards (24/36/48/60) │ AI expl.    │
│ customer + provenance │  – per-veh & fleet €, band   │ Risk factors│
│ key terms + add-ons   │  – select (highlight)        │ Audit trail │
│ exceptions            │ Price breakdown (how comp.)  │ Live feed   │
│                       │ [ Generate ] [ Adjust ]      │             │
└───────────────────────┴──────────────────────────────┴─────────────┘
```

### 3. Workspace — **Mode C · Generated**: Mode B + green "Generated" banner + Download (PDF later); Generate→Regenerate; still lets you re-select / Adjust.

### 3. Workspace — **Mode D · Blocked**: red banner + blocking reasons + explanation; economic-RED shows "Try alternative" → drops into Adjust (Mode A′).

## Component inventory (reusable, mode-composed)
`TopBar` · `StatusStepper` · `VehicleHero` (image+full spec+colour) · `RequestForm` (fields + ✱ needed) · `AgentChat` (transcript+input) · `NeededChecklist` · `ScenarioCards` · `PriceBreakdown` · `ProvenancePanel` (Decide+ only) · `RiskFactors` · `ExplanationCard` · `AuditTimeline` · `LiveFeed` · `OfferSummary`.

## What changes vs today
1. Provenance panel **only in Decide/Generated**, never during intake (kills the "MISSING" wall).
2. **One** vehicle card per view (no duplication).
3. Intake becomes a single, guided "Build the request" panel: form + chat together, with clear ✱ needed markers and a right-rail checklist → obvious where to answer.
4. Richer vehicle data + image surfaced in the hero.
5. Clear per-vehicle vs fleet totals in header + scenarios.

## Build approach
Visual mockups first (Claude Artifact) for approval → then port to the Next app component-by-component.
