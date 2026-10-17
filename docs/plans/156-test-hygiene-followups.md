# Plan 156 - Test hygiene follow-ups from the 20261017 audit

Status: open (follow-on of the 20261017 hardening audit, session 36). Source:
TESTS-A-16, -17, -18, -19, -25, -26, -27, -28 (docs/audit/20261017-tests-a.md). Lane hint: `build`.

## Problem

The tests-a slice filed eight hygiene gaps it could not finish in one run: leveling fixtures read tracked epoch / issue data (A-16), tests import helpers via `from tests.test_x` (A-17), test_ew_loop git marks are module-wide (A-18), git global config is not isolated (A-19), eventnotices fixture list (A-25), launch spawn path (A-26), grind old-session refill (A-27), deadeye reject-leaves-state (A-28).

## Slices

1. For each ID: the change named in the audit doc row, test-only unless the audit row says a product defect sits under it (then failing test first, minimal fix).
2. A shared tests/_http.py (or similar) helper module replaces cross-test-module imports (A-17).
3. Record each ID as FIXED in docs/audit/20261017-tests-a.md (append a 'Follow-up plan 156' column note).

## Acceptance

Each slice's test failed before the fix and passes after; ruff, touched tests
and (if app/ changed) npm test green; ASCII / LF; the audit doc row for each
source ID is updated to FIXED with this plan number.

Depends on: 150, 155.

## As-built deviations

1. Helper module names. Decision: `tests/ew_testkit.py` (HTTP, Clock, bmp,
   FakeWatch) and `tests/ew_loopkit.py` (the ew_loop worlds), not
   `tests/_http.py`. Alternatives: one `_http.py` holding only the HTTP
   helpers. Why: the imports also carried portrait, clock and loop helpers,
   and tests/ helper modules are named `ew_*.py` (ew_tiers, ew_hermetic).
   Reverses if: a helper module naming rule is set for tests/.
2. A-17 scope. Decision: the 3 bare `import test_ew_loop` / `from
   test_ew_loop import` (same module object, so no double run) moved too.
   Alternatives: only the 8 `from tests.test_x` imports. Why: the audit row's
   second cost is coupled test files, and the A-19 isolation needed one home
   for the git helpers. Reverses if: never (no behaviour depends on it).
3. A-19 and `ew_loop.tree_key`. Decision: test-only; git_world writes LF files.
   Alternatives: make `tree_key` keep GIT_CONFIG_* while dropping the other
   GIT_* variables (a tools/ change). Why: the loop never runs with
   GIT_CONFIG_* set, so it is no product defect, and the plan is test-only
   unless the audit row names one; with LF files a host autocrlf cannot change
   a tree hash. Reverses if: the loop is ever run with GIT_CONFIG_* set.
4. Red-before-fix. A-25 to A-28 add coverage over correct product code, so
   their new asserts pass on the first run (as the audit rows expected: no
   product defect). A-16 / A-17 / A-18 / A-19 each have a test that was red
   before the change.
5. Progress file. `ops/loop/control/progress/p156-build.json` in the main
   checkout could not be written: this run was not granted writes outside
   the worktree (the same gap plan 150 noted).

refute-rounds: 0/3 (lane build; the loop's verifier runs the review)
