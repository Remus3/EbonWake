# Plan 140 - Weekly silver goal: target, pace and projection from session and sales ledgers

Status: open. Source: research 0029 finding C1 (plan 134). Lane hint:
`build`.

Problem: EW measures silver (grind log silver/h `server/ew/grind.py:70`,
session silver delta `:1351`, silver-OCR rate and delta
`server/ew/ocrinfer.py:772,814`, sold-items ledger plan 123) but never says
whether this week is on pace, the question that sizes a grind session.

## Slices

1. Tests first: `tests/test_silvergoal.py` for pure
   `server/ew/silvergoal.py`:
   - week = the plan 021 weekly reset window (NA, the same rule the Today
     weeklies use); no new reset constant.
   - `earned_week(sources, week)`: sum of grind-session silver (auto rows of
     plan 112 and typed rows) plus sold-items net (plan 123), de-duplicated so
     a sale is not counted twice when a silver-OCR delta also covers it
     (sales win; the OCR delta fills only gaps).
   - goal: an explicit override (plan 079 ledger key `grind.week_goal`,
     expiring with the week) else the median of the last 4 full weeks'
     earned plus 10 percent, else none (card hidden, zero-touch).
   - `pace`: needed per remaining day, projection at the trailing 7-day
     rate, `on_track` bool; all integer silver.
2. `GET /api/silvergoal` read-only; the goal override uses the existing
   override write route (no new POST route).
3. Grind tab card "This week": earned / goal bar, needed per day, projection;
   What-now (plan 069) gains one suggestion only when `on_track` is false and
   the game is running. `app/test/silvergoal.test.js` for the render helpers.

## Acceptance

- New Python and app tests green; ruff green.
- With 4 weeks of fixture history and no override the goal equals median
  plus 10 percent; an override wins until the weekly reset.
- A sale also seen as an OCR silver delta is counted once.

## Game ToS

Reads EW's own ledgers built from operator screenshots, the session log and
public APIs; no game input, memory read or client file.

Depends on: none.
