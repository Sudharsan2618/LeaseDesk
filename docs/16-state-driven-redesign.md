# 16 — State-driven, chat-first intake (design + plan)

**Status:** design proposal — no code changed yet. For client alignment before build.
**Supersedes the intake interaction model in** [09-ui-and-screenflow](09-ui-and-screenflow.md), [10-screen-redesign](10-screen-redesign.md), [13-agent-workbench-design](13-agent-workbench-design.md). Everything downstream of intake (pipeline, scenarios, review, generation) is unchanged.

---

## 1. What the client asked for

1. **Confirm / edit / update from the chat** — not only the wizard confirm buttons. Typing in the agent chat should set values, confirm a step, or change something.
2. **Edit any step from anywhere, without navigating** — e.g. while on *Commercial* (step 5), change the *Customer* (step 2) by typing in chat; the agent applies it and I stay where I am. Crucially, the agent must handle the **ripple**:
   - work out which parameters **change** and which **don't** because of the edit;
   - for changed parameters the user must **verify/confirm**; if a now-required value is **missing**, the agent **asks**;
   - for parameters that were confirmed but are affected, the agent **re-asks confirmation** — all inline in chat.
3. **Persistent chat, full session context** — the whole thread is one session; the agent knows end-to-end what was decided and edited.

Governing principle stays: **AI assists · Rules decide · Humans govern.** Chat becomes the primary control surface; the wizard becomes a live *view* of state, not the driver.

---

## 2. What we already have (reuse as-is)

| Capability | Where |
|---|---|
| One durable session per offer (thread = `offer.id`), full state persisted & resumable | `PostgresSaver` checkpoint on Neon — `api/server.py`, `graph/state.py` |
| Persistent chat transcript (with confirmation + `edited` entries) | `agent_context["messages"]` → `offers.agent_context` (jsonb); returned in every snapshot/interrupt |
| Single mutable proposal that re-propagates to the whole offer | `agent_context["proposed"]` → `agent_nodes._assemble` rebuilds the Offer from it |
| Edit the current step by chat text (LLM fold-in) | `agent_nodes._apply_turn` → `understand()` (LLM) + `_merge()` into `proposed` |
| Two hardcoded ripple invalidations | `_merge`: make/model → clear `vehicle_key`+`colour`; company → clear `register_number` |
| Deterministic engine, scenarios, review gate, generation | `engine/*`, `graph/nodes.py` — untouched by this redesign |

**Conclusion:** persistence, session context, and edit-fold-in exist. The redesign adds a *field-state + dependency* layer and replaces the *linear step cursor* with a *single conversational turn*.

---

## 3. What's missing (the state-driven core)

Today the intake is a **linear cursor**: `state.step` + `step_ok` + `goto_step` (`graph/state.py`) walking five separate `interrupt()` gates (`select_channel … select_commercial`). Editing an earlier field means **navigating** (`goto`) to that step. There is no per-field "confirmed" set and no general dependency model.

Three gaps:

- **G1 — Confirm/edit intent from chat.** `ok = reply.get("confirm")` is a structured flag; a chat "yes / looks good / change term to 48 and continue" is not interpreted as confirm.
- **G2 — Field-level state + dependency graph.** No `field_state` (which fields are unset / proposed / confirmed / stale); no declaration of what an edit *invalidates* vs *re-prices silently*.
- **G3 — Stay-in-place editing + re-confirmation.** The UI screen is bound to whichever step the interrupt sits on; there's no single turn that accepts any-field edits and re-surfaces only the affected confirmations.

---

## 4. Target model

### 4.1 Field-state model

Replace the single step cursor with a per-field state map, stored in `agent_context["field_state"]` (persisted, in-checkpoint):

```
field_state[<field>] = {
  value:      <current value | null>,
  status:     "unset" | "proposed" | "confirmed" | "stale",   # stale = was confirmed, an edit invalidated it
  source:     "agent" | "user" | "default" | "resolved",
  confirmed_at: <turn #> | null
}
```

Fields (from today's `proposed`): `channel, business_line, leasing_product, asset_category, register_number (customer), vehicle_key (+ make/model/colour), term_months, annual_mileage_km, quantity, special_payment_eur, service_maintenance, service_tyres, insurance`, plus flexible `filters, constraints, ambiguities`.

This reuses/extends the existing `ProvenanceValue.status` idea (`core/types.info_state` → established / confirmed / requires_confirmation / needs_action) — the FD already renders those four states.

### 4.2 Dependency table (the "changing vs non-changing" engine)

A **config-driven** table declares, per field, what an edit does. This generalizes the two edges already hardcoded in `_merge`.

| Edited field | Invalidates (→ `stale`, must re-confirm) | Clears (must re-resolve/ask) | Silent re-price only |
|---|---|---|---|
| `channel` | `register_number` (partner kind can differ) | — | — |
| `customer` (`register_number`) | — | re-run credit / KYC / scoring context | ✓ (re-score) |
| `leasing_product` | `asset_category`, `asset` (category may change) | `vehicle_key` if category changes | ✓ (policy params) |
| `asset` (`vehicle_key`) | — | `colour` | ✓ (re-price) |
| `make`/`model` | `asset` | `vehicle_key`, `colour` | — |
| `term_months` | — | — | ✓ (residual, funding, calc) |
| `annual_mileage_km` | — | — | ✓ (residual, calc) |
| `quantity` | — | — | ✓ (exposure → scoring, calc) |
| `special_payment_eur` | — | — | ✓ (eligibility, calc) |
| services / `insurance` | — | — | ✓ (calc) |

Rules the table encodes:
- **Changing parameter, value supplied** → mark `confirmed` (the user stated it) or `proposed` (agent inferred) and mark dependents `stale`.
- **Changing parameter, value now required but missing** → agent **asks** in chat.
- **Affected confirmed parameter** (`stale`) → agent **re-asks confirmation** in chat before pricing.
- **Non-changing parameter** → untouched; no re-confirm.

Reference data stays controlled: allowed channels/products/asset-categories come from `reference_data.json`; the table is policy/config, never agent-invented.

### 4.3 Chat as the driver

Extend extraction (`agent/extract.py` / `schemas.ExtractedIntent`) so a turn also yields an **action intent**:

```
intent.action ∈ { set, confirm, edit, goto, ask, generate, none }
```

- `set`/`edit` → fold values into `field_state` via the dependency table.
- `confirm` (affirmations: "yes", "confirm", "looks good", "continue") → confirm the pending field(s). Closes **G1**.
- A single sentence can carry both ("make it 48 months and continue" = set + confirm).
- Ambiguous / missing → agent asks (existing `ambiguities`).

### 4.4 Graph shape

Replace the five `select_*` interrupt nodes with **one `agent_turn` node** that loops on `interrupt()`:

```
understand → agent_turn (loop) → assemble → run_pipeline → … (unchanged)
                 ▲   │
      resume ────┘   └── each turn:
                        1. fold the chat/overrides into field_state (dependency table)
                        2. recompute pending = fields that are unset-required or stale
                        3. if pending → interrupt(agent_turn payload: full field_state + what's pending + transcript)
                        4. else → proceed to assemble
```

- The FD `Interrupt` type already anticipates this (`type: "agent_turn"`).
- `interrupt()` / `Command(resume=…)` already carry arbitrary payloads (`api/server.py`), so no transport change.
- "Stay on the same screen" falls out for free: there is one screen (the workbench); the wizard rail renders `field_state`, and editing any field is just another turn. Closes **G3**.
- `goto` becomes optional sugar (focus a field), not a navigation.

`_assemble`, the pipeline, scenarios, `workspace_gate`, `human_review`, generation — **unchanged**.

### 4.5 Persistence & context

- `field_state` lives in `agent_context` (already persisted via `repository.upsert_offer`, already in the checkpoint) — no schema change required for the MVP (jsonb).
- Transcript already records user confirmations + `edited` tags; add a compact "edit ripple" line ("Customer changed → re-confirm asset, re-scored") so the session log stays the source of truth.
- The agent sees the full `field_state` + transcript each turn → it "knows what was decided and edited," satisfying scenario 3.

### 4.6 Frontend

- `WizardRail` becomes a **view of `field_state`** (per-field status chips: set / to-confirm / stale / needs-input) — the component already shows per-step values and the four info-states.
- `AgentChat` stays the primary control: confirm/edit/ask all happen here (already sends `{message}`); add quick-confirm affordances.
- The structured cards stay as a scannable mirror (per [13](13-agent-workbench-design.md)); confirming a card = a chat turn.

---

## 5. Worked example (scenario 2)

State: on the workbench after confirming Customer = *Musterlogistik*, Asset = *BMW X1*, now editing Commercial. User types: **"actually the customer is Schwerlast Spedition."**

1. `agent_turn` extracts `edit customer=Schwerlast`.
2. Dependency table: `customer` → re-run credit/KYC/scoring context (silent re-price) — and (per config) does **not** invalidate the asset, but **does** require re-scoring. `term/mileage/asset` are **non-changing** → left as-is.
3. `register_number` re-resolves; scoring context marked to re-run at pipeline.
4. Agent replies in chat: *"Customer set to Schwerlast Spedition GmbH. Term, asset and mileage are unchanged. I'll re-run the credit check and re-score at pricing — confirm to continue."* → user confirms in chat.
5. No navigation; the rail's Customer chip flips to *confirmed (edited)*, others stay *confirmed*.

If instead the edit were **"switch to an Equipment product,"** the table marks `asset_category` + `asset` **stale** → agent asks the user to pick/confirm a new asset before pricing.

---

## 6. Phased plan (each phase reviewable; validate against this doc)

- **Phase A — Field-state + dependency table (backend, additive).** Add `field_state` to `agent_context`; implement the config-driven dependency/invalidation engine (generalize `_merge`). Keep the existing step nodes working. *Gate: unit tests for each edit → correct invalidations.*
- **Phase B — Chat intent (confirm/edit/goto) from the LLM.** Extend `ExtractedIntent` with `action`; wire affirmation → confirm. *Gate: "yes/confirm/change X and continue" advance correctly.*
- **Phase C — Single `agent_turn` node.** Collapse the five `select_*` interrupts into one turn loop driven by `field_state` + pending. Keep `assemble`/pipeline unchanged. *Gate: full intake happy-path + edit-any-field mid-flow, on Neon.*
- **Phase D — Frontend as a state view.** `WizardRail` renders `field_state`; chat-first confirm/edit; stay-on-screen; re-confirmation prompts. *Gate: the two client scenarios demoed end-to-end.*
- **Phase E — Ripple transparency.** Edit-ripple lines in the transcript + audit; "why" answerable from session context.

Reused unchanged: engine, scenarios, review, generation, persistence, extraction transport, most FD components.

---

## 7. Decisions to confirm with the client

1. **Dependency policy** — the exact "invalidates vs re-prices" per field (§4.2). This is a **business** decision (e.g. does changing the customer force re-confirming the asset?). The table above is a proposed default.
2. **Confirm granularity** — confirm per field, or one "confirm all pending"? (Proposed: both — per-field chips + a chat "confirm all".)
3. **Keep the stepper?** Proposed: keep it as a *status view* (not a gate), so the flow stays legible.
4. **Scope of "edit anytime"** — intake fields only, or also after pricing (which already re-prices via Adjust)? Proposed: intake fields now; post-pricing edits keep going through Adjust → re-price.

---

## 8. Effort (rough)

- Phase A: S–M (config + engine + tests).
- Phase B: S (schema + prompt + wiring).
- Phase C: M (graph refactor; the riskiest — collapses 5 nodes to 1).
- Phase D: M (FD state-view + chat-first).
- Phase E: S.

No new external dependencies; no DB migration for the MVP (jsonb `agent_context`). The deterministic core and governance gates are untouched, so risk is concentrated in Phase C (graph refactor) and is contained by keeping `assemble`→pipeline stable.
