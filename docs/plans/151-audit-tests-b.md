# Plan 151 - Hardening audit tests-b: tests/test_[m-z]*.py (test hygiene and coverage gaps)

Status: open (operator order 2026-10-17, session 36: "after completing the
found new tasks - do a full deep audit file by file for hardening and
bug/issue corrections"). Lane hint: `build`.

Goal: read every file in this slice IN FULL, line by line, and fix real
defects. Slice sized to fit one lane run (lane_timeout_s 5400; adjudicator
ruling session 36: 12 slices of about 7k lines, plans 141-152).

## Files

every tests/test_[m-z]*.py file.

## Method

1. Read each file completely (no skimming, no sampling). For each, check:
   unvalidated input (HTTP bodies, query params, OCR text, JSON files,
   env / config), path traversal and unsafe joins, non-atomic writes
   (must be tmp then replace), swallowed or over-broad exceptions that hide
   failures, resource leaks (files, sockets, subprocesses, timers, listeners),
   missing timeouts on network / subprocess calls, races on shared state and
   files, unbounded growth (lists, caches, logs), time-zone / DST / clock
   errors, off-by-one and None / empty handling, HTML injection in the
   dashboard / overlay (untrusted text into innerHTML), bind address other
   than 127.0.0.1, secrets or machine paths in tracked files, non-ASCII / CRLF,
   dead code, and the Game ToS floor in CLAUDE.md (any input to the game
   window, memory, packets, client files, authenticated market calls is a
   critical finding).
2. Each real finding is fixed root-cause-first (skill root-cause-fix): a
   failing test that reproduces it FIRST, then the minimal fix, then a sweep
   for the same pattern in the rest of the slice. Behaviour that is correct
   stays unchanged; no refactors without a defect.
3. Record every finding in `docs/audit/20261017-tests-b.md`: one row per
   finding with ID (TESTS-B-NN), file:line, severity (H/M/L), what was
   wrong, the test that pins it, and status FIXED / FILED / NOT-A-BUG (with
   why). Also list every file read, so coverage is checkable.
4. A finding too large to fix in this run is FILED: add it under
   "Proposed ROADMAP rows" in this plan doc (`| NNN | title | [ ] open |`,
   next free number at merge time is assigned by the session) - never overrun
   the lane.
5. Never edit ops/fleet_kit/ (vendored, pinned). A kit defect goes into a
   "Kit defects for MAIN" section of the audit doc; the session reports it.

## Acceptance

Audit doc lists every file in the slice as read; every FIXED finding has a
test that failed before the fix; ruff, the touched tests, and (if app/
changed) npm test green; ASCII / LF.

Depends on: 135, 136, 137, 138, 139, 140.

## As-built deviations

1. TESTS-B-03 and TESTS-B-05 are FIXED without a red-then-green test.
   Decision: fix them in place and say so in the audit row. Alternatives:
   leave them (a known-dead assertion and an unjoined thread stay), or invent
   a meta-test (an AST rule for "no assert on a module object" / "every
   started Thread is joined" would be broader than the two defects and flag
   correct daemon threads elsewhere). Why: both defects live inside a test
   body, so the test itself is the only thing that can change; there is no
   production behaviour that fails first. Reverses if: a reviewer shows a
   cheap guard that pins either pattern without false positives.
2. The checklist progress file `ops/loop/control/progress/p151-build.json`
   was not written: every write path to the MAIN checkout (Write tool,
   `python -c` through `fleet_headless.write_progress`, a helper script)
   was refused by this run's permission set. Decision: proceed, record here.
   Alternatives: stop the lane (wastes the run), write it inside the
   worktree (wrong place per FLEET item 12, the widget never reads it).
   Reverses if: the lane prompt's permission set grants that one path.
3. The isolation guard is scoped to tests/test_[m-z]*.py (this plan's
   slice); the a-l half is FILED (row below), not fixed here, so this lane
   never edits the tests-a slice in parallel with its own lane.

refute-rounds: 0/3

## Proposed ROADMAP rows

| NNN | EWServer reads market / profile config from the injected config_path, not REPO_ROOT (TESTS-B-06) | [ ] open |
| NNN | Extend the plan 151 test-isolation guard to tests/test_[a-l]*.py and fix its fixtures (TESTS-B-07) | [ ] open |
