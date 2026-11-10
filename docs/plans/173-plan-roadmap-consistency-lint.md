# Plan 173 - plan doc / ROADMAP consistency lint

Status: proposed. Source: research 0046.

## Problem

Plan docs (docs/plans/NNN-*.md) and ROADMAP rows are linked only by habit.
A doc with a wrong first-line number, a duplicate number, or no row, or a row
whose cited doc is missing, goes unnoticed until the loop ingests it.

## Scope

1. A test checks: each plan doc's first line is `# Plan NNN - Title` with NNN
   equal to its filename prefix; no number repeats; each doc has a ROADMAP row
   `| NNN | ... |`; any `docs/plans/...` path cited in a row exists.
2. Rows without a doc are allowed (order rows); a legacy allow-list holds
   the current exceptions, so the lint only fails on new drift.
3. ASCII-only messages naming the offending number.

## Tests

Failing test first with fixture docs in tmp_path (bad number, duplicate,
missing doc), then one run over the real tree.

## Depends-on

None

## As-built

`tools/plan_lint.py` (lint, stale_allow, CLI `python tools/plan_lint.py
[--root DIR] [--no-legacy]`, exit 1 on findings) and `tests/test_plan_lint.py`
(10 fixture tests in tmp_path, 2 real-tree tests). Real tree at landing: 0
first-line, 0 duplicate, 0 missing-doc findings; 9 no-row exceptions (089,
090, 121-126, 162) held in `LEGACY`.

## As-built deviations

1. A row in `docs/plans/ROADMAP-history.md` satisfies "each doc has a row".
   Alternatives: ROADMAP.md only (would force allow-listing every archived
   plan). Why: the ROADMAP header names the history file as where finished
   rows go. Reverses if: archived rows stop carrying their plan number.
2. Added `stale_allow` and a real-tree test that every LEGACY entry still
   matches a finding, so the allow-list can only shrink. Alternatives: a
   static list nobody prunes. Why: scope item 2 ("only fails on new drift")
   is kept honest only if fixed exceptions leave the list. Reverses if: the
   list must hold pre-emptive entries.
3. "No number repeats" is checked over plan doc filenames only, not ROADMAP
   row numbers. Alternatives: also flag repeated row numbers. Why: the plan's
   problem statement is doc drift; row duplicates belong to the loop's ROADMAP
   parser. Reverses if: a duplicate row number is seen to misroute the loop.
