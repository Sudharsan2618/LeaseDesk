# 05 — MVP Reference Policy `DE_PKW_V1`

> **Disclaimer (must appear in the technical docs and be carried in provenance):** *These rules
> constitute the controlled MVP reference policy used to demonstrate the Agentic Offer Creation
> process. They do NOT represent the production commercial/credit policy of any leasing company.*
>
> This is the 🟣 client-controlled layer that the client will not provide, authored by us as a
> deterministic, versioned, explainable, replaceable configuration. It lives in
> config/DB — **never in an LLM prompt**. The Agent reads it and explains it; it may not modify it.

---

## 1. Why a versioned policy object

- **Deterministic** — same inputs → same outputs; demos and tests are repeatable.
- **Explainable** — every number is named and traceable (`DE_PKW_FUNDING_V1`, etc.), so the Agent can say *why* a rental is what it is.
- **Replaceable** — when the client eventually supplies real policy, we bump to `DE_PKW_V2` (or a client-specific id); Offers pin the version they used (`offers.policy_version`).
- **Layered** — sub-policies (funding, margin, residual, risk) version independently so one can change without touching the others.

---

## 2. Master policy config (single source of the constants)

```jsonc
{
  "policy_id": "DE_PKW_V1",
  "country": "DE",
  "currency": "EUR",
  "product": { "vehicle_category": "M1", "lease_type": "KILOMETER_LEASING" },

  "term": { "min_months": 12, "max_months": 60, "step_months": 6, "preferred": [24, 36, 48, 60] },

  "mileage": { "baseline_annual_km": 15000, "min_annual_km": 5000, "max_annual_km": 40000, "step_km": 5000 },

  "special_payment": { "standard_max_pct": 20, "review_max_pct": 30 },   // >30% BLOCK

  "residual": {
    "base_term_rv_pct": { "12": 80, "24": 68, "36": 58, "48": 49, "60": 41 },
    "extra_5000km_penalty_pp": 2.5,
    "lower_5000km_bonus_pp": 1.5,
    "mileage_uplift_cap_pp": 5,
    "mileage_penalty_cap_pp": 15,
    "minimum_pct": 20,
    "maximum_pct": 80
  },

  "funding": {
    "reference_rate_source": "BUNDESBANK",
    "term_spread_pp": { "12-24": 0.35, "25-36": 0.50, "37-48": 0.70, "49-60": 0.90 },
    "asset_uncertainty_spread_pp": { "HIGH": 0.00, "MEDIUM": 0.30, "LOW": 0.60 }
  },

  "margin": {
    "base_pp": 1.50,
    "risk_adjustment_pp": { "GREEN": 0.25, "YELLOW": 1.00, "RED": null },   // null = not priced
    "deal_size_adjustment_pp": { "lt_20k": 0.25, "20k_60k": 0.00, "60k_100k": -0.10, "gt_100k": "MANUAL_REVIEW" },
    "commercial_margin_floor_pp": 1.00,
    "commercial_margin_cap_pp": 3.50
  },

  "risk": { "green_min": 75, "yellow_min": 55, "red_max": 54.99 },

  "risk_weights": {
    "B2C": { "credit_bureau": 0.40, "affordability": 0.25, "income_stability": 0.15, "existing_exposure": 0.10, "kyc_confidence": 0.10 },
    "B2B": { "credit_quality": 0.40, "financial_strength": 0.25, "exposure_vs_limit": 0.15, "company_age": 0.10, "payment_history": 0.10 }
  },
  "affordability_bands": { "strong_max": 30, "acceptable_max": 40, "weak_max": 50 },   // % ; >50 high risk
  "b2b_exposure_bands": { "strong_max": 50, "moderate_max": 100 },                     // % ; >100 weak

  "eligibility": {
    "vehicle": { "category": "M1", "price_min_eur": 10000, "price_max_eur": 150000,
                 "term_max_months": 60, "annual_mileage_max_km": 40000, "age_at_end_max_years": 8 },
    "high_value_review_threshold_eur": 100000
  },

  "mileage_settlement": {
    "tolerance_km": 2000,
    "per_km_rate_eur_by_vehicle_value": { "le_30k": 0.10, "30k_60k": 0.15, "gt_60k": 0.20 }
  },

  "term_context_caps": {
    "used_vehicle_max_months": 48,
    "high_mileage_over_30k_max_months": 48,
    "low_rv_confidence_max_months": 48
  },

  "vat": { "source": "EU_TEDB", "fallback_pct": 19 },

  "offer_limit": { "standard_max_eur": 100000, "absolute_mvp_max_eur": 150000 },

  "output": { "languages": ["en", "de"], "format": "PDF" },

  "engine_versions": {
    "lease_calc": "MVP_LEASE_CALC_V1",
    "funding": "DE_PKW_FUNDING_V1",
    "margin": "DE_PKW_MARGIN_V1",
    "residual": "DE_PKW_RV_V1",
    "risk": "DE_PKW_RISK_V1"
  }
}
```

---

## 3. Roles, permissions & approval matrix (maker-checker)

| Role | Can do | Cannot |
|---|---|---|
| `SALES` | view, create, edit, generate scenarios, submit | approve |
| `REVIEWER` | view, comment, return, resolve soft exceptions, review | change pricing engine, approve beyond limit |
| `APPROVER` | review, approve within authority, return | approve own Offer |
| `SENIOR_APPROVER` | as Approver + higher limits + permitted **soft** overrides | approve own Offer, hard overrides |
| `POLICY_ADMIN` | manage reference policy & mock rules | approve own deals |

**Authority limits:**
| Role | GREEN up to | YELLOW up to |
|---|---|---|
| Reviewer | €75,000 | — |
| Approver | €100,000 | €50,000 |
| Senior Approver | €150,000 | €150,000 |

`> €150,000` → outside MVP / blocked. **Invariants:** creator ≠ approver (four-eyes); and
**agent effective permissions = min(agent policy, current user's permissions)**.

---

## 4. Exception registry (typed)

| Code | Default severity | Blocking | Override | Required role | Next action |
|---|---|---|---|---|---|
| DATA_MISSING | — | yes until resolved | n/a | SALES | request_information |
| DATA_CONFLICT | — | yes | reviewable | REVIEWER | resolve_conflict |
| ASSET_UNSUPPORTED | RED | yes | no | — | block |
| PRODUCT_INELIGIBLE | RED/YELLOW | depends | reviewable if high-value | APPROVER | review/block |
| TERM_OUT_OF_RANGE | — | yes | reviewable | REVIEWER | correct |
| MILEAGE_OUT_OF_RANGE | — | yes if >40k | reviewable | REVIEWER | correct/review |
| SPECIAL_PAYMENT_HIGH | YELLOW | no (20–30%) | reviewable | REVIEWER | review |
| RESIDUAL_LOW_CONFIDENCE | YELLOW | no | reviewable | REVIEWER | review |
| RISK_YELLOW | YELLOW | no | reviewable | APPROVER | human_review |
| RISK_RED | RED | yes | no (compliance) / loop (economic) | — | block / suggest_alternatives |
| SANCTIONS_MATCH | RED | yes | no | — | block |
| KYC_FAILED | RED | yes | no | — | block |
| AUTHORIZATION_DENIED | RED | yes | no | — | block |
| CALCULATION_FAILED | RED | yes | no | — | block/retry |
| EXTERNAL_SERVICE_UNAVAILABLE | — | yes | no | — | retry/mock-fallback |
| DOCUMENT_MISSING | — | depends | reviewable | SALES | request_document |
| PDF_GENERATION_FAILED | — | yes | no | — | retry |

Every override → AuditEvent `{who, when, reason, before, after, rule}`.

---

## 5. Required documents (contextual)

| Context | Required | Conditional |
|---|---|---|
| B2C | identity, address, credit result, vehicle quote/config | income evidence (only when risk policy requires) |
| B2B | company identity/register, authorized representative, UBO/KYC result, credit result, vehicle quote/config | financial info (when risk requires) |
| Vehicle — new | make/model/type/variant/version/config-id/dealer quote | VIN optional |
| Vehicle — used | VIN, registration date, mileage, condition/valuation | — |

---

## 6. PDF output contract

`Validated Offer JSON → language template (EN/DE) → HTML → PDF`. Never `LLM → prose → PDF`.

Sections: offer reference · customer · vehicle · leasing product · term · mileage · special
payment · monthly rate (net/gross) · residual assumption · fees · mileage settlement · scoring
status · conditions/exceptions · approval · offer validity · assumptions · disclaimer.

**Controlled disclaimer text** (verbatim, do not LLM-translate controlled labels):
- **EN — Illustrative Offer:** "This document is a non-binding leasing offer generated as part of the MVP demonstration. The stated terms are based on the information, reference data and calculation parameters recorded in the Offer at the time of generation. Final contractual terms remain subject to the required verification, approval and separate contractual documentation."
- **DE — Unverbindliches Angebot:** "Dieses Dokument ist ein unverbindliches Leasingangebot, das im Rahmen der MVP-Demonstration erstellt wurde. Die dargestellten Konditionen basieren auf den zum Zeitpunkt der Erstellung im Angebot hinterlegten Informationen, Referenzdaten und Berechnungsparametern. Endgültige Vertragskonditionen stehen unter dem Vorbehalt der erforderlichen Prüfung, Genehmigung und gesonderten Vertragsdokumentation."

Controlled status labels get fixed EN/DE translations (READY/BLOCKED/GREEN/YELLOW/RED etc.); only
free-text *explanations* may be LLM-generated in the selected language.

---

## 7. Localization structure

```
language
├── en → { labels, statuses, validation_messages, pdf_text }
└── de → { labels, statuses, validation_messages, pdf_text }
```
Controlled enum values map to fixed labels per language; the LLM never re-translates them ad hoc.
