# Plan 112 - Grind silver auto: silver-OCR delta across the play session fills the auto grind log row

Status: open (priority). Operator order session 28 (zero-touch wave). Lane
hint: `build`.

Goal: an auto grind session closes with its silver filled, not 0. Minutes
already come from the session log (plan 062); silver comes from the OCR
silver samples taken inside the session window.

State today (read 2026-10-10): `server/ew/grind.py:1144` `auto_stop`
logs the auto session "with 0 silver (a loot import may value it later)".
OCR silver samples land in store domain `silver` with source `ocr:<file>`
(plan 063); `server/ew/ocrinfer.py:503` `silver_rate` already computes a
per-hour rate between the first and last sample inside a play window
(plan 062 `PlaySession.view()` open / last) - used for display only.

Inputs (ToS floor): screenshots the operator took (silver line OCR), the
plan 008 session-log state (play window). Nothing reaches the game.

## Slices

1. Pure `ocrinfer.silver_delta(samples, window)` -> {silver, first, last,
   n, conf} | None: baseline = the last OCR sample at or before the window
   start (within BASELINE_MAX_S, e.g. 6 h) else the first inside; end = the
   last sample inside the window (or within AFTER_LOGOUT_S after its end);
   None with fewer than 2 points; a negative delta (silver spent, e.g.
   repairs, market buys) -> None with why, never a negative row.
2. Fill on close: `PlaySession` close -> `grind.auto_stop(started, at,
   silver=delta)`; when samples arrive after the close (late screenshots
   are read async), a `grind.auto_fill(sid, silver, source)` sets silver on
   that session once, only while it is still 0 and `auto`.
3. Provenance + undo: the session row gains `silver_src: "ocr_delta"` and
   `silver_from` {first_at, last_at, n}; the Grind tab badges it; a typed
   edit of the row's silver replaces it (typed beats derived); undo via the
   existing grind session edit.
4. Spending guard: silver spent mid-session corrupts the delta; when a
   plan 081 / inventory sale or market action is unknown, accept the delta
   only when every consecutive pair is non-decreasing beyond a small
   tolerance; otherwise sum the positive steps and set conf < 1 with why.

## Tests first

- `tests/test_grind_silver_auto.py`: baseline before start + last inside
  -> delta; no baseline, 2 inside -> delta; 1 point -> None; negative ->
  None; late sample fills a 0 auto session once and never overwrites a
  typed value; a dip mid-session sums positive steps with lowered conf;
  manual (non-auto) sessions untouched.
- `app/test/grind.test.js`: the `ocr_delta` badge text.

Acceptance: a fixture play window with three OCR silver samples closes to a
grind row with the hand-computed silver and silver/h; gates green; verifier
PASS within 3 rounds; one push.

Retires: typing silver into an auto-closed grind session.

Depends on: 062, 063.

## As-built deviations

1. No grind session edit existed. Decision: a new POST `/api/grind`
   `{"edit": {id, silver}}` (`GrindService.edit`) sets silver and marks the
   row `silver_src: "typed"`, dropping `silver_from`; the Grind tab makes an
   auto row's amount clickable (Enter saves). Alternatives: delete + re-log
   (loses started / minutes), a general all-fields edit (scope creep). Why:
   the smallest surface that lets typed beat derived and undo a bad delta.
   Reverses if: a general session edit lands; it subsumes this op.
2. The delta is computed inside `grind.auto_stop` (reading store domain
   `silver`) instead of `PlaySession` passing it in; `auto_stop(started, at,
   silver=None)` still takes a precomputed delta. Late fill is
   `grind.refill_silver()`, run from the app's AutoOcr `on_change` notifier
   (every commit / undo), which calls `auto_fill(sid, delta)` on the newest
   closed auto session (ended within 24 h) that is still 0 and unsourced.
   Alternatives: a play-window -> grind-sid map in `playsession` (more state,
   same result: the auto session's started == the play window start). Why:
   no new cross-service wiring; idempotent. Reverses if: auto sessions stop
   sharing the play window's start.
3. `silver_delta(samples, window, why=None)`: None cannot carry a reason, so
   the why is appended to an optional list. Zero gain is also None (a 0 row
   is the unfilled default). With a dip beyond tolerance (0.1 percent of the
   balance) the gains are summed at conf 0.6 even when the net is negative
   (spent more than earned); only an all-falling series is None. Why: slice
   4's guard covers the net-negative-with-gains case better than a bare None.
   Reverses if: a plan 081 sale / market action feed makes spends known.
4. `auto_stop` now returns the new session id (truthy) instead of True.
   Auto sessions carry `auto: true` so a late fill never touches manual rows.
