# 13 — Agent Workbench Design: 60/40 Wizard + Conversational Agent

> **Supersedes** the mode-driven single-column workspace in [10-screen-redesign.md](10-screen-redesign.md)
> for the offer detail screen. Grounded in [11-client-spec-extract.md](11-client-spec-extract.md)
> and the decisions in [12-business-logic-bookmark.md](12-business-logic-bookmark.md).
>
> **User directive (2026-09-23):** split the offer screen — **left 60% = end-to-end wizard flow
> (structured input/output)**, **right 40% = live chat between the agent and the salesperson**. The
> agent must handle **any** phrasing of a leasing request, extract the information, and drive the
> wizard. Example scenario (one of many): *"I need 4 seater 30 insured cars — my budget is $300k."*

---

## 1. The core layout — one Offer, two synchronized views

```
┌ Top bar: brand · Offers · OFF-xxxx · readiness pill (Ready/Requires action/Blocked) · lang · theme ┐
├──────────────────────────────────────────────────────────┬──────────────────────────────────────┤
│  LEFT · 60%  —  WIZARD (the structured Offer)             │  RIGHT · 40%  —  AGENT CHAT           │
│                                                            │                                      │
│  Vertical stepper down the journey, each step a section:  │  • Conversation: salesperson ⇄ agent │
│   1 Partner            ✓ confirmed                         │    (natural language, any request)   │
│   2 Business Line + Product   ◐ requires confirmation      │  • Agent extracts → fills the wizard  │
│   3 Asset category + Asset    ⚠ needs action               │    on the left in real time          │
│   4 Commercial requirements   ⚠ needs action               │  • Agent asks for missing / ambiguous │
│   5 Pricing + Scenarios       — locked until 1–4 done      │  • Agent explains outcomes & options  │
│   6 Review & confirm → Generate                            │  • "Applied to the offer" chips show  │
│                                                            │    what each message changed          │
│  Each section shows: inputs, resolved outputs, the 4      │  • Message input pinned at the bottom │
│  info states, and its own [Confirm] gate.                 │                                      │
└──────────────────────────────────────────────────────────┴──────────────────────────────────────┘
```

**They are two views of ONE Offer context** (spec §7.5). The chat drives the wizard; the wizard
reflects the chat; a manual edit in the wizard is narrated back into the chat. Neither is a
"chatbot-only" experience — per §10, commercial outcomes, validation states and decisions always
stay visible in the **structured left panel**.

Responsive: below ~1024px the two stack (wizard first, chat collapsible), keeping the 60/40 intent
on desktop where the work happens.

---

## 2. The wizard = the selection hierarchy, each step a CONFIRM gate

This fixes the partner-confirmation gap and makes **every** hierarchy step confirmable
(spec §3.4–3.6, FR-03/06/08/09, BR-02/03).

| # | Step | Inputs (structured) | Outputs / what the agent resolves | Confirm gate |
|---|---|---|---|---|
| 1 | **Partner** | Channel (Internal/Partner/Credit); customer name or number | Matched partner, address, VAT, **duplicate candidates** | ✅ **Confirm partner** (FR-06) — was missing; now explicit |
| 2 | **Business Line + Product** | Business line, leasing product | Applicable **Offer Parameters & rules** (term/payment/eligibility ranges) from reference data | ✅ Confirm product |
| 3 | **Asset category + Asset** | Category (PKW/Equipment/NFZ/ITK); asset + attributes | Matched catalogue asset; **attribute filters** (e.g. seats); incompatibility flags | ✅ Confirm asset |
| 4 | **Commercial requirements** | Quantity, term, mileage/usage, special payment, services, insurance, **budget/constraints** | Normalized values; ambiguities flagged | ✅ Confirm requirements |
| 5 | **Pricing + Scenarios** | (from 1–4) | Deterministic calc + limited scenarios; **budget-fit** highlighted | Select scenario |
| 6 | **Review & confirm** | full offer | Consolidated view + exceptions | ✅ **Human review → Generate** (single-actor gate, BR-15) |

Each step carries the **four info states** on its fields: ✓ Established · ✓ Confirmed · ◐ Requires
confirmation · ⚠ Missing/needs action (§7.6). A step cannot be marked done while a mandatory field
is ⚠ or an ambiguous field is ◐ (FR-16, BR-02/03).

---

## 3. The agent must extract from ANY request — the general model

The agent is **not** a set of hardcoded phrase matchers. It fills a **flexible intent schema** and
reconciles it against reference data + the catalogue + the deterministic engine.

### 3.1 The intent schema (extensible slots + constraints)

```
IntentExtraction {
  partner:        { name?, number?, channel? }
  business_line?:  string            # mapped to reference data
  product?:        string            # mapped to reference data
  asset_category?: PKW|Equipment|NFZ|ITK
  asset_filters:   { seats?, fuel?, transmission?, body?, power?, ... }   # arbitrary attribute filters
  commercial:      { quantity?, term_months?, mileage_km?, special_payment?, insurance?, services[] }
  constraints:     [ { kind: budget|monthly_cap|delivery|..., value, currency?, basis? } ]  # freeform
  ambiguities:     [ { field, reason, options? } ]     # → ◐ Requires confirmation
}
```

- **Known slots** map to wizard fields.
- **`asset_filters`** are open-ended attribute filters (seats, fuel, colour…) → narrow the catalogue.
- **`constraints`** capture things that aren't direct offer parameters (a budget, a monthly cap) →
  drive **scenario generation**, not a single field.
- **`ambiguities`** are surfaced as ◐ confirm prompts — never silently resolved (BR-03).

### 3.2 Worked example — *"I need 4 seater 30 insured cars — my budget is $300k."*

| The agent extracts | Into |
|---|---|
| "cars" | `asset_category = PKW` |
| "4 seater" | `asset_filters.seats = 4` → filter PKW catalogue to 4-seaters |
| "30 … cars" | `commercial.quantity = 30` |
| "insured" | `commercial.insurance = all 30` |
| "budget is $300k" | `constraints += { kind: budget, value: 300000, currency: "$"→ambiguous, basis: total?/monthly?→ambiguous }` |

The agent then, on the **left wizard**:
1. Pre-fills Asset category = PKW, quantity = 30, insurance = on, and filters assets to 4-seaters.
2. Leaves **Partner, Business Line, Product** as ⚠ needs-action (not in the request) and asks for
   them in chat.
3. Flags the budget as **◐ requires confirmation** in chat: *"Is €300k the total acquisition budget
   or a monthly cap, and is that USD or EUR?"* (currency + basis ambiguous → BR-03).
4. Once basis is known, treats the budget as a **constraint on scenario generation**: it proposes
   candidate 4-seater configs, the **deterministic engine prices each** (30 units + insurance), and
   the agent surfaces **which configurations fit within €300k** — with the differences explained
   (§5 COMPARE, FR-24–27).

### 3.3 The guardrail that never bends

**AI assists · Rules decide · Humans govern.** The agent *extracts, filters, proposes and explains*
— it **never computes the price or decides budget-fit itself**. Every euro comes from the
deterministic engine (BR-06/07/08); the agent only arranges candidates and narrates the result.
Budget-fitting = "agent proposes N candidate configs → engine prices them → agent shows which pass."

---

## 4. What each side does, precisely

**Left (wizard, 60%)** — the record of truth the salesperson can read and edit directly:
- Structured fields per step with the 4 info states and confirm gates.
- Live outputs: resolved partner, product parameters, matched asset + specs, price breakdown,
  scenario cards, exceptions, readiness pill.
- Manual edits allowed at any unlocked step (mutable-until-generate) → re-runs affected
  calc/validation (FR-17/29/40, BR-05).

**Right (agent chat, 40%)** — the natural-language surface:
- Free-form intake and clarification in either language (DE/EN later).
- Each agent action shows an **"applied to the offer"** chip (which step/field it touched) so the
  chat and wizard never drift.
- Explanations on demand: "why this price?", "what changes if term = 48?", "why is it blocked?"
  (§5 EXPLAIN, FR-30–34).
- Asks — never assumes — for missing (⚠) and ambiguous (◐) items.

---

## 5. Build implications (for when we start coding)

- **Backend:** generalize `ExtractedIntent` into the flexible schema above (open `asset_filters` +
  `constraints` + `ambiguities`); the resolver maps slots → reference data / catalogue keys
  deterministically (LLM never invents identifiers — existing rule). Scenario generation must accept
  a **constraint set** (e.g. budget) and return engine-priced candidates ranked by fit.
- **Graph:** the intake chat loop stays, but now populates the full hierarchy; add per-step confirm
  interrupts and the pre-Generate human-review gate.
- **Frontend:** replace the mode-driven single column with the **60/40 split shell**; left = stepper
  wizard bound to offer state, right = persistent `AgentChat`; both subscribe to the same snapshot +
  SSE feed.

---

## 6. Next step
Proposed: build a **visual mockup of this 60/40 workbench first** (as with the prior approved
mockup), covering the empty wizard, a partially-extracted state from the `$300k` scenario, an
ambiguity-confirm moment, and a priced/budget-fit state — then port it screen-by-screen. Awaiting
your go before building the mockup or touching code.
