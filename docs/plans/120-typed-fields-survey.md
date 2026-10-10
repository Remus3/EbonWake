# Plan 120 - Remaining typed-fields survey and automation plans

Status: done by the build lane 2026-10-10 (see As-built deviations). Lane
hint: `build`.

Goal: list every operator-typed field the EW server still accepts (pets,
mounts, inventory LT, crafting and the rest) with a candidate live source
inside the Game ToS floor, and write deduped automation plans + ROADMAP rows
for the viable ones.

Inputs (Game ToS floor): the EW tree only (`server/ew/app.py` POST routes,
the domain modules, `ocrauto.KINDS`, the profile and notice readers). No
fetch, nothing reaches the game.

## Slices

1. Survey: `docs/research/0021-typed-fields-survey.md` - one row per POST
   route / typed op, its live source today and a verdict (AUTO, INTENT,
   VIABLE, NO SOURCE), with what would reverse each NO SOURCE call.
2. Plans: one doc per viable automation, numbered from 121, each with
   slices, tests first, acceptance and a `Depends on:` line.
3. Guard: `tests/test_typed_fields_survey.py` - every `POST_ROUTES` path is
   in the survey (a new typed route without a survey row fails), every
   proposed row has its plan doc, and no proposed title duplicates an earlier
   plan or another proposed one under `loop_roadmap.is_duplicate` (the loop's
   own deep-dive dedup rule).

## Acceptance

Survey covers every POST route; plans 121-126 exist, are well-formed and
deduped; the guard test, ruff and the ASCII / LF test are green.

Depends on: none.

## Proposed ROADMAP rows

| 121 | Pet window OCR fills the pets roster: pet list / info shots set species, tier, talents; typed stays a newer-wins override (plan docs/plans/121-pet-window-ocr.md; depends on 111) | [ ] open |
| 122 | Horse information OCR fills mounts and T10 breed materials; Royal Fern Root rate derived from count reads (plan docs/plans/122-horse-info-ocr.md; depends on 111, 113) | [ ] open |
| 123 | Warehouse storage and sold-items ledger from OCR: per-town used / total and a deduped sales log into the VP ledger (plan docs/plans/123-warehouse-market-sales-ocr.md; depends on 111) | [ ] open |
| 124 | XP book stock and Imperial delivered count from reads: loot reads add books, delivery window remaining sets delivered (plan docs/plans/124-xp-book-stock-imperial-delivered.md; depends on 113, 117) | [ ] open |
| 125 | Crafting recipe catalog data file: pick a recipe instead of typing it, robots-checked source (plan docs/plans/125-crafting-recipe-catalog.md; depends on 054) | [ ] open |
| 126 | Stored failstack bank and enhance step completion from OCR (plan docs/plans/126-stored-failstacks-step-done-ocr.md; depends on 118) | [ ] open |

## As-built deviations

1. No plan doc existed. Decision: the lane wrote this doc first from the
   ROADMAP row text. Alternatives: block and ask. Why: the row is
   self-describing and the operator standing order says self-adjudicate.
   Reverses if: never (a doc now exists).
2. ROADMAP rows not written to `docs/plans/ROADMAP.md`. Decision: the six
   rows are in "Proposed ROADMAP rows" above, verbatim in the ROADMAP table
   format, for the merging loop / next session to append when it flips row
   120. Alternatives: edit ROADMAP.md in the lane (forbidden by the lane
   order: parallel lanes editing it collided); a hand-off bullet (the lane may
   not edit `EW-NEXT-SESSION.txt`). Why: the lane order outranks the plan's
   "write ROADMAP rows" wording; the rows lose nothing by waiting for the
   merge. Reverses if: the loop gains a step that ingests proposed rows from
   a plan doc (then it reads this section).
3. Six plans, not capped at 2. Decision: every viable automation got a plan.
   Alternatives: the deep-dive cap `loop.max_new_plans_per_day` (2). Why:
   that cap governs the idle deep-dive lane, not an ordered survey whose row
   asks for plans "for the viable ones"; the dedup rule still applies and is
   tested. Reverses if: the loop's extra_checks start applying the cap to
   build lanes.
4. Progress file. Decision: no `ops/loop/control/progress/p120-build.json`
   was written. Alternatives: Write tool / a kit `write_progress` helper
   script. Why: both were refused by this headless lane's permission policy
   (writes outside the worktree and running a non-module Python script need
   approval); the lane ran inline and short. Reverses if: the lane policy
   allows the kit helper (then call `fleet_headless.write_progress`).
5. Crafting catalog (125) lane hint `data`, no fetch in this lane.
   Decision: the source ruling (robots.txt) is slice 1 of plan 125.
   Alternatives: fetch now. Why: this lane is a survey; a fetch belongs to
   the plan that writes the data file. Reverses if: never.
