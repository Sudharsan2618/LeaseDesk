# 12 — Business Logic Bookmark & Gap Analysis

> **Purpose.** A break from development. This bookmarks the business logic that the client spec
> ([11-client-spec-extract.md](11-client-spec-extract.md)) actually requires, and marks — honestly —
> where the current BE/FD build diverges. **Read this before touching the calculation again.** No
> code is being changed by this document.

---

## 0. The three things you called out — confirmed against the spec

### A. "Why are we sticking with cars? This is B2B — it can be anything, right?" — **Correct.**

The spec never says "car leasing." §3.6 lists **four asset categories**:

- **PKW** (passenger cars)
- **Equipment**
- **NFZ** (commercial vehicles)
- **ITK** (IT & communications)

And §3.5 puts **two selection layers above the asset**:

1. **Business Line** selection
2. **Leasing Product** selection

The Business Line + Leasing Product **determine the Offer Parameters and product-specific rules**
(permitted terms, eligibility, calculation inputs, scenario constraints) — pulled from **controlled
Offer Reference Data**, not hardcoded and not decided by the Agent (§3.5, §5.5, BR-08, BR-09).

**What this means for us:** the domain must be **asset-category-agnostic**. Business Line, Leasing
Product and Asset Category are *first-class selectable entities driven by reference data* — not
baked-in "PKW/car" semantics. The spec *does* allow using **one representative scenario** for the
2–3 week demo (§9.5 "one representative Offer scenario is sufficient"), so PKW can remain the *seed
demo data* — but the **structure, selection flow and reference-data model must be generic**. Today
we hardcoded car concepts (vehicle make/model/colour/fuel/hp) into the core; that's the mistake.

### B. "Everywhere the system must ask confirmation — human-in-loop — this is missing." — **Correct.**

Confirmation and human-in-loop are pervasive requirements, not optional polish:

- **Per-screen Confirm gates** (§10): Intake → *Confirm extracted info*; Customer Context →
  *Confirm*; Asset+Product → confirm config; Pricing → *Select scenario*; Review → *Generate*.
- **Four information states on every field** (§7.6): ✓ Established · ✓ Confirmed · ◐ Requires
  confirmation · ⚠ Missing/needs action.
- **BR-02/BR-03:** missing info is never treated as confirmed; **ambiguous info requires user
  confirmation before it is used** for a material outcome.
- **FR-03/FR-04/FR-05:** present the interpreted requirement for confirmation; flag ambiguity; allow
  correction *before proceeding*.
- **Dedicated Human Review step** (§9.10 Step 08 + Screen 06 + Screen 07; FR-35…FR-40; BR-15…BR-19):
  human review is **required before final generation** and is **controlled iteration** — a material
  change returns the Offer to an earlier stage and forces reassessment.
- **§9.14** three-control model: *Agentic assistance / Deterministic control / Human decision.*

### C. What's missing / wrong in the current state — see the gap table in §2 below.

---

## 1. The canonical business logic to lock (the "bookmark")

### 1.1 The motto that governs everything
> **AI assists. Rules decide. Humans govern.** (§2.6)

- **Agent (LLM):** understand, assemble, identify gaps, orchestrate, compare, recommend, explain.
- **Deterministic engine + reference data:** all pricing, eligibility, thresholds, validation.
- **Human:** confirms context, resolves exceptions, reviews and approves before generation.

### 1.2 The six interventions (functional backbone) — §5
`UNDERSTAND → ASSEMBLE → VALIDATE → ORCHESTRATE → COMPARE → EXPLAIN`

### 1.3 The ten process steps (the single spine) — §9
`01 Initiate → 02 Establish Context → 03 Configure → 04 Check Completeness → 05 Calculate/Assess →
06 Generate Scenarios → 07 Review Outcomes → 08 Human Review → 09 Validate → 10 Generate` ⇒
**decision-ready Offer**. Stop point is the generated Offer; **no contract creation**.

### 1.4 The selection hierarchy (this is the part we skipped) — §3.4–3.6
```
Channel (Internal Sales | Partner Sales | Credit Partner)
  └─ Customer / Partner   (Offer Partner vs Business Partner, per channel; search/create; dedupe)
       └─ Business Line                      ← reference data
            └─ Leasing Product               ← reference data → defines Offer Parameters & rules
                 └─ Asset Category (PKW | Equipment | NFZ | ITK)
                      └─ Asset / Object + attributes
                           └─ Commercial requirements (term, mileage/usage, payment, quantity…)
```

### 1.5 Scoring model — §3.11–3.12
- Two patterns: **Automatic** (params match predefined process) vs **Manual/Intervention**.
- Outcome: **Green / Yellow / Red** → drives the path.
- **Red** = cannot proceed on the normal path; needs a new Offer/variant.
- **Yellow** = **UNDER-SPECIFIED in the source → validate with client, do not assume.** *(open Q)*

### 1.6 Readiness states — §12.5 / FR-45
`READY` (all conditions met incl. human review + confirmed scenario) · `REQUIRES ACTION`
(correctable issue) · `BLOCKED` (mandatory condition prevents progression).

### 1.7 Cross-cutting requirements we under-weighted
- **Authorization sets / roles** (mocked): View · Edit · Review · Approve · Restricted (§10.2,
  FR-59…FR-61). *Note: this is the client's model; reconcile with our earlier "single actor"
  decision — see §3 open question.*
- **Bilingual (two languages, DE/EN)** for UI, workflow messages, validation, Agent explanations
  (§10.2, FR-63, AC-18).
- **Audit / traceability** as a first-class capability (Screen 08; FR-54…FR-58; AC-15).
- **Negative-workflow messaging:** WHAT → WHY → WHAT next (§10.2, FR-62).
- **Asset assessment** as a distinct simulated outcome (§3.7, FR-19), including "assessment
  unavailable ⇒ cannot progress."
- **Document/Offer output** as a representative generated artifact (§10.9, FR-47…FR-53).

---

## 2. Gap analysis — spec vs. current build

Legend: ✅ built · 🟡 partial / car-specific · ❌ missing.

| Spec area | Requirement | Current state |
|---|---|---|
| **Asset generality** | 4 asset categories; Business Line + Product drive params (§3.5–3.6) | ❌ Hardcoded PKW/car (make/model/colour/fuel/hp) in domain, engine, fixtures |
| **Business Line selection** | Select Business Line (§3.5, FR-08) | ❌ Absent |
| **Leasing Product selection** | Select Product → defines Offer Parameters (§3.5) | ❌ Absent (we jump straight to a vehicle) |
| **Offer Reference Data** | Controlled reference set drives rules/params (§5.5) | 🟡 We have `de_pkw_v1.json` policy, but it's a car policy, not a generic Business-Line/Product reference-data model |
| **Channels** | Internal Sales / Partner Sales / Credit Partner (§3.3) | ❌ Single implicit sales actor |
| **Partner model** | Offer Partner vs Business Partner; search/create; dedupe (§3.4, FR-06, Screen 03) | 🟡 We have a customer catalogue + register lookup; no channel distinction, no duplicate detection, no Customer Context screen |
| **Six interventions** | Understand/Assemble/Validate/Orchestrate/Compare/Explain (§5) | ✅ Understand/Validate/Compare/Explain via LangGraph; 🟡 Assemble (limited); ✅ Orchestrate |
| **Ten-step spine** | §9 | 🟡 We have intake→pipeline→scenarios→gate→validate→generate; missing explicit Context, Configure, Asset+Product, distinct Human Review as its own controlled stage |
| **Per-screen confirmation** | Confirm at intake/context/config/pricing/review (§10, FR-03) | 🟡 Intake confirms; other confirm gates thin/absent |
| **4 info states** | Established/Confirmed/Requires-confirmation/Missing (§7.6) | 🟡 We have provenance (value/status/source/confidence); not mapped to these 4 UI states |
| **Human Review step** | Required before generation; controlled iteration (§9.10, FR-35–40, BR-15) | 🟡 We *removed* the approver earlier (single-actor mutable gate). Spec wants an explicit review gate — reconcile (§3) |
| **Scoring Green/Yellow/Red** | Auto vs manual; Red blocks; Yellow TBD (§3.11–12) | 🟡 We have risk bands + outcomes; verify mapping to Green/Yellow/Red + auto/manual patterns; Yellow rule still open |
| **Asset assessment** | Distinct simulated outcome; can block (§3.7, FR-19) | ❌ Not modeled as its own step/outcome |
| **Authorization / roles** | View/Edit/Review/Approve (mocked) (§10.2, FR-59–61) | ❌ Not implemented (we deliberately dropped roles) |
| **Bilingual DE/EN** | UI + messages + explanations (FR-63, AC-18) | ❌ English only |
| **Screens** | 7 core + 1 audit (§10) | 🟡 We have Inbox, New Offer, Workspace (modes). Missing dedicated Customer Context, Asset+Product, Credit/Approval, Review+Output, Audit screens |
| **Negative-workflow messaging** | WHAT→WHY→WHAT next (FR-62) | 🟡 Some banners; not systematic |
| **Audit trail** | First-class (Screen 08, FR-54–58) | ✅ Append-only audit + timeline exists |
| **Deterministic engine** | Controlled calc; Agent never prices (BR-06–08) | ✅ Solid — but coupled to car list-price semantics |
| **Offer output artifact** | Representative generated Offer (FR-47–53) | 🟡 We produce a summary; not a document-style artifact |

**Headline:** the *engine, LangGraph orchestration, persistence and audit are genuinely aligned with
the spec's control model.* The divergence is **upstream** — we collapsed the
**Channel → Partner → Business Line → Product → Asset Category → Asset** selection hierarchy into a
single "pick a car" step, and thinned out the **confirmation + human-review** gates.

---

## 3. Decisions (resolved with the user 2026-09-23)

1. **Asset generality — DECIDED: generic domain + PKW seed.** Refactor Business Line / Leasing
   Product / Asset Category into **reference-data-driven entities**; keep **PKW as the working demo
   dataset**. Honors spec §3.5–3.6 while using the §9.5 "one representative scenario" allowance. The
   car-specific concepts (make/model/colour/fuel/hp) become *attributes of the PKW asset category*,
   not core domain types.
2. **Roles / human review — DECIDED: single actor + explicit review gate.** Keep one internal sales
   user. Add a **mandatory "Review & confirm" gate before Generate** that satisfies BR-15 / FR-44 in
   spirit (no second persona). Full View/Edit/Review/Approve role model is *not* built now.
3. **Yellow scoring — DECIDED: Yellow → REQUIRES ACTION / human review.** Green proceeds; **Red
   blocks**; **Yellow routes to the human-review gate as a REQUIRES ACTION state.** Consistent with
   §12.5 readiness states. (Still flag to client that the spec left Yellow under-specified.)

### Still open (lower stakes — default recommendation noted)
4. **Bilingual (DE/EN).** *Recommend:* build the structure English-first, layer DE i18n after the
   generic domain + screens land (FR-63 is a demonstration requirement, not a blocker for the spine).
5. **Screen set.** *Recommend:* keep ONE Offer workbench (§10.12 says the screens are views/states of
   one workbench, not 8 apps) and express Customer Context / Asset+Product / Credit-Approval /
   Review-Output as **sections/modes** within it, adding the dedicated confirm gates each screen
   requires.

---

## 4. Re-architecture plan (approved decisions applied — sequenced)

Adopt docs 11 & 12 as source of truth above docs 02–10 where they conflict. Then, in order:

1. **Generalize the reference-data model** — introduce `BusinessLine`, `LeasingProduct`,
   `AssetCategory` (PKW/Equipment/NFZ/ITK) as reference-data entities; `LeasingProduct` carries the
   Offer Parameters/rules (term/payment/eligibility/calc inputs/scenario constraints). Re-house the
   current car fields as PKW asset attributes.
2. **Insert the selection hierarchy with confirm gates** — Channel → Partner (Offer vs Business,
   + dedupe) → Business Line → Leasing Product → Asset Category → Asset, each step confirmable.
3. **Add the explicit Human-Review gate** before Generate (single actor), with controlled iteration
   back to earlier stages on a material change.
4. **Map provenance → the 4 info states** (✓Established / ✓Confirmed / ◐Requires-confirmation /
   ⚠Missing) in the UI.
5. **Scoring + assessment** — confirm Green/Yellow/Red mapping (Yellow → Requires Action → review);
   model asset assessment as a distinct simulated outcome that can block.
6. **Only then revisit the calculation** to run against generic Leasing-Product parameters.
7. **Later:** DE i18n; representative Offer output artifact.

**Status:** decisions 1–3 locked (§3). Bilingual timing + screen structure use the recommended
defaults unless you say otherwise. No code has been written yet — awaiting your go on the plan.
