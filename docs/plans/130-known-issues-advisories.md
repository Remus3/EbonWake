# Plan 130 - Known-issues advisories: stop learning from bad numbers

Status: open. Source: deep dive 0025 (NA Known Issues notice, read
2026-10-14, updated 2026-10-09). Lane hint: `data`. Depends on: 064, 116, 060.

Problem: the official Known Issues notice lists live defects that make EW's
derived numbers wrong without any EW fault, and EW has no way to say so:
Trading EXP under-granted since the 2026-10-08 maintenance (Imperial delivery
and fish sales), Lv 59 at 99.99 % cannot level from quest EXP, Season-server
fishing EXP over-granted, Agris Fever cost change landing 2026-10-15, an event
item becoming sellable 2026-10-15. Plan 116 learns XP rate from samples and
plans 035 / 036 price enhancement; a sample taken inside a known defect window
skews the level ETA, and the operator sees an unexplained gap.

## Slices

1. Data file `server/ew/data/known_issues.json` (hand-curated, sourced,
   ASCII): `{"id","title","affects":[leveling|trading|enhance|market|
   books],"from","until"|null,"source","verified"}`. Seed with the four items
   above; each row cites the notice and read date. No scraping: plan 064's
   notice import may later suggest rows, suggest-only.
2. `GET /api/known-issues?area=` returns active rows (now between from and
   until). Pure function `active(now, area)`; times stored UTC.
3. Leveling: an XP sample whose time falls in an active `leveling` or
   `trading` window is tagged `suspect` and excluded from the rate fit (still
   shown, greyed); the Leveling card shows one chip "known issue: <title>".
4. Enhance and Market cards show the same chip for their area; the Agris
   Fever row flips from "pending" to "applied" at its `from` date.
5. Tests: window edges (inclusive from, exclusive until), area filter,
   suspect sample excluded from the rate, chip rendering (node test), ASCII.

## Out of scope

Fetching the notice automatically (plan 064 owns notice import); any game
input. Read-only data only.

## As-built

- `server/ew/knownissues.py` (validate / load / state / active / suspect),
  `server/ew/data/known_issues.json` (6 rows), `GET /api/known-issues?area=`
  (400 on an unknown area; `error` carries a bad-file message).
- Leveling view: each sample carries `suspect` (row id or null); suspect
  samples are dropped before `rate_pct_h` (both the segment and the fallback
  fit). Tagged at read time, never stored, so a curated row edit re-tags old
  samples.
- Chips: `C.knownIssueChips(body, area)` (base part); Leveling card, Deadeye
  "Enhancement plan" card (area `enhance`), Market "Watchlist" card. Suspect
  samples are greyed (`ew-stale`) with a `suspect` label.
- Tests: `tests/test_known_issues.py`, `app/test/known_issues.test.js`.

## As-built deviations

1. Trading EXP row affects `trading` only, not `leveling`. Alternatives: tag
   combat XP samples during the trading window as the plan text says.
   Why: Trading EXP is life-skill EXP; the Leveling rate is combat level %,
   and an open-ended trading window would discard every combat sample since
   2026-10-08 (no rate at all for the operator). Reverses if: EW starts
   tracking a life-skill (trade) level rate.
2. Rows carry optional `kind` (defect | change, default defect),
   `exclude_samples` (default true), `level_min` / `level_max` and `note`.
   Alternatives: the plan's bare schema. Why: the Lv 59 stall only taints
   Lv 59 samples; Season-server fishing over-grant only touches season
   characters, which EW cannot identify, so it is chip-only
   (`exclude_samples: false`); `kind: change` gives the Agris Fever
   pending -> applied flip without a special case. Reverses if: the notice
   import (plan 064) needs a different shape.
3. Seed is 6 rows, not 4: added "Enhancement gauge / effects sometimes
   missing" (enhance, same notice) and "Event Bountiful Autumn Pear sellable"
   (market change, 2026-10-15). Agris Fever is area `enhance` (EW's Agris
   stacks live on the enhancement side). Why: without them the Enhance chip
   had only Agris and Market had no row at all. Change rows end 2026-10-29
   (two weeks of "applied"). Reverses if: the operator finds the extra chips
   noisy.
4. Starts not dated by the notice use an assumed `from` (Lv 59 = the
   2026-10-08 maintenance; Season fishing and enhance gauge = the notice update
   date 2026-10-09), stated in each row's `note`. Reverses if: a later notice
   read gives real dates.
5. The `known_issues` file is read once at server start (like xp_epochs /
   deadlines); a curated edit needs a server restart (allowed any time).
