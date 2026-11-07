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
