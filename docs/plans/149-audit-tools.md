# Plan 149 - Hardening audit tools: tools/*.py (loop, lanes, launch, leak sweep, eta, hooks installers)

Status: open (operator order 2026-10-17, session 36: "after completing the
found new tasks - do a full deep audit file by file for hardening and
bug/issue corrections"). Lane hint: `build`.

Goal: read every file in this slice IN FULL, line by line, and fix real
defects. Slice sized to fit one lane run (lane_timeout_s 5400; adjudicator
ruling session 36: 12 slices of about 7k lines, plans 141-152).

## Files

every tools/*.py file (ew_loop.py and its loop_*.py split, ew_lane.py, launch.py, leak_sweep.py, eta.py, install_hooks.py, logon_task.py, loop_task.py, ew_tests.py and the rest).

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
3. Record every finding in `docs/audit/20261017-tools.md`: one row per
   finding with ID (TOOLS-NN), file:line, severity (H/M/L), what was
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

None: every finding was FIXED or NOT-A-BUG (docs/audit/20261017-tools.md).

## As-built deviations

1. Slice limited to tools/*.py. Decision: the tools/*.ps1 OCR helpers
   (ocr.ps1, ocr_bench.ps1, ocr_ink.ps1, ocr_prep.ps1) were not audited.
   Alternatives: audit them here too. Why: the plan's Files section names
   `tools/*.py` only and the slice was sized on those lines. Reverses if:
   a later slice plan names the .ps1 helpers.
2. eta.record clamps a negative duration to 0 instead of refusing it
   (TOOLS-01). Alternatives: refuse negatives like NaN. Why: callers
   (`ew_lane.run_lane`'s finally, `eta.py run`) compute wall-clock deltas,
   and a refusal there would raise out of a finally and mask the run's
   result after a clock step back. Reverses if: callers move to a
   monotonic clock.
3. Progress file written in the lane worktree's
   ops/loop/control/progress/p149-build.json, not the main checkout's:
   this run's permissions denied the main-checkout write. The loop reads
   the worktree copy first (`Tick.lane_progress`). Reverses if: lane runs
   get a write grant on the main progress dir.
