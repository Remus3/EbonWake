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
