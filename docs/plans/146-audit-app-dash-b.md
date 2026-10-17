# Plan 146 - Hardening audit app-dash-b: app/dashboard/ home.js through today.js plus their app/test files

Status: open (operator order 2026-10-17, session 36: "after completing the
found new tasks - do a full deep audit file by file for hardening and
bug/issue corrections"). Lane hint: `build`.

Goal: read every file in this slice IN FULL, line by line, and fix real
defects. Slice sized to fit one lane run (lane_timeout_s 5400; adjudicator
ruling session 36: 12 slices of about 7k lines, plans 141-152).

## Files

app/dashboard/home.js, imperial.js, index.html, inventory.js, leveling.js, market.js, overrides.js, palette.js, pets.js, progress.js, settings.js, toast.js, today.js, and the matching app/test/*.test.js.

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
3. Record every finding in `docs/audit/20261017-app-dash-b.md`: one row per
   finding with ID (APP-DASH-B-NN), file:line, severity (H/M/L), what was
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

None: every finding was FIXED or NOT-A-BUG (`docs/audit/20261017-app-dash-b.md`).

## As-built deviations

1. Regression tests for the three fixes live in one new file,
   `app/test/dash_b_hardening.test.js`, which runs toast.js, pets.js and
   progress.js in a vm against a minimal fake DOM (same approach as
   overlay_context.test.js). Alternatives: add a test to each module's own
   test file (pets.test.js, progress.test.js; toast.js has none) and
   duplicate the fake DOM three times. Why: the existing per-module files are
   pure-helper / static tests with "No DOM" in their headers; one shared rig
   keeps them unchanged. Reverses if: a shared app/test DOM helper is added,
   then these tests move next to their modules.
2. The progress file `ops/loop/control/progress/p146-build.json` in the main
   checkout could not be written: the write was denied by the permission
   layer in this run. Alternatives: write it through a shell or kit helper
   (would bypass the denial). Why: a denied write is not retried by another
   path. Reverses if: the lane's permission profile allows that path.
