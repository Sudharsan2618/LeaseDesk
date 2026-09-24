# 03 — Data Sources & Integration (every piece, its I/O, its MVP treatment)

> The purpose of the API research (Turns 3 & 5) was **to get a public *structure* for the data,
> not to depend on paid vendors.** For the MVP: use free/live data where it exists, mock/sandbox
> everything else, and hide all of it behind adapters with a `LIVE / SANDBOX / MOCK` switch so the
> Offer workflow never changes when a source is swapped.
>
> ⚠️ Every capability/field/endpoint below was asserted by the prior research chat and is **not
> re-verified here**. Treat it as the *intended contract*; verify against the live source before
> depending on it ([08](08-open-questions-and-verification.md)).

---

## 1. The universal adapter contract

Every integration implements the same shape so the engine is source-agnostic:

```python
class SourceAdapter(Protocol):
    name: str                      # "KBA", "VIES", "CRIF", ...
    source_type: SourceType        # OPEN_OFFICIAL | EXTERNAL_PROVIDER | CONTROLLED_REFERENCE_DATA
    mode: Literal["LIVE","SANDBOX","MOCK"]
    def fetch(self, request) -> ProvenanceValue | ResultEnvelope: ...
```

- `LIVE` → real call to the free/official source.
- `SANDBOX` → provider's UAT/trial environment (dummy but realistic data).
- `MOCK` → local fixture JSON (identical response shape). **Fallback whenever credentials are slow.**

Switching modes must **not** change the response schema or the workflow — only the data's origin
(recorded in provenance).

---

## 2. Source inventory (deduplicated master table)

| # | Source | Class | Provides | MVP treatment | Auth |
|---|---|---|---|---|---|
| 1 | **KBA / GovData** | 🟢 | HSN/TSN, manufacturer, trade-name (German ref) | LIVE | none |
| 2 | **EEA CO₂ dataset** | 🟢 | full vehicle *structure* (type/variant/version, category, fuel, engine, mass, WLTP, CO₂) + SQL REST | LIVE | none |
| 3 | **NHTSA vPIC** | 🟢 | VIN decode (used vehicles) | LIVE fallback | none |
| 4 | **Bundesbank / ECB (SDMX)** | 🟢 | reference interest-rate series | LIVE | none |
| 5 | **EU TEDB** | 🟢 | VAT rate by country/date (SOAP) | LIVE | none |
| 6 | **VIES** | 🟢 | EU VAT-ID validate (SOAP) → valid + identity | LIVE | none |
| 7 | **EU consolidated sanctions list** | 🟢 | sanctions entries (CSV/XML) | LIVE / local cache | none |
| 8 | **Unternehmensregister** | 🟢 | company register extract (XML "SI") | FIXTURE/MOCK (no public REST search) | free retrieval |
| 9 | **Bundesbank bank sort codes** | 🟢 | bank exists / routing / BIC / IBAN structure | LIVE (optional) | none |
| 10 | **Zoll** | 🟢 | vehicle-tax CO₂/engine rules | LIVE (only if lease includes vehicle tax) | none |
| 11 | **OpenSanctions** | 🔵 | sanctions/PEP fuzzy `/match` | SANDBOX (30-day trial) | business email |
| 12 | **CRIF Developer UAT** | 🔵 | KYC + credit (company, reps, UBO, PEP, sanctions, credit index, limit) | SANDBOX | free signup (UAT client id/secret) |
| 13 | **Creditsafe** | 🔵 | credit/risk (test DB, OpenAPI) | SANDBOX (alt) | trial |
| 14 | **JATO** | 🔵 | new-car catalogue, trim, options, build rules, pricing, incentives | NOT USED in MVP (EEA replaces the structure) | commercial |
| 15 | **DAT / SilverDAT** | 🔵 | residual value, VIN, finance calc | NOT USED in MVP (our RV policy replaces) | commercial |
| 16 | **Autovista** | 🔵 | residual/valuation | NOT USED (alt to DAT) | commercial |
| 17 | **mobile.de** | 🔵 | used-market asking prices (evidence only) | OPTIONAL | dealer/API account |
| 18–n | **SCHUFA / Creditreform** | 🔵 | credit bureau | NOT USED in MVP (CRIF/Creditsafe sandbox or mock) | commercial |

**Client-controlled (🟣) has no external source** — it is authored as `DE_PKW_V1`
([05](05-mvp-reference-policy.md)).

---

## 3. Per-source I/O contracts (the ones the MVP actually calls)

### 3.1 Vehicle structure — EEA CO₂ dataset (LIVE) + KBA (LIVE)
```
IN : { make?, commercial_name?, fuel_type?, ... free-text or filters }
OUT: Vehicle[] where each field is a ProvenanceValue{source:"EEA"|"KBA", source_type:OPEN_OFFICIAL, status:ESTABLISHED}
     (make, commercial_name, type, variant, version, type_approval_number, vehicle_category,
      fuel_type, engine_capacity_cc, engine_power_kw, mass_kg, wltp_co2_g_km,
      electric_consumption_wh_km, hsn, tsn)
SEED: list_price_net/gross (no authoritative free price → seed/mock, status:ESTABLISHED source:"SEED")
```
This gives the **official domain shape** for the Asset object. Purpose = structure + dataflow.

### 3.2 VIN decode — NHTSA vPIC (LIVE, used vehicles only)
```
IN : { vin }
OUT: { make, model, year, ... } → reconcile against EEA structure; status:ESTABLISHED source:"NHTSA"
```

### 3.3 VAT-ID validation — VIES (LIVE, B2B)
```
IN : { vat_id }            e.g. "DE123456789"
OUT: { valid: bool, name?: string, address?: string }
     → sets customer.vat_id.status = INVALID if !valid, else CONFIRMED
```

### 3.4 Sanctions — EU list (LIVE/cache) + OpenSanctions `/match` (SANDBOX)
```
IN : { names: [customer, directors[], ubo[]] }
OUT: { match: bool, hits: [{name, list, score}] }
     match==true → Exception SANCTIONS_MATCH (hard, RED-compliance, never override)
```

### 3.5 KYC — CRIF UAT (SANDBOX) → fixture (MOCK)
```
IN : { company_ref | person_ref }
OUT: { identity: {verified:bool, ...}, representatives[], ubo[], pep:{match:bool}, kyc_status }
     failure → Exception KYC_FAILED (hard)
```

### 3.6 Credit — CRIF/Creditsafe (SANDBOX) → deterministic mock (MOCK)
```
IN : { customer_ref, requested_exposure }
OUT (raw bureau): { score, default_probability, recommended_limit, negatives[] }
     ⚠ this is an INPUT only — it does NOT decide G/Y/R. The MVP Risk Engine maps it. See §4.
```

### 3.7 Reference rate — Bundesbank/ECB SDMX (LIVE)
```
IN : { series_id, as_of_date }
OUT: reference_rate (%)   ProvenanceValue{source:"BUNDESBANK", source_type:OPEN_OFFICIAL}
     ⚠ reference only — NOT the funding rate. Funding policy adds spreads. See [04].
```

### 3.8 VAT rate — EU TEDB (LIVE) with §12 UStG fallback
```
IN : { country:"DE", date }
OUT: vat_rate (%)  (DE standard = 19%)  → stored on the Offer's CalculationResult
```

---

## 4. The KYC / sanctions / credit dataflow (mock/sandbox — understand it, don't productionize it)

```
Customer
   │
   ▼
KYC Adapter (CRIF UAT | fixture)  ──► IdentityResult ─── fail ──► Exception KYC_FAILED (hard)
   │
   ▼
Sanctions Adapter (EU list | OpenSanctions trial | fixture) ──► SanctionsResult ── match ──► Exception SANCTIONS_MATCH (hard)
   │
   ▼
Credit Adapter (CRIF/Creditsafe sandbox | deterministic mock) ──► CreditResult {score, PD, limit}
   │
   ▼
MVP RISK ENGINE  ← the only place G/Y/R is decided (client-controlled policy DE_PKW_RISK_V1)
   │
   ▼
ScoringResult { mvp_risk_score, band, red_kind, factor_breakdown }
```

**The critical boundary** (repeated in the source): external providers give *inputs* (score, PD,
recommended limit, sanctions hit). The **mapping to GREEN/YELLOW/RED and to approve/review/block
is client-controlled policy** — for the MVP it lives in `DE_PKW_RISK_V1`, never in the LLM, never
copied from the bureau's own score. Detail in [04](04-calculation-logic.md) §risk and
[05](05-mvp-reference-policy.md).

---

## 5. Deterministic mock design (so demos are repeatable)

"Simulated" must be a **predictable rule**, never `random.choice(...)`. Every mock adapter derives
its output deterministically from the input (e.g. hash the customer id → a stable score band; map
known fixture companies → fixed KYC/credit outcomes) so the same demo always yields the same
result and negative flows can be triggered on demand.

Suggested fixture personas to seed (to exercise every branch):
- `GREEN B2B` clean company, mid exposure → GREEN.
- `YELLOW B2B` new company / high value → YELLOW → review.
- `RED-economic` poor affordability / over-exposure → RED with alternatives.
- `RED-compliance` sanctions hit or KYC fail → BLOCKED, no alternatives.
- `B2C GREEN` and `B2C YELLOW` (affordability edge).

---

## 6. What is genuinely LIVE in the MVP vs mocked

```
LIVE (real calls, free, no key)                 SANDBOX (trial/UAT)         MOCK (fixtures)
────────────────────────────────                ────────────────────        ────────────────────
EEA vehicle structure                            OpenSanctions /match        company register (SI XML)
KBA HSN/TSN                                       CRIF UAT (KYC+credit)       credit bureau (deterministic)
NHTSA VIN (used)                                  Creditsafe (alt)            workflow approval backend
Bundesbank/ECB reference rate                                                 e-sign / delivery
EU TEDB VAT rate                                                              vehicle list price (seed)
VIES VAT validation
EU sanctions list
(Bundesbank bank codes, Zoll — optional)
```

Everything mocked keeps the **exact response schema** of its live/sandbox counterpart, so
switching `mode="LIVE"` later is a config change, not a rewrite.

---

## 7. Integration checklist before writing engine code

- [ ] Define the `ProvenanceValue` and `ResultEnvelope` types (they are the contract for every adapter).
- [ ] Write the `SourceAdapter` protocol + a registry keyed by `name`, each with its `mode`.
- [ ] For each LIVE source (§3.1–3.8): capture a real sample response, save it as the MOCK fixture, and pin the field mapping.
- [ ] For each SANDBOX source: obtain credentials *or* start on the MOCK fixture with the same schema.
- [ ] Ensure every adapter tags `source` + `source_type` + `retrieved_at` on its output.
- [ ] Add an `EXTERNAL_SERVICE_UNAVAILABLE` exception path (adapter throws → engine records exception, does not fabricate a value).
- [ ] Confirm no adapter output ever reaches the calculation with status other than `ESTABLISHED`/`CONFIRMED`.
