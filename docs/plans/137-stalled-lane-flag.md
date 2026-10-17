# Plan 137 - Stalled-lane flag: a lane silent for twice its ETA shows stalled in the loop checklist

Status: open. Source: research 0029 findings A3 and A7 (plan 134). Lane hint:
`build`.

Problem: FLEET item 12 says a progress file that stops updating for 2x its
own ETA step is a failure to investigate. The tick's `reap_lost`
(`tools/ew_loop.py:518-531`) checks only that the lane pid is alive, so a
hung lane is noticed only at `LANE_TIMEOUT_S = 5400`. A lane may also be
unable to write its progress file in the main checkout (permission set) and
write the worktree copy instead.

## Slices

1. Tests first in `tests/test_ew_loop.py` (fake Deps, no git, no socket):
   - pure `stall_of(doc, now, floor_s=600) -> None | seconds_silent`:
     stalled when `now - updated > max(2 * eta_s, floor_s)` and status is
     `running`; `done` / `failed` / `blocked` never stall; missing,
     unparsable `updated` or missing file -> None (unknown is not stalled).
   - the tick reads `p<id>-build.json` from the lane worktree first, then
     the main checkout (same order as `blocked_marker`,
     `tools/ew_loop.py:717-720`), newest `updated` wins; a doc older than the
     item's `dispatched` is ignored (stale from a previous run).
2. New tick phase after `reap_lost`: for each `dispatched` item with a live
   pid, set `rec["stalled_s"]` (or clear it), log one step line
   `"<id>: stalled <n>m"`, and the checklist row shows
   `(stalled, <n>m silent)`. The lane is NEVER killed or re-dispatched for a
   stall (CLAUDE.md loop rule 1: never kill a running lane); the 5400 s
   timeout stays the only kill.
3. A stall lasting past 3x ETA records one `timings.jsonl` row kind
   `lane-stall` (seconds silent) so the ETA tooling sees it.
4. If plan 136 has landed, `loopstatus.summary` lists stalled items under
   `stuck` with state `stalled`; otherwise this slice is skipped and noted.

## Acceptance

- New tests green; `python tools/ew_tests.py fast` green; ruff green.
- A fake lane whose progress `updated` is 25 min old with `eta_s` 300 shows
  `stalled` in loop.json; one with no progress file shows nothing.
- No lane is killed by this plan.

## As-built deviations

- Slice 4 skipped: plan 136 (`loopstatus.summary`) has not landed in this
  tree. Alternatives: build a stub summary here. Why: 136 owns that module;
  a stub would collide with its lane. Reverses if: 136 lands - then its
  `stuck` list reads `rec["stalled_s"]` (state `dispatched` + `stalled_s`).
- The lane worktree is found from the RUNNING lane-lock row whose lane name
  matches the record (`lane_state` + `lane_worktree`): a `dispatched` record
  carries no `worktree` yet. Alternatives: store the worktree at dispatch.
  Why: the kit claims the index only when the worker runs. Reverses if:
  dispatch starts recording the claimed worktree.
- The stall phase re-reads the record just before writing and skips it unless
  still `dispatched`, so a lane worker finishing mid-tick is never clobbered.
  The one-time `lane-stall` row is keyed on the record's `dispatched` stamp
  (`stall_recorded`), so a re-dispatch can record again. Alternatives: a
  separate stall ledger file. Why: no new control file. Reverses if: records
  gain a compare-and-swap put.
- A stalled checklist row carries `eta_s` null so it renders exactly
  `(stalled, <n>m silent)`. Alternatives: keep the remaining-ETA suffix. Why:
  the plan's row text; a negative / zero ETA on a hung lane misleads.
- The new tests use fake Deps, but `tests/test_ew_loop.py` is module-marked
  `git` (plan 097: the tick probes hooksPath), so they run in the whole suite,
  not the fast tier. Reverses if: the module's tests are split by tier.
- `refute-rounds: 0/3` (no verifier round in this lane; the loop's review
  worker runs it).

## Game ToS

Loop tooling only; nothing reaches the game client.

Depends on: none.
