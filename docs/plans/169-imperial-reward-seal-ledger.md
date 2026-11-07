# Plan 169 - Imperial Reward Seal ledger

Status: proposed. Source: research 0044 (2026-11-05 patch).

## Problem

The 2026-11-05 patch adds per-category Imperial Reward Seals (Cooking, Fishing,
Subjugation, Training, Work Supervisor, Alchemy) with new exchange tables;
Golden Seals convert at the 2026-12-03 maintenance. EW has no seal state, so
the operator cannot see which seals are held, what each exchange needs, or
that Golden Seals should be spent or planned before conversion.

## Scope

1. Data file `server/ew/data/reward_seals.json`: categories and exchange rows,
   each row with a source and `verified` flag (plan 085 verifier applies).
2. Operator-typed (or OCR-fed, later) seal counts per category in the
   operator store; Golden Seal count with a countdown to 2026-12-03.
3. Card beside the Imperial delivery planner: seals held, nearest affordable
   exchange, Golden Seal conversion warning in the plan 074 before-maintenance
   digest.

## Out of scope

Conversion rate (unannounced; shown as unknown until sourced), any game
input, any client file read.

## Tests

Failing test first: seal totals, affordability, conversion-date warning,
unknown-rate wording.

## Depends-on

053

## As-built deviations

1. No exchange rows seeded. Decision: `reward_seals.json` ships the six
   categories and the Golden Seal row (all `verified: false`, plan 085 hints
   on the 2026-11-05 patch-notes title) with `exchange: []`; the operator adds
   exchange rows on the card (`seal_ex_add`), stored in the `reward_seals`
   store domain. Alternatives: seed guessed rows; fetch the tables now.
   Why: research 0044 did not read the tables row by row, and an unsourced
   cost would mislead the affordability math. Reverses if: a deep-dive reads
   the official exchange tables - seed them with source + verified.
2. Seals render as a section inside the Imperial delivery card, served on
   GET /api/imperial (`seals` key) with POST ops `seal_count`, `seal_ex_add`,
   `seal_ex_del`, instead of a separate card and route. Alternatives: a new
   /api/seals route + card. Why: "beside the planner" with no new route,
   bridge whitelist entry or poll. Reverses if: the section outgrows the
   card (then split it into its own card on the same Today tab).
3. "Nearest affordable exchange" is read as two fields per category:
   `ready` (the dearest row the typed count covers) and `next` (the row with
   the smallest shortfall). Alternatives: one field only. Why: the operator
   needs both "what can I take now" and "what is closest". Reverses if: the
   operator asks for a single pick.
4. The conversion moment is that date's maintenance start (an official
   notice beats the weekly slot, `maint.resolve`), not midnight. The digest
   row rides plan 074's `ending` list (kind `seal`) so it shows only when the
   2026-12-03 maintenance is the next one. A Golden Seal count left untyped
   still warns ("count not typed"); a typed 0 does not. Reverses if: the
   official notice moves the conversion off a maintenance.
