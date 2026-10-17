# Plan 150 - Hardening audit tests-a: tests/test_[a-l]*.py plus tests/conftest.py (test hygiene and coverage gaps)

Status: open (operator order 2026-10-17, session 36: "after completing the
found new tasks - do a full deep audit file by file for hardening and
bug/issue corrections"). Lane hint: `build`.

Goal: read every file in this slice IN FULL, line by line, and fix real
defects. Slice sized to fit one lane run (lane_timeout_s 5400; adjudicator
ruling session 36: 12 slices of about 7k lines, plans 141-152).

## Files

tests/conftest.py and every tests/test_[a-l]*.py file, plus any tests helper module.

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
3. Record every finding in `docs/audit/20261017-tests-a.md`: one row per
   finding with ID (TESTS-A-NN), file:line, severity (H/M/L), what was
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

## Proposed ROADMAP rows

| NNN | Server config defaults follow the injected path: `config_market` / `config_market_watch` / `config_hash` honour `config_path` (server/ew/app.py:136-195), `loopstatus.main_root` resolves a relative gitdir (TESTS-A-01 root cause, TESTS-A-15) | [ ] open |
| NNN | Test hygiene follow-ups from plan 150: leveling fixtures off tracked epoch / issue data (TESTS-A-16), shared HTTP helper module instead of `from tests.test_x` (A-17), per-test git marks in test_ew_loop (A-18), git global config isolation (A-19), eventnotices fixture list (A-25), launch spawn path (A-26), grind old-session refill (A-27), deadeye reject-leaves-state (A-28) | [ ] open |

## As-built deviations

1. Reading split across six foreground read-only reader agents (about 3.5k
   lines each); every candidate finding was re-checked against the code
   before it was accepted or fixed here. Alternatives: one inline read of
   20.5k lines (exceeds one context window), sampling (forbidden by the
   method). Why: full line-by-line coverage inside one lane run. Reverses if:
   the lane prompt forbids foreground sub-agents outright.
2. TESTS-A-01 fixed in the test harness (new `tests/ew_hermetic.py`, installed
   from conftest, autouse) instead of editing about 20 fixtures and the
   server. Alternatives: pass `config_path` / `market_client` / `profile_cfg`
   in every fixture (misses `config_market`, which ignores `config_path`, and
   the next new fixture); change server/ew/app.py (outside this tests slice,
   FILED as a row). Why: one root-cause guard covers every current and future
   test, including tests outside this slice. Reverses if: the server row lands
   and every default follows `config_path` (the urlopen guard stays).
3. Test-hygiene FIXED rows (the defect is in the test itself) carry
   "hygiene" in the audit doc's test column instead of a red-before-fix run:
   making them red needs breaking the code under test first. Reverses if: an
   adjudicator requires mutation runs for test-only fixes.
4. The FLEET item 12 progress file in the main checkout was not written:
   this run was not granted writes outside its worktree. Reverses if: the
   lane grant includes the progress path.
