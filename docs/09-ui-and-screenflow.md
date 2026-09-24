# 09 — UI & Screen Flow (FD)

> Design of the Next.js frontend, derived from docs/01–08 and our LangGraph workflow. Principle:
> **the UI is a live window into the Offer Case, never a black box.** Every fact we hold in the
> DB/API — provenance, calculation breakdown, scoring factors, exceptions, audit, and the agent's
> live progress — is surfaced to the user in context.

---

## 1. Stack
- **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui** (mirrors the Agentic Ticket FE).
- **TanStack Query** for fetching/snapshots; **SSE** (EventSource) for the live agent feed.
- Typed API client to the FastAPI backend (`BE`, CORS already enabled).

## 2. The mental model the UI must convey
One **Offer Case** moving through a state machine. The header always answers the four questions
(docs/01): *Where am I? What do we know? What needs attention? What can I do next?* The workflow
status + `next`/`interrupts` from the API drive which action is live.

```
DRAFT → UNDERSTANDING → CONTEXT_REQUIRED → CONTEXT_COMPLETE → READY_FOR_CALCULATION →
CALCULATED → SCENARIOS_AVAILABLE → SCENARIO_SELECTED → PENDING_HUMAN_REVIEW →
APPROVED/RETURNED → FINAL_VALIDATION → READY/REQUIRES_ACTION/BLOCKED → OFFER_GENERATED
```

## 3. Screens (one workbench, many views of one Offer)

| # | Screen | Purpose | API |
|---|---|---|---|
| 1 | **Inbox** | List offers (status, band, value, next action) + review queue; New Offer | `GET /offers` |
| 2 | **Intake (conversational)** | NL request → agent understands → **chat**: agent asks for missing/ambiguous, user replies in plain language or edits catalogue picks → confirm | `POST /offers/nl`, `POST /offers/{id}/intake` (message/confirm/overrides), `GET /catalogue/*` |
| 3 | **Workspace** | The hub: live offer with context, activity, transparency panels | `GET /offers/{id}`, SSE |
| 4 | **Scenarios** (in Workspace) | Compare 24/36/48/60, AI advisory, select one | `POST /offers/{id}/select` |
| 5 | **Review** (in Workspace) | Reviewer sees everything; approve/return (four-eyes) | `POST /offers/{id}/review` |
| 6 | **Output** | Final outcome + generated offer (PDF in Phase 5), download | `GET /offers/{id}` (+ output) |
| 7 | **Audit** (tab) | Full event timeline | `GET /offers/{id}/audit` |

Screens 3–7 are **panels/tabs of one Workspace page**, not separate apps — the user never loses
the offer context.

## 4. The Workspace layout (the heart)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ HEADER: OFF-XXXX · [status stepper] · Band ●GREEN · €654/mo · Outcome: READY     │
│         Policy: DE_PKW_V1 (illustrative, not production)        [role switch]     │
├──────────────────────┬───────────────────────────────┬──────────────────────────┤
│ CONTEXT (left)       │ STAGE (center, follows status)│ TRANSPARENCY (right)      │
│  Customer  ▸ chips   │  - Intake confirm form         │  ▸ Agent Activity (LIVE) │
│  Vehicle   ▸ chips   │  - Scenario comparison         │  ▸ AI explanation (badge)│
│  Commercial▸ chips   │  - Review panel                │  ▸ How this was computed │
│  each field:         │  - Blocked / result view       │  ▸ Risk factors          │
│  value·status·source │                                │  ▸ Exceptions            │
│                      │                                │  ▸ Audit timeline        │
└──────────────────────┴───────────────────────────────┴──────────────────────────┘
```

- **Status stepper**: the pipeline nodes as steps; each lights up as it completes (fed by SSE).
- **Context chips** carry **provenance**: `Term 36m · CONFIRMED · USER`, `Residual 55.5% · DE_PKW_RV_V1`,
  `List price €37,800 · SEED`, `Customer · VIES/REGISTER`. Colour by status
  (green=established/confirmed, amber=inferred/requires-confirmation, grey=missing, red=invalid).
- Distinguishing known / AI-inferred / missing directly delivers "never silently convert
  uncertainty into truth" (docs/13 principle) — the user always sees where a value came from.

## 5. The real journey (happy path, B2B)

1. **Inbox → New Offer.** User types: *"Lease a BMW X1 for Musterlogistik, 36 months, ~20k km, keep the monthly low."*
2. **AI understands** (live feed: "Understanding request…"). Intake shows **proposed fields with confidence** and a resolved vehicle/customer candidate. User reviews, edits if needed, **Confirm** → fields become CONFIRMED.
3. **Pipeline runs live**: feed streams "Assembling customer & KYC…", "Residual 55.5% (HIGH)", "Scoring… GREEN 87.2", "Funding 3.50% + margin 1.75% = 5.25%", "Monthly €711 gross". The center fills in as each completes — **the user watches the reasoning**, not a spinner.
4. **Scenarios** appear (24→€806 … 60→€620) with the **AI advisory** ("48M stays Green and lowers the monthly"). User **selects** one.
5. **Review**: submitted → the reviewer (different user) opens the Review panel: full context, calculation breakdown, risk factors, exceptions, the selected scenario, and an AI review summary. **Approve** → offer generated. (Four-eyes below.)
6. **Output**: READY, offer document, download. Audit tab shows the whole trail.

## 6. Human-in-the-loop — how each pause is presented

The API tells the UI exactly where it paused via `next` + `interrupts[].type`. The UI renders the
matching action and **disables everything else**:

| Interrupt | Screen shown | Action | Who |
|---|---|---|---|
| `confirm_intake` | Intake confirm form (proposed fields, confidence) | Confirm/Edit → `POST /confirm` | Sales |
| `select_scenario` | Scenario comparison + AI advisory | Pick one → `POST /select` | Sales |
| `review_required` | Review panel (full picture + AI summary) | Approve / Return → `POST /review` | Reviewer/Approver |

Because LangGraph **persists** the pause, the user can close the tab and resume later — the
Workspace reloads the exact pending step from `GET /offers/{id}`.

## 7. Edge cases & scenarios (each has a real UI, not an error toast)

| Scenario | What the user sees |
|---|---|
| **Missing/unconfirmed data** | Confirm form highlights missing fields; "Continue" disabled until provided; grey MISSING chips |
| **RED — compliance** (sanctions/KYC) | Red **BLOCKED** banner + hard-block reasons ("Sanctions match", "KYC failed"); no price, no scenarios, **no override**; explanation of why |
| **RED — economic** (over-exposed/affordability) | BLOCKED banner **+ AI-suggested alternatives** (cheaper car / higher special payment / shorter term); one-click "Try alternative" re-runs |
| **YELLOW** | Priced but amber-flagged; routed to Review; Review panel shows the yellow reason + risk factors; approver approves or returns |
| **Special payment too high** | Inline exception "reduce down payment"; the field is flagged; pricing withheld |
| **Term / mileage out of range** | Validation chip on the field; pricing blocked until corrected; allowed range shown |
| **Four-eyes** | On the Review panel, if current user = creator, **Approve is disabled** with a tooltip ("creator can't approve — four-eyes"); backend 409 is the backstop, surfaced as a friendly message |
| **Return for modification** | Status → RETURNED; Workspace routes back to editable intake; a banner shows the reviewer's comment; re-run starts a fresh pass |
| **External source mocked/unavailable** | A **source badge** (LIVE / SANDBOX / MOCK) on customer/credit panels, from provenance `source_type` — the user knows the data's origin |
| **High-value (>€100k)** | Amber "manual review" note; still priced; flagged for approver |

## 8. Real-time transparency (the "not a black box" requirement)

**A. Live agent feed (SSE).** A new backend endpoint streams `graph.stream(...)` node updates as
Server-Sent Events. Each node emits a human-readable line + the values it produced:
```
▸ understand        parsed: BMW X1, 36m, 20k km, minimize monthly
▸ confirm_intake    (awaiting your confirmation)
▸ run_pipeline      residual 55.5% (HIGH) · risk GREEN 87.2 · rate 5.25% · €711 gross
▸ scenarios         4 options priced (24/36/48/60)
▸ explain_scenarios AI: "48M stays Green, lowers monthly vs 36M"
```
This is the core of "show what's happening in the background."

**B. Transparency panels (all data we hold, surfaced):**
- **How this was computed** — the full chain: reference rate → funding → margin → finance rate →
  NetCap → PV(residual) → base lease → net → +VAT → gross, plus the **policy versions**
  (`ResultEnvelope.policies`) and `inputs_digest`. Nothing hidden.
- **Risk factors** — band + score + each weighted factor's contribution + any hard blocks
  (from `ScoringResult`).
- **Exceptions** — typed list: code, severity, blocking, required role, next action.
- **Provenance** — every field's value/status/source/confidence (context chips).
- **Audit timeline** — who/when/what for every state change (append-only `audit_events`).
- **Policy banner** — DE_PKW_V1 is an illustrative MVP policy, stated up front.

## 9. Backend additions needed for the UI (small, planned)
1. **SSE run endpoints** — `POST /offers/nl/stream`, `POST /offers/{id}/{advance}/stream` using
   `graph.stream` to emit per-node events (real-time feed).
2. **`GET /offers/{id}/audit`** — the audit trail (already in `repository.audit_trail`).
3. **`GET /offers/{id}/detail`** — full provenance + scoring factors + calculation breakdown
   (currently summarised; expose the full `ResultEnvelope`s).
4. Keep existing create/confirm/select/review/list endpoints.

## 10. Roles (mocked personas for the MVP)
A role switcher (Sales / Reviewer / Approver) in the header, matching `users`. Sales creates,
confirms, selects, submits (cannot approve). Reviewer/Approver see the review queue and
approve/return within authority; four-eyes enforced. Agent actions never exceed the current
user's permissions (docs/05).

## 11. Build order (once approved)
1. Scaffold Next app in `FD/` (App Router, Tailwind, shadcn/ui) + typed API client.
2. Backend SSE + audit/detail endpoints.
3. Inbox → Intake (NL + confirm) → Workspace shell (header, 3 columns).
4. Live agent feed (SSE) + status stepper.
5. Scenarios panel + selection; Review panel + approve/return (four-eyes).
6. Transparency panels (compute breakdown, risk factors, provenance chips, audit).
7. Edge-case views (blocked/compliance/economic/returned) + source badges.
8. Output view (offer summary; PDF once Phase 5 lands).
9. End-to-end wire-up against Neon; bilingual labels (EN/DE).
```
