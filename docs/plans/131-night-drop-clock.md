# Plan 131 - Night drop-chance clock: derive the night flag from a calibrated game clock

Status: open. Source: deep dive 0026 (Global Lab notes posted 2026-10-08: the
minimap game-time tooltip says item drop chance rises at night). Lane hint:
`data`. Depends on: 038, 063.

Problem: plan 038's drop-buff cap calculator takes "night" as a hand-set
toggle, so grind numbers and the What-now card never know the real state.
BDO's day/night cycle is a fixed repeating period, so a single calibration
point predicts every night window.

## Slices

1. Data file `server/ew/data/daynight.json`: `{"period_min","night_from",
   "night_to","source","verified":false}` (game-time of day to real minutes).
   Seed values are unverified community figures; the plan 085 verifier flags
   the row until a calibration confirms it. No scraping.
2. Calibration: one operator screenshot of the minimap with the game-time
   tooltip open -> OCR kind `gametime` (plan 063 pipeline, confidence gated)
   stores `(real_utc, game_hhmm)`. A second reading later checks drift; the
   period is refit only inside a sanity band, else the read is held.
3. Pure `night_state(now)` -> `{night, next_change_utc}`; `GET /api/daynight`.
4. Plan 038 reads `night` from the clock when calibrated; a typed toggle stays
   an expiring override (plan 079 ledger). Overlay chip "night ends in 12m".
5. Tests: window edges, wrap past midnight, drift refit inside / outside the
   band, held read, override precedence, ASCII.

## Out of scope

Any game input or memory read; time read only from an operator-taken shot.
