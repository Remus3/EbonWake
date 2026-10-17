# Plan 157 - Extend the test-isolation guard to tests/test_[a-l]*.py

Status: open (follow-on of the 20261017 hardening audit, session 36). Source:
TESTS-B-07 (docs/audit/20261017-tests-b.md). Lane hint: `build`.

## Problem

Plan 151 added a guard that fails a test touching live repo state; it covers tests/test_[m-z]*.py only.

## Slices

1. Extend the guard's scope to every tests/test_*.py file; run it, and fix each a-l fixture it flags (tmp_path roots, no writes under the repo).
2. Keep the guard fast (no extra whole-suite run); record the extension in docs/audit/20261017-tests-b.md.

## Acceptance

Each slice's test failed before the fix and passes after; ruff, touched tests
and (if app/ changed) npm test green; ASCII / LF; the audit doc row for each
source ID is updated to FIXED with this plan number.

Depends on: 151, 156.
