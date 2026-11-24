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

## As-built deviations (build lane, self-adjudicated 2026-11-24)

Built: `data/dst_windows.json`, `bosses.load_windows()` / `dst_windows()` /
`dst_pending()` / `dst_info()`, `_spawn` / `next_spawns(windows=)` rows carry
`shift_h` + `window` {source, ends, verified, derived}, `GET /api/bosses`
`dst` {shift_h, start_utc, end_utc, ends_pt, source, verified, derived},
`signals` data reason `dst_unverified`, `EWCore.bossDstBanner`, Today card
banner, overlay `#ov-boss-dst`. Tests: `tests/test_dst_windows.py`,
`app/test/bosses.test.js` (plan 176 block).

1. Window start = the maintenance START (`maintenance.json` 07:00 UTC Thu),
   end = the clock change instant; a slot is in the window when its TABLE
   instant (PT wall clock) is in [start, end). Alternatives: maintenance end
   (no spawn falls inside maintenance, so equal in practice); the shifted
   instant (circular at the edge). Why: one comparison, matches the notice's
   "from the maintenance until 02:00". Reverses if: a notice names a
   different start (list the window explicitly).
2. Spring 2026 listed with `verified: false` (search snippet only, never
   fetched), so it reads "expected" like a derived window. `verified` is
   false or a read date. Alternatives: mark it verified. Why: only a read
   notice counts. Reverses if: the notice is fetched and read.
3. Derived windows are computed for now.year-1..+1 and dropped where a listed
   window overlaps. Fall 2027 derives to 2027-11-04 .. 11-07 (first Sunday of
   November is 11-07).
4. Digest line = plan 073 `data` row (the plan 174 row), reason
   `dst_unverified`, level warn, hint `data.dst_unverified`; contradicted /
   patch_newer win and carry the DST line as an extra line. Alternatives: a
   new digest row; the `boss_drift` row (its source is unwired). Why: reuses
   the suggest-only data-verification path. Reverses if: DST lines prove
   noisy beside patch lines.
5. Banner text is built in JS (`bossDstBanner`) from the server `dst` field
   (window in force now, else the window holding the next shifted spawn);
   "official DST notice" only when `verified` is a date, else "expected".
   Overlay: a span inside `ov-boss-row` (wraps to its own line), not a new
   OVERLAY_ROWS row. Why: no change to the pinned row order / context tests.
   Reverses if: the overlay gets per-row layout config for banners.
6. Existing tests changed: `test_next_spawns_shape_and_order` (new keys) and
   `test_next_spawns_across_fall_back` (the Sun 00:00 slot on 2026-11-01 now
   spawns 01:00 PDT per the notice; the 10:00 PST slot is unchanged).
7. Reset (plan 021) untouched: `today.next_daily_reset` stays 00:00 UTC
   (test pins it inside the window). No reset card change.
8. Progress file `progress/p176-build.json` could not be written: writes
   outside the worktree were refused by the lane's permission mode. Reverses
   if: the lane is granted that one path.
