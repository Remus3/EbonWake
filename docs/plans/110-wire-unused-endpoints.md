# Plan 110 - Wire built-but-unused endpoints into the dashboard: events/currency, zones/xp, data/verdicts

Status: open (priority). Operator order session 28 (zero-touch wave: data
EW already computes must show without the operator going looking). Lane
hint: `build`.

Goal: every GET endpoint the server builds has a dashboard consumer (or is
named on an allowlist with the block that already carries its data), so a
finished feature is visible with no manual step.

State today (read 2026-10-10, `grep -rn` over `app/`): no dashboard or
ewcore JS calls these three routes in `server/ew/app.py`:
- `/api/events/currency` (plan 095, `app.py:921`). Its data already
  reaches the Events tab inside the `/api/events` body (`currency=` at
  `app.py:748`), so the route is a duplicate read; the Events tab refetches
  the whole events body after `event_tick`.
- `/api/zones/xp` (plan 088, `app.py:955`, `zoneinfo.ZoneXpService.view`:
  per-zone recommended level, per-kill EXP, kills-to-level, cap_pct). Only
  `by_spot` (spot recommender) and `here` / `cap_bound_here` (leveling,
  context) are consumed; the zone table itself is never shown.
- `/api/data/verdicts` (plan 085, `app.py:986`,
  `dataverdicts.VerdictService.view`: confirmed / contradicted / silent per
  hinted data row, unchecked rows, last notice). Only the plan 073 `data`
  signal row (counts) and per-row badges reach the UI.

Inputs: the existing local endpoints only. No new host, no new GET.

## Slices

1. Events: after an `event_tick` / `event_untick` / wishlist edit, refresh
   only the currency rows from `/api/events/currency` (light read) instead
   of the whole events body; pure merge helper in
   `app/shared/core/events.part.js`.
2. Leveling: a "Zones" details table on the Progress / leveling card from
   `/api/zones/xp`: zone, recommended Lv, EXP per kill, kills to next level,
   cap-bound flag, read age; sorted by recommended level; empty state "Take
   a screenshot of a Monster Zone Info panel to fill this" (no input
   needed beyond the screenshot the operator already takes). Pure
   formatter `zonesRows()` in `app/shared/core/leveling.part.js`.
3. System: a "Data checks" details list on the System freshness card (plan
   020) from `/api/data/verdicts`: contradicted rows first with evidence +
   date + patch-notes link, confirmed count, unchecked count, last notice
   date. Pure formatter `verdictRows()` in a core part.
4. Guard: `app/test/endpoint_consumers.test.js` scans the GET routes in
   `server/ew/app.py` (regex over `if path == "/api/...` lines) and asserts
   each one appears in `app/` JS or on an allowlist in the test with the
   reason (embedded in another body, overlay-only, health contract). The
   Python side gets nothing new.

## Tests first

- `app/test/zones.test.js`: `zonesRows` sorting, kills-to-level text,
  cap-bound badge, empty state.
- `app/test/verdicts.test.js`: contradicted first, link text, counts line,
  error state.
- `app/test/eventcurrency.test.js`: the merge helper replaces only the
  currency rows.
- `app/test/endpoint_consumers.test.js`: the slice 4 guard (fails today on
  the three routes).

Acceptance: `npm test --prefix app` green with the guard; on the desktop
self-test the Zones table and Data checks list render (empty states
included); gates green; verifier PASS within 3 rounds; one push.

Retires: the manual curl / API look-up the operator would need to see zone
EXP or data verdicts.

Depends on: 088, 085, 095.
