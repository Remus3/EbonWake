# Plan 152 - Hardening audit ops-ci-config: ops/ non-kit files, .github/, config templates, root files

Status: open (operator order 2026-10-17, session 36: "after completing the
found new tasks - do a full deep audit file by file for hardening and
bug/issue corrections"). Lane hint: `build`.

Goal: read every file in this slice IN FULL, line by line, and fix real
defects. Slice sized to fit one lane run (lane_timeout_s 5400; adjudicator
ruling session 36: 12 slices of about 7k lines, plans 141-152).

## Files

ops/loop/slots.py and every other ops/ file outside ops/fleet_kit/ and gitignored runtime dirs, .github/workflows/*.yml and dependabot config, config/local.example.json, pytest.ini, ruff / pyproject config, .gitignore, .gitattributes, README.

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
3. Record every finding in `docs/audit/20261017-ops-ci-config.md`: one row per
   finding with ID (OPS-CI-CONFIG-NN), file:line, severity (H/M/L), what was
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

None. The four FILED findings (OPS-CI-CONFIG-07..10) are all in the
byte-pinned shared `ops/loop/slots.py` and go to MAIN as kit defects
(`docs/audit/20261017-ops-ci-config.md`, "Kit defects for MAIN"), not to an
EW row.

## As-built deviations

1. Slice widened to ci/requirements-*.{in,txt}, NOTICE, SECURITY.md,
   CONTRIBUTING.md and conftest.py. Alternatives: README only as the sole
   named root file. Why: the plan says "root files" and the workflow installs
   the ci/ pins, so they are CI config. Reverses if: a later slice owns them.
2. Progress file `ops/loop/control/progress/p152-build.json` not written: the
   lane's permission set denied the write to the main checkout and the run of
   a helper script (both refused at the tool layer). Alternatives: write it
   in the worktree (wrong location per FLEET item 12). Why: no permitted path;
   the loop's own lane progress covers the run. Reverses if: the lane
   settings grant that one path.
