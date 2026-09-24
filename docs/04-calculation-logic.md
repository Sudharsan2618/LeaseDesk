# 04 — Calculation & Decision Logic (the deterministic engine)

> This is the single most important thing to get right and validate *before* any AI/UI work.
> Every number here is deterministic, versioned, and explainable. The LLM never enters any box in
> this document — it only reads the `ResultEnvelope` output and explains it.
>
> All policy constants come from `DE_PKW_V1` ([05](05-mvp-reference-policy.md)). The values are the
> **MVP reference policy**, not the client's production policy.

---

## 1. Pipeline overview

```
                 ┌─────────────────────────────────────────────────────────────┐
 INPUTS          │  1 FUNDING RATE  →  2 CUSTOMER FINANCE RATE  →  3 RESIDUAL   │
 (vehicle,       │        │                      │                    │         │
  term,          │        └──────────┬───────────┘                    │         │
  mileage,       │                   ▼                                 ▼         │
  customer,      │             4 NETCAP  ──────────►  5 LEASE FORMULA ◄┘         │
  special pmt)   │                                          │                    │
                 │                                          ▼                    │
                 │                              6 NET / GROSS + FEES + VAT       │
                 └───────────────────────────────────────┬─────────────────────┘
                                                          ▼
                     7 SCORING (G/Y/R)  ──feeds back into──►  2 (risk_adjustment)
                                                          │
                                                          ▼
                     8 ELIGIBILITY + EXCEPTIONS  ──►  READY / REQUIRES_ACTION / BLOCKED
```

Order matters: scoring's band feeds the margin's `risk_adjustment`, so **score first (or with a
provisional band), then price** — see §7.4 for the ordering rule.

---

## 2. Step 1 — Funding rate (context-aware)

```
funding_rate = reference_rate + term_spread + asset_uncertainty_spread
```

| Component | Source | Value |
|---|---|---|
| reference_rate | 🟢 Bundesbank/ECB (LIVE) | latest series value, as-of Offer date |
| term_spread | 🟣 policy | 12–24m +0.35 · 25–36m +0.50 · 37–48m +0.70 · 49–60m +0.90 (pp) |
| asset_uncertainty_spread | 🟣 policy | new/high-RV-confidence +0.00 · used/medium +0.30 · low-RV-confidence +0.60 (pp) |

`asset_uncertainty_spread` depends on **residual confidence** (§4), which depends on the
vehicle/term/mileage — so residual confidence is computed before the funding rate.

---

## 3. Step 2 — Customer finance rate (funding + margin)

```
customer_finance_rate (annual) =
    funding_rate
  + base_margin
  + risk_adjustment       (from scoring band)
  + deal_size_adjustment
```

| Component | Value |
|---|---|
| base_margin | +1.50 pp |
| risk_adjustment | GREEN +0.25 · YELLOW +1.00 · RED → *not priced* |
| deal_size_adjustment | <€20k +0.25 · €20–60k 0.00 · €60–100k −0.10 · >€100k → *manual review* |

**Then clamp the total commercial margin** (base + risk + deal) to `[+1.00 pp, +3.50 pp]`.
> Note: the clamp is on the *commercial margin portion*, not on the whole rate. If the raw margin
> is below 1.00 it is raised to 1.00; above 3.50 it is capped at 3.50.

RED is never priced (no rate produced); >€100k deal forces manual review before a rate is final.

---

## 4. Step 3 — Residual value & confidence (`DE_PKW_RV_V1`)

```
RV% = base_term_RV + mileage_adjustment + vehicle_age_adjustment + market_asset_adjustment
RV% clamped to [20%, 80%]
```

**Base term RV (new PKW):**
| Term | 12m | 24m | 36m | 48m | 60m |
|---|---|---|---|---|---|
| RV% | 80 | 68 | 58 | 49 | 41 |
(interpolate for non-tabulated allowed terms, e.g. 30m, 42m, 54m.)

**Mileage adjustment** (reference 15,000 km/yr, asymmetric — conservative):
- each **+5,000** km/yr → **−2.5 pp**
- each **−5,000** km/yr → **+1.5 pp**
- caps: max uplift **+5 pp**, max penalty **−15 pp**

Worked examples at 36m: 15k→58% · 20k→55.5% · 25k→53% · 10k→59.5%.

**Residual confidence:**
| Confidence | Conditions |
|---|---|
| HIGH | new vehicle **and** term ≤48 **and** annual km ≤25,000 **and** vehicle data complete |
| MEDIUM | 60-month term **or** 25k–35k km/yr **or** used ≤3 years |
| LOW | used >3 years **or** >35k km/yr **or** unusual config **or** missing critical specs |

`LOW` confidence → raises `RESIDUAL_LOW_CONFIDENCE` (soft, YELLOW) → human review, and also feeds
`asset_uncertainty_spread` in §2.

Output (`AssessmentResult`): `{residual_value_pct, residual_value_amount, residual_confidence, assumptions[]}`.

---

## 5. Step 4 — Net capital cost

```
NetCap = acquisition_price
       + financed_fees
       − discounts_incentives
       − special_payment
```

Special-payment rules (`% of acquisition cost`): 0–20% standard · >20–30% allowed but YELLOW/review
· >30% BLOCK (`PRODUCT_INELIGIBLE`/`SPECIAL_PAYMENT_HIGH`).

**Edge case (must handle explicitly):** if `NetCap ≤ PV_RV` (i.e. the special payment or discounts
drive the amount to amortise to zero/negative), do **not** silently alter the payment — return
`SPECIAL_PAYMENT_TOO_HIGH` and ask the user to reduce it.

---

## 6. Step 5–6 — Lease formula (amortisation-to-residual) → net/gross

```
r = customer_finance_rate / 12               # monthly rate

PV_RV = residual_value_amount / (1 + r)^n    # present value of the residual

if r == 0:
    base_lease = (NetCap − residual_value_amount) / n        # no divide-by-zero
else:
    base_lease = (NetCap − PV_RV) * r / (1 − (1 + r)^(−n))

monthly_net   = base_lease + recurring_service_fees
monthly_gross = monthly_net * (1 + vat_rate)                 # vat_rate: EU TEDB / DE 19%
```

This is a standard annuity amortising `NetCap` down to the residual over `n` months; it handles a
balloon/residual naturally. `residual_value_amount = list_or_acquisition_base × RV%` (define which
base once and keep it consistent — see [08](08-open-questions-and-verification.md) Q-CALC-1).

**Mileage settlement terms** (kilometre leasing, appear in PDF, not in the monthly rate): tolerance
±2,000 km; per-km rate ≤€30k €0.10 · €30–60k €0.15 · >€60k €0.20 (same rate for excess and under),
where the band is by vehicle value. `contract_mileage = annual_mileage × term_months / 12`.

**Rounding:** round only the final presented `monthly_net`/`monthly_gross` (to cents); keep full
precision internally. Record the rounding rule in the `ResultEnvelope`.

---

## 7. Step 7 — Risk scoring (MVP Risk Score 0–100, `DE_PKW_RISK_V1`)

> Do **not** emulate SCHUFA or reuse a bureau's own score as the band. Compute an internal MVP
> score from weighted factors, then band it. The bureau result is only one input factor.

### 7.1 B2C weighted score
| Factor | Weight |
|---|---|
| credit/bureau (mock) | 40% |
| debt burden / affordability | 25% |
| income stability | 15% |
| existing exposure | 10% |
| identity/KYC confidence | 10% |

Affordability ratio = `(existing_monthly_debt + new_monthly_gross) / net_monthly_income`:
≤30% strong · 30–40% acceptable · 40–50% weak · >50% high risk.

### 7.2 B2B weighted score
| Factor | Weight |
|---|---|
| external/mock credit quality | 40% |
| financial strength | 25% |
| exposure vs credit limit | 15% |
| company age / stability | 10% |
| payment history | 10% |

Exposure ratio = `offer_exposure / recommended_credit_limit`: ≤50% strong · 50–100% moderate · >100% weak.

### 7.3 Bands & hard blocks
```
HARD BLOCK present?  ──► RED (compliance)          # skip the weighted score entirely
   hard blocks: confirmed sanctions match, fraud flag, identity failure,
                company inactive/insolvent, required credit outcome unavailable,
                unresolved material data conflict
else band by score:
   score ≥ 75             ──► GREEN
   55 ≤ score ≤ 74.99     ──► YELLOW   (or any soft policy exception → YELLOW)
   score < 55             ──► RED (economic)
```

### 7.4 Ordering rule (resolving the scoring↔margin cycle)
Scoring's band feeds the margin's `risk_adjustment`, and affordability (a scoring factor) needs
`new_monthly_gross` from pricing. Break the cycle deterministically:
1. Compute residual + confidence (§4).
2. Compute a **provisional** finance rate using a neutral band assumption (or the customer's prior band), price a provisional `monthly_gross`.
3. Run scoring with that provisional payment → get the real band.
4. Re-price with the real band's `risk_adjustment`.
5. If the band changes the payment enough to flip an affordability threshold, iterate once more (cap at 2 iterations; if still oscillating, take the more conservative band and flag it).

Record the final band and the number of iterations in the `ResultEnvelope`.

---

## 8. Step 8 — Eligibility & exceptions

### 8.1 Eligibility rules
**Vehicle:** category `M1`; price €10,000–€150,000; term ≤60; annual mileage ≤40,000; age at lease
end ≤8 years. Age at end > 8y → **BLOCK**. Price >€100k → **not** blocked → YELLOW/manual approval.

**Customer B2C:** age ≥18, identity verified, address present, credit info present, not sanctioned.
**Customer B2B:** company identified, registration data, authorized representative, UBO/KYC status,
credit info present, not sanctioned.

**Offer:** calculation succeeded, residual available, risk ≠ RED, mandatory data complete, human
review completed where required.

### 8.2 Typed exceptions (each: `{code, severity, blocking, override_allowed, required_role, next_action}`)
`DATA_MISSING · DATA_CONFLICT · ASSET_UNSUPPORTED · PRODUCT_INELIGIBLE · TERM_OUT_OF_RANGE ·
MILEAGE_OUT_OF_RANGE · SPECIAL_PAYMENT_HIGH · RESIDUAL_LOW_CONFIDENCE · RISK_YELLOW · RISK_RED ·
SANCTIONS_MATCH · KYC_FAILED · AUTHORIZATION_DENIED · CALCULATION_FAILED ·
EXTERNAL_SERVICE_UNAVAILABLE · DOCUMENT_MISSING · PDF_GENERATION_FAILED`.

### 8.3 Hard vs soft
- **Hard (never override):** confirmed sanctions, KYC failure, fraud, RED-compliance, missing
  required calculation, missing mandatory approval, unauthorized user, final-validation failure.
- **Soft (reviewable):** high-value vehicle, low RV confidence, new company, high mileage, special
  payment 20–30%, minor data uncertainty, economic YELLOW.

### 8.4 Red handling (two kinds)
- **Economic RED** → agent may suggest: cheaper car / higher special payment / different term /
  lower mileage → **recalculate → rescore** (a normal loop).
- **Compliance RED** → **no** alternatives → `BLOCKED`.

### 8.5 Yellow handling (the source left this open; now defined)
`YELLOW → HUMAN REVIEW` presenting reason codes + scoring factors + offer + exceptions +
alternatives → reviewer approves or returns for modification. **Yellow can never go straight to PDF.**

---

## 9. Worked example (illustrative, values from `DE_PKW_V1`)

Assume: new BMW X1, acquisition €45,000 net, term 36m, annual mileage 20,000 km, special payment
€4,500 (10%), recurring service fee €0, VAT 19%, reference_rate 3.00%, GREEN band, B2B mid-exposure.

```
Residual:  base 58% (36m) + mileage adj (20k = +5k over ref → −2.5pp) = 55.5%; confidence HIGH
           residual_value_amount = 45,000 × 55.5% = €24,975
Funding:   3.00 + term_spread(36m = +0.50) + asset_spread(HIGH = +0.00)      = 3.50%
Margin:    base 1.50 + risk(GREEN +0.25) + deal_size(€20–60k = 0.00) = 1.75% → within [1.00,3.50] ✓
Finance r: 3.50 + 1.75 = 5.25% / yr  → r = 0.4375%/mo (0.004375)
NetCap:    45,000 + 0 − 0 − 4,500 = €40,500
PV_RV:     24,975 / (1.004375)^36 = 24,975 / 1.1701 ≈ €21,344
base_lease:(40,500 − 21,344) × 0.004375 / (1 − 1.004375^-36)
          = 19,156 × 0.004375 / (1 − 0.85462)
          = 83.81 / 0.14538 ≈ €576.4
monthly_net   ≈ €576.4
monthly_gross ≈ 576.4 × 1.19 ≈ €685.9
```
(Figures are for validating the *mechanics*; recompute precisely in code and reconcile the residual
base per Q-CALC-1.)

---

## 10. Validation checklist for the engine (do this before AI/UI)

- [ ] `r == 0` branch produces `(NetCap − RV)/n` with no error.
- [ ] `NetCap ≤ PV_RV` returns `SPECIAL_PAYMENT_TOO_HIGH`, never a negative rental.
- [ ] Term outside 12–60, or context caps (used→48, km>30k→48, low-RV→48), raise `TERM_OUT_OF_RANGE`.
- [ ] Mileage <5k → manual review; >40k → `MILEAGE_OUT_OF_RANGE`.
- [ ] Special payment >30% → BLOCK; 20–30% → YELLOW.
- [ ] Residual clamped to [20%,80%]; mileage adj capped [+5pp,−15pp].
- [ ] Commercial margin clamped [1.00pp,3.50pp]; RED never priced; >€100k → manual review.
- [ ] Vehicle age at end >8y → BLOCK; price outside €10k–€150k handled (>€100k = YELLOW, not block).
- [ ] Hard-block conditions bypass the weighted score → RED-compliance → BLOCKED (no alternatives).
- [ ] Scoring↔margin cycle terminates (≤2 iterations, conservative fallback).
- [ ] Every result carries a full `ResultEnvelope` (engine + policy versions + inputs_digest + assumptions).
- [ ] Same inputs → identical outputs (no randomness anywhere).
