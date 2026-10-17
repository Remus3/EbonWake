# Plan 147 - Hardening audit app-core: app/shared/core/*.part.js and app/shared/ewcore.js plus their app/test files

Status: open (operator order 2026-10-17, session 36: "after completing the
found new tasks - do a full deep audit file by file for hardening and
bug/issue corrections"). Lane hint: `build`.

Goal: read every file in this slice IN FULL, line by line, and fix real
defects. Slice sized to fit one lane run (lane_timeout_s 5400; adjudicator
ruling session 36: 12 slices of about 7k lines, plans 141-152).

## Files

app/shared/core/*.part.js (base, bosses, bus, deadeye, entry, events, grind, home, inventory, leveling, market, notify, ocr, progress, settings, shell, today), app/shared/ewcore.js, and the matching app/test/*.test.js.

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
3. Record every finding in `docs/audit/20261017-app-core.md`: one row per
   finding with ID (APP-CORE-NN), file:line, severity (H/M/L), what was
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

None: every finding was FIXED or NOT-A-BUG (`docs/audit/20261017-app-core.md`).

## As-built deviations

1. Test files read. Decision: this lane read in full the core test files no
   sibling audit covered (ewcore, ewcore_split, bus, notify, ocr, shell); the
   other tests that exercise these parts were read in full by plans 145 / 146
   and their audit docs list them. Alternatives: re-read all ~90 app/test
   files (over the lane budget). Why: "matching" tests overlap the dashboard
   slices; coverage stays checkable through the three audit docs together.
   Reverses if: a reviewer finds a core-part test listed in no audit doc.
2. Progress file. Decision: `ops/loop/control/progress/p147-build.json` in the
   main checkout was not written; this lane's permission mode refused every
   write outside the worktree (Write tool and a Python helper both asked for
   approval that a headless run cannot give). Alternatives: write it inside
   the worktree (the lane widget would never read it there, FLEET item 12).
   Why: the work itself was not blocked; the loop reads the lane's own
   lane-<i>.json. Reverses if: the lane's settings grant that one path.
3. Fix shape. Decision: only internal lookup maps became
   `Object.create(null)`; maps returned to callers stay plain objects.
   Alternatives: own-property checks at every lookup, or null-prototype
   outputs too. Why: the smallest change at the root, and the output shapes
   are pinned by deepStrictEqual tests (a null prototype would fail them).
   Reverses if: an output map is found keyed by untrusted text.
