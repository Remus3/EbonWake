# Plan 163 - Lane allow-list gap + false PASS on FIX orders

ROADMAP row 163.

## Problem

1. Headless code lanes (`tools/ew_lane.py` `CODE_EXTRA`) allow only the gate
   commands. A dependency-bump or alert-closing order needs `npm install` /
   `npm ci` in `app/`, the Dependabot alert reads via `gh api` and `git add`
   of a regenerated lockfile; all were denied, so order N82830d failed 3/3
   refute rounds without ever being able to do the work.
2. The keep-ref commit 9e52b0e carried `verifier: PASS` while the `app/`
   files the FIX note ordered changed had an empty diff. The verifier prompt
   never told it to compare the ordered files with the diff, and nothing in
   the loop checked it mechanically.

## Acceptance

- A dependency-bump item can run `npm install` / `npm ci` / `npm test
  --prefix app` and read the Dependabot alerts (`gh api
  repos/{owner}/{repo}/dependabot/alerts...`) in its lane.
- The loop fails (an `extra_checks` finding, before any verifier spawn) any
  FIX order whose ordered files are missing from the lane diff; the
  verifier prompt also requires it for every order.

## Design

- `ew_lane.GATE_TOOLS` (the old allow list) + `ew_lane.DEP_TOOLS`
  (`npm install`, `npm ci`, `npm ls`, `npm view`, `npm outdated`, `npm audit`,
  `git add`, `git status`, `git diff`, and read-only `gh api` on the repo's
  Dependabot alerts plus `gh pr view` / `gh pr list`). `CODE_EXTRA` =
  both. The deep-dive lane keeps `GATE_TOOLS` + web only (it writes no code).
  `gh api` uses the `{owner}/{repo}` placeholders, so no account id is
  tracked.
- `loop_inbox.ordered_files(text)`: repo-relative paths a note names (a
  slash, a file extension, not a URL, not `ops/fleet_kit/`, `.claude/`,
  `CLAUDE.md` - those route to the session, plan 091).
- `loop_inbox.missing_ordered(text, changed, roadmap, oid, exists)`: the
  ordered paths that exist in the worktree (or whose parent directory does)
  and are neither in the diff nor named in a BLOCKED / NOT-APPLICABLE bullet
  of the order's `## Order <oid> - blocked items` section. A file the lane
  could not touch is therefore reported as blocked (and plan 161 routes an
  all-BLOCKED order to the session) instead of passing silently.
- `Tick.order_checks(rec, wt)` (from `extra_checks` for `kind == "order"`):
  applies `missing_ordered` when the note's kit class
  (`fleet_inbox.note_class`) is FIX. Changed = `git diff HEAD --name-only`
  plus untracked files.
- `order_prompt` names the dependency tools as allowed (a bump's
  `npm install` is not an excluded "download") and says GETs only on
  `gh api`; `verify_prompt` for an order requires every ordered file to
  appear in the diff or in a BLOCKED / NOT-APPLICABLE bullet.

## Tests

`tests/test_p163_lane_tools.py` (pure, no git, no socket).

## As-built deviations

1. Mechanical check is FIX-only; ORDER / RULING rely on the verifier prompt.
   Alternatives: check every order class. Why: ORDER notes often cite files
   for reference only, so a path-in-text check would cost refute rounds on
   false findings; the row's acceptance names FIX. Reverses if: an ORDER
   false PASS with a missing ordered file recurs.
2. `gh api` is granted by command prefix
   (`gh api repos/{owner}/{repo}/dependabot/alerts:*`), which a permission
   prefix cannot restrict to GET; the "GET only" rule lives in the order
   prompt. Alternatives: no gh at all (N82830d keeps failing), a wrapper
   script (new tool surface for one call). Why: smallest grant meeting the
   acceptance, scoped to one endpoint. Reverses if: a lane is seen issuing a
   write through it.
3. `tests/test_ew_lane.py::test_code_lane_runs_accept_edits_read_lane_does_not`
   asserted no `git` at all in the code-lane allow list; it now pins the git
   grants to exactly add / diff / status (commit, merge, push stay the
   loop's). Why: plan 163 adds `git add` on purpose. Reverses if: lanes stop
   needing to stage a regenerated lockfile.
4. The progress file was written in the lane worktree
   (`ops/loop/control/progress/p163-build.json`, gitignored): the write to
   the main checkout was denied in this run. Reverses if: the lane gets that
   one write grant.
