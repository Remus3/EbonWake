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

## Game ToS

Loop tooling only; nothing reaches the game client.

Depends on: none.
