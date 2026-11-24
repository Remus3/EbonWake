# Plan 176 - DST transition window: boss times and reset display shift for three days

Status: open. Deep dive 2026-11-24 (research 0052 section 3). Lane hint: `data`.
Depends on: 031.

Spec gap: the official NA DST notice (2026-10-22) shifts every NA boss spawn
one hour later from the 2026-10-29 maintenance until 2026-11-01 02:00 PT
(spring: one hour earlier from the maintenance before the March change until
that Sunday), then returns to the PT wall clock. The Daily Reset stays on UTC.
`server/ew/bosses.py` assumes PT wall clock always, so next-spawn, the
5 / 15-minute notification and the overlay are one hour wrong inside the window.

1. Data: `server/ew/data/dst_windows.json` lists windows {start_utc, end_utc,
   offset_hours, source, verified}: 2026-10-29 maintenance to 2026-11-01
   02:00 PT (+1), spring 2026 (-1). Future windows are DERIVED by rule (the
   Thursday maintenance before the US clock change to the change) and marked
   `derived` until an official notice is read.
2. `next_spawns` applies the window offset to every slot whose spawn falls in
   it; the API carries `shift_h` and `window` (source, ends).
3. Bosses card and overlay widget show one banner line "NA times +1 h until
   Sun 02:00 PT (official DST notice)"; derived windows read "expected".
4. Reset countdown (plan 021): the daily reset stays UTC; the card must not
   shift.
5. Plan 174 digest line when a window is within 7 days and not `verified`.
6. Tests: `tests/test_dst_windows.py` - a slot inside the window moves 1 h,
   outside does not, spring window moves -1 h, reset unchanged, derived
   marked, no network.

Acceptance: next-spawn for 2026-10-30 reads +1 h against the table, 2026-11-02
reads the table time; gates green; verifier PASS within 3 rounds; one push.

ToS check: static data and local time arithmetic; no network, no game input.
