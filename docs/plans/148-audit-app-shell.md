# Plan 148 - Hardening audit app-shell: Electron shell: main.js, preloads, overlay, selftest, tray, ew.css

Status: open (operator order 2026-10-17, session 36: "after completing the
found new tasks - do a full deep audit file by file for hardening and
bug/issue corrections"). Lane hint: `build`.

Goal: read every file in this slice IN FULL, line by line, and fix real
defects. Slice sized to fit one lane run (lane_timeout_s 5400; adjudicator
ruling session 36: 12 slices of about 7k lines, plans 141-152).

## Files

app/main.js, app/preload.js, app/overlay/index.html, app/overlay/overlay.js, app/overlay/preload.js, app/selftest.js, app/shared/tray.js, app/shared/ew.css, app/package.json, and the matching app/test/*.test.js (overlay_*, tray, selftest, shell).

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
3. Record every finding in `docs/audit/20261017-app-shell.md`: one row per
   finding with ID (APP-SHELL-NN), file:line, severity (H/M/L), what was
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

(none - every finding was fixed or ruled NOT-A-BUG; see
`docs/audit/20261017-app-shell.md`)

## As-built deviations

1. New module `app/shared/localhttp.js` (APP-SHELL-01). Decision: move
   main.js `getLocal` / `postLocal` into a pure Node module so the cut-off
   reply hang is tested against a real local socket. Alternatives: patch
   in place and pin with a source regex only (cannot show the hang is gone);
   load main.js under a fake `electron` (large rig for two functions). Why:
   smallest change that makes the defect testable; reply shapes, timeouts and
   the 64 KiB cap are unchanged. The test that failed first is the static
   "main.js reaches the server only through shared/localhttp"; the module's
   behaviour tests were written with it. Reverses if: main.js gains an
   Electron-free test harness, then the helpers may move back.
2. Progress file `ops/loop/control/progress/p148-build.json` was not written:
   the lane's permission mode refused writes outside the worktree. Decision:
   carry on inline (the run is short and foreground). Reverses if: the lane
   permission set allows the main-checkout progress path.
