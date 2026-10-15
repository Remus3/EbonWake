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

## As-built

`server/ew/daynight.py` (pure clock, tooltip parser, `DayNightService`),
`server/ew/data/daynight.json`, OCR kind `gametime` in `ocrauto`, ledger key
`grind.night` in `data/override_policy.json`, `GET /api/daynight`, grind
`drops.night` + the night row's via `clock|override`, overlay chip
`C.nightChip` on the Grind row. Tests: `tests/test_daynight.py`,
`app/test/daynight.test.js`.

Clock model: phase 0..1 of the cycle, 0 at night start; night is the first
night_min / period_min of it, and game time maps piecewise-linearly (night
22:00-07:00 runs faster than day). A re-read within TOL_MIN (3 real min) of
the prediction confirms; else the period is refit from the chain's first read
(`n = round(E/P - df)`, `P' = E / (n + df)`) and taken only within BAND (2 %)
of the data period; anything else is held for review.

## As-built deviations

1. Data file carries `night_min` and `titles` beyond the plan's field list.
   Alternatives: a linear clock (night = 9/24 of the period); tooltip hints in
   `ocr_regions.json` like plan 088. Why: the game clock runs faster at night
   (40 real min for 9 game hours), so the night length is a separate figure;
   keeping the hints in the same file keeps the feature in one tracked row.
   Reverses if: a measured calibration shows a linear clock.
2. "Verified" is earned by calibration, not by the plan 085 patch-notes
   verifier. The data row stays `verified: false`; `/api/daynight` reports
   `verified: true` once a second read agreed (inside TOL_MIN or a refit
   inside BAND). Alternatives: a plan 085 `verify` regex block. Why: patch
   notes never print the cycle length, so a regex verdict could never confirm
   it; the plan's own confirmation source is the calibration. Reverses if:
   an official notice states the cycle figures.
3. Typed toggle = ledger key `grind.night` (`days:1`), ended early at the next
   day / night change of the calibrated clock (`retired_by: "clock"`). When the
   clock service is wired, the night row ignores the old stored `drop_on`
   toggle, so an uncalibrated typed toggle now lasts 1 day instead of forever.
   Alternatives: a new `until:night_change` ledger rule; keep the forever
   toggle while uncalibrated. Why: no ledger rule change for one key, and a
   never-expiring night flag is the stale-value defect plan 079 exists to
   remove. Reverses if: the operator wants a sticky manual night.
4. The ledger's "live signal supersedes" rule is not applied to
   `grind.night`: the typed toggle wins over the clock until the next change
   (the plan asks for override precedence). `grind.night` is listed in
   `live_signals()` (signal `game_clock`) so the plan 109 zero-touch guard
   counts it as read, not typed.
5. `gametime` review items are accept / discard only (no typed fix); an
   accept of a held read starts a new calibration chain. Why: a typed game
   time is no better than the read; the screenshot is the evidence.
6. The overlay chip rides the existing Grind row (shown with the grind
   widgets) instead of a new overlay widget: "night ends in 12m" at night,
   "night in 9m" within 15 min of night, "night (typed)" for an override.
   Why: no new widget key / context rule for one chip. Reverses if: the
   operator wants it without the Grind widgets on.
7. The What-now card is not changed (the Problem line names it): it ranks no
   drop-rate source today, so there is no night input to feed. Alternatives:
   a "night ends soon - grind now" action. Why: a new ranked action is new
   scope with its own weight row; the overlay chip covers the glance.
   Reverses if: a later plan adds a drop-rate action to What now.
