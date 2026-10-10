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
