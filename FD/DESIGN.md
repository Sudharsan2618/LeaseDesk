# DESIGN.md — Agentic Offer Creation console

## Direction contract
**THESIS** — A *glass-walled decision console*: the offer's reasoning is visible at every step. It
refuses both the black-box chatbot and the same-size-card dashboard; the page is a working ledger +
a live reasoning spine, not a grid of tiles.

**OWN-WORLD** — Cool paper ground, ink text, one confident accent, semantic bands as status only.
- Ground `#F7F8FA`, surface `#FFFFFF`, ink `#111318`, muted ink `#5B6270`, hairline `#E4E7EC` (1px).
- Accent (primary action + workflow spine): indigo `#3B3FBE` / hover `#2E32A0`.
- Bands (status only, never decoration): green `#0E9F6E`, amber `#C77700`, rose `#D64550`.
- Type: **system UI stack** for interface text (Operate workhorse); **ui-monospace** ONLY for money,
  rates, IDs, VINs (real data/measurement). No display serif, no gradient text, no glass decoration.
- Structure: hairline separators, generous row rhythm, a persistent right **transparency rail**;
  status shown as a vertical **spine** of steps, not pills scattered around.

**STORY** — A sales user types one sentence, watches the engine reason (live), confirms what the AI
inferred, compares scenarios, and submits; a reviewer sees the entire basis and approves (four-eyes).

**FIRST VIEWPORT** — The **Inbox**: a dense, legible ledger of offers (reference · status spine ·
band dot · monthly gross · next action), with a single prominent "New offer" entry that opens NL
intake. Not a hero.

**FORM** — An operations console / ledger (workhorse Operate form), chosen deliberately over a
concept tournament because an internal decision tool inherits the task's real scene (docs/09).

## Durable rules
- **Color strategy: Restrained** — neutrals + one indigo accent; band colors reserved for risk/status.
- Light theme (office daytime use scene).
- Money/rates/IDs render in monospace, tabular-nums, right-aligned in tables.
- Every material value shows **provenance** (source + status); AI-generated prose carries an "AI · grounded" badge.
- No card-in-card. Cards are used sparingly; the primary structures are the ledger table, the
  status spine, and the transparency rail.
- Motion: one authored moment — the live agent feed lines stream in (ease-out, from visible); no
  scattered hover animations.
- Bands map: GREEN=emerald, YELLOW=amber, RED=rose; READY=emerald, REQUIRES_ACTION=amber, BLOCKED=rose.

## Tokens (provisional until first build settles them)
Radius 8px (surfaces), 6px (controls). Shadow: `0 1px 2px rgba(16,18,24,.06), 0 4px 12px rgba(16,18,24,.05)`.
Spacing scale 4/8/12/16/24/32. Container max 1200–1320px; workspace = 3 columns (context · stage · rail).
