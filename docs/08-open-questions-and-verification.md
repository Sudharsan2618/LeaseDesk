# 08 — Decided vs Open, and What to Verify

> The point of this file: separate **settled decisions** (build on them) from **genuine open
> items** (don't guess) and **claims to verify** (don't trust the research chat blindly). Keep it
> updated as answers land.

---

## 1. Settled for the MVP (build on these)

| # | Decision | Source |
|---|---|---|
| D1 | Asset scope = German passenger cars (PKW), category M1 | Turn 2 |
| D2 | Languages = English + German | Turn 2 |
| D3 | Output = PDF (non-binding illustrative offer) | Turn 2 / Turn 5 |
| D4 | Jurisdiction = Germany (still to be *explicitly* confirmed with client) | Turn 3 |
| D5 | Primary product = **kilometre leasing** (`KILOMETER_LEASING`) | Turn 5 |
| D6 | Vendors are NOT a blocker; build end-to-end on free/trial/sandbox + a public data *structure* | Turn 4 |
| D7 | Client-controlled rules are authored by us as **`DE_PKW_V1`** (deterministic, versioned, replaceable) | Turn 4 / Turn 5 |
| D8 | Vehicle *structure* comes from the **EEA CO₂ dataset** (+ KBA for HSN/TSN) | Turn 5 |
| D9 | Stack intent = FastAPI + PostgreSQL + LangGraph + React/Next.js; JSONB data modules | Turn 1 / user |
| D10 | Scope ends at a decision-ready Offer — **no contract creation** | Turn 1 |
| D11 | AI assists → deterministic rules decide → humans govern; LLM never in calc/scoring/eligibility | Turn 1 (throughout) |

---

## 2. Genuine project choices we made (revisit if the client disagrees)

These were the ❌/YES "client must provide" items, now authored as MVP policy. If the client later
supplies real values, bump to a new policy version.

funding-rate model · commercial margin · lease formula · allowed terms · mileage bands ·
special-payment rules · residual-value policy · eligibility rules · Green/Yellow/Red mapping ·
Yellow treatment · approval limits · role permissions · exception/override rules · required
documents · PDF legal wording. (All specified in [04](04-calculation-logic.md) and
[05](05-mvp-reference-policy.md).)

---

## 3. Still open — decide before/while building (don't guess silently)

| ID | Question | Why it matters | Working assumption |
|---|---|---|---|
| Q-SCOPE-1 | B2B, B2C, or both for the MVP demo? | Drives required data, KYC depth, risk weights, legal controls (GDPR Art.22, §506 BGB) | Support **both** structurally; demo happy-path on **B2B** first |
| Q-SCOPE-2 | Confirm Germany as primary operating country | Legal/tax/data-source assumptions hinge on it | Germany |
| Q-CALC-1 | Residual value % applies to **list price** or **acquisition price**? | Changes `residual_value_amount` and every rental | Apply to acquisition/list base; **pick one and pin it** in `MVP_LEASE_CALC_V1` |
| Q-CALC-2 | Are recurring service fees / vehicle tax / insurance in the monthly rate for the MVP? | Full-service vs plain kilometre leasing changes the formula inputs | Plain kilometre leasing; service fees = €0 default, structurally supported |
| Q-CALC-3 | Reference-rate series to use from Bundesbank/ECB (which exact series id)? | The funding rate's base number | Pick one documented series; store its id in `funding.reference_rate_source` |
| Q-RISK-1 | Exact factor *inputs* for the mock credit/affordability (what mock fields feed the 40/25/… weights)? | Needed to make scoring deterministic and demoable | Define fixture personas ([03](03-data-sources-and-integration.md) §5) |
| Q-DEMO-1 | Which 3–5 negative flows must the demo show? | Shapes the fixtures and exception coverage | GREEN, YELLOW-review, economic-RED, compliance-RED, missing-data |
| Q-AUTH-1 | Real auth or mocked personas for the MVP? | Affects effort; roles/limits still needed either way | Mocked personas per role |

---

## 4. Claims from the research chat to VERIFY before depending on them

The prior chat asserted these with citations; **none are re-verified in this repo.** Verify the
specific capability/field/tier/endpoint against the live source before writing an adapter or making
a legal statement. (Use the browser/WebFetch tools when you're ready to check.)

**Data sources (verify the API exists, its auth, and the exact fields):**
- EEA CO₂ passenger-car dataset — SQL REST endpoint + the field list in [03](03-data-sources-and-integration.md) §3.1.
- KBA/GovData HSN/TSN dataset — format, freshness, license.
- Bundesbank/ECB SDMX — the exact rate series and access.
- EU TEDB — SOAP service for VAT rate by country/date.
- VIES — SOAP validate endpoint + what identity fields it returns.
- EU consolidated sanctions list — CSV/XML distribution + update cadence.
- NHTSA vPIC — VIN decode (US-centric; confirm coverage for EU vehicles or treat as fallback only).
- OpenSanctions — the 30-day business trial terms + `/match` contract.
- CRIF Developer UAT — signup, UAT client id/secret, sandbox data shape.
- Creditsafe — sandbox/test DB + OpenAPI availability.
- Unternehmensregister — confirm there is *no* free public REST search (chat said so) → fixture is correct.
- Transparency Register — confirm the API is restricted (eligibility/accreditation) → mock for MVP.

**Legal claims (verify wording/applicability; get legal sign-off before any production use):**
- §12 UStG (DE VAT 19%), §1/§32 KWG + BaFin (Finanzierungsleasing = regulated), GwG §10 (KYC
  duties), GDPR Art.22 (automated decisions), EU AI Act Annex III (credit scoring of natural
  persons), §506 BGB (consumer-credit applicability to leasing).
- These inform *controls and disclaimers*; the MVP's non-binding illustrative-offer stance keeps it
  out of contract territory, but confirm before claiming compliance anywhere user-facing.

**Domain figures used as policy seeds (label as MVP simulation, not market truth):**
- ADAC references (12–60m terms, ~36m/15,000 km typical, mileage↔rate relationship) — used only to
  make `DE_PKW_V1` *plausible*; they are not the client's numbers.

---

## 5. Doc-consistency items flagged in the source (ask the client / doc owner)

- "58 functional requirements" vs IDs extending to **FR-63** — reconcile the count.
- **AC-16 vs AC-17** — likely duplicate authorization acceptance criterion; confirm.

---

## 6. Suggested first working session agenda

1. Confirm D2/D4/D5 and answer Q-SCOPE-1, Q-CALC-1, Q-CALC-2, Q-DEMO-1 (these unblock the engine).
2. Freeze the `ProvenanceValue` + `ResultEnvelope` contracts ([02](02-domain-entities.md) §1).
3. Capture one real response per LIVE source → save as MOCK fixtures ([03](03-data-sources-and-integration.md) §7).
4. Implement + unit-test the deterministic engine against the [04](04-calculation-logic.md) §10 checklist — **no AI, no UI yet.**
5. Only then move to the workbench, then the agent, then LangGraph orchestration.
