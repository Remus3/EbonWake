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
