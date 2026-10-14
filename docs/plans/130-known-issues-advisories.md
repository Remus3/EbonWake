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

## As-built deviations

None yet.
