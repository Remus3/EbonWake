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

## As-built deviations

1. Slice 1 trigger. Decision: the Events tab re-reads
   `/api/events/currency` on the SSE `today` push (an `event_tick` /
   `event_untick` is a POST /api/today, which bumps only `today`) and swaps
   the block in with `withCurrency()` (events.part.js). A wishlist / balance
   edit does NOT re-read: its POST /api/events reply is already the full
   events body with `currency`, which `send()` accepts. Alternatives: a GET
   after every wishlist POST (a duplicate read of data in hand); a server
   bump of `events` on event ticks (Python change, full-body refetch - what
   the plan retires). Why: the light read lands exactly where data changed
   without a new GET. Reverses if: a currency-changing op moves off the
   events POST reply.
2. Slice 3 placement and formatter home. Decision: the Data checks list is a
   `<details>` inside the Signal health card (plan 073 renamed the plan 020
   freshness card), fed by `/api/data/verdicts` in the same `pollVersion`
   round as `/api/signals`; `verdictRows()` lives in base.part.js next to
   `signalRows()` and lists contradicted then confirmed rows (silent rows
   are neither listed nor counted). Links reuse
   `EWToast.linkButton` (allowlisted hosts, ew:open-external). Alternatives:
   a separate "Data checks" card; listing silent rows. Why: one card for data
   health; silent rows have no evidence to show. Reverses if: the operator
   asks for silent rows or a separate card.
3. Slice 4 guard scope. Decision: a route counts as consumed only by a
   quoted literal (`'/api/x'`, `'/api/x?...'`) in non-test app/ JS or HTML;
   comment mentions and prefixes do not. The allowlist is empty: every GET
   route has a consumer after slices 1-3. Alternatives: substring match
   (a doc comment would satisfy it). Why: a comment is not a consumer.
   Reverses if: a route is legitimately built dynamically (add it to ALLOW
   with its reason).
4. Desktop self-test not run in the lane (headless worktree, no Electron
   window). The node tests pin the fetches, the details nodes and the empty
   states; the loop's merge / session self-test covers the render. Reverses
   if: the self-test shows either block missing.
5. Progress file: the lane's sandbox refused writes to the main checkout's
   `ops/loop/control/progress/p110-build.json` (and python outside
   pytest / ruff), so no item-12 progress was written this run.
