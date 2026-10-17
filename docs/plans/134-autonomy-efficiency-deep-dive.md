# Plan 134 - Targeted deep-dive: autonomous operation, efficiency, player features

Status: open (operator order 2026-10-17, session 36). Lane hint: `build`.

Goal: research how EW can run more autonomously and more cheaply, plus
helpful player features inside the Game ToS floor, and turn the findings into
deduped, buildable plans + proposed ROADMAP rows. Write no product code in
this plan (the guard test below is the only code).

Operator order (verbatim): "do a deep-dive research and expansion for
implementing and improving the autonomous usage of ebonwake and other
features that would be helpful + efficiency related."

Inputs (Game ToS floor, CLAUDE.md): the EW tree itself (tools/ew_loop.py and
its loop_*.py split, tools/ew_lane.py, tools/launch.py, server/ew/*,
app/*, tests/*, ops/loop/control/timings.jsonl, headless_usage.jsonl,
loop_items/*.json, progress/*.json) plus read-only, unauthenticated public web
sources with robots.txt respected. Nothing reaches the game client.

## Scope

A. Autonomy: loop self-healing and unattended recovery (stale progress
   detection, lost lanes, stuck states, index.lock, dead claims), server /
   overlay / dashboard supervision and auto-restart, retry + backoff
   policy, failure alerting surfaced on the dashboard, scheduling efficiency
   (tick cost, idle ticks, lane fill), health self-tests.
B. Efficiency: headless spend reduction (usage per kind from
   headless_usage.jsonl, prompt size, verifier passes, no-change runs),
   arsha.io / BDO-REST-API cache and rate-limit efficiency (TTL, conditional
   requests, batching, backoff), server and Electron startup cost, test-suite
   wall time (slowest tests, xdist, fixtures), disk / log growth.
C. Player features within the ToS floor that would help a single-character
   Deadeye player (zero-touch per research 0010 and plan 079): only ideas not
   already covered by plans 001-133.

## Slices

1. Research doc `docs/research/0029-deep-dive-autonomy-efficiency.md`: one
   section per scope area, each finding with evidence (file:line, measured
   number or dated source), severity H/M/L and a verdict (PLAN, NOTE, NO).
2. Plans: one doc per PLAN finding, numbered from 135, AT MOST 6, each sized to fit one lane run (lane_timeout_s 5400), each with
   first line `# Plan NNN - Title`, slices, tests first, acceptance and a
   `Depends on:` line. Rank them in the research doc (value / cost).
3. Proposed rows: list each new plan below under "Proposed ROADMAP rows"
   as `| NNN | title (plan doc docs/plans/NNN-<slug>.md) | [ ] open (priority) |`.
   Do NOT edit docs/plans/ROADMAP.md (the session copies the rows after merge).
4. Guard: `tests/test_plan134_deep_dive.py` - every proposed row has its plan
   doc with a `Depends on:` line, at most 6 proposed, and no proposed title
   duplicates an earlier plan or another proposed one under
   `loop_roadmap.is_duplicate`.

## Acceptance

Research doc exists with evidence per finding; plans 135.. exist, well
formed, deduped, at most 6; guard test, ruff and ASCII / LF tests green.

Ruling (adjudicator, session 36): targeted deep-dive = ordinary priority row
134 (<= 6 plans + priority rows); alternatives: raise max_new_plans_per_day /
reset today's deep-dive marker, hand-run session sub-agent; why: the
kind=deep-dive cap and once-a-day gate do not bind ordinary rows
(tools/ew_loop.py extra_checks, deep_dive_item), row 120 precedent,
headless-first; reverses if: the lane times out or more than 6 viable
non-duplicate plans turn up.

Depends on: none.

## Proposed ROADMAP rows

Ranked in research 0029 "Ranking" (135, 136, 137, 138, 140, 139).

| 135 | Server watchdog: the app health-polls and auto-restarts a dead EW server (plan doc docs/plans/135-server-watchdog.md) | [ ] open (priority) |
| 136 | Loop status card: last tick age, lanes, stuck items, halt and backoff on the dashboard (plan doc docs/plans/136-loop-status-card.md) | [ ] open (priority) |
| 137 | Stalled-lane flag: a lane silent for twice its ETA shows stalled in the loop checklist (plan doc docs/plans/137-stalled-lane-flag.md) | [ ] open (priority) |
| 138 | Control ledger rotation: cap timings, usage, claims and finished lane status files (plan doc docs/plans/138-control-ledger-rotation.md) | [ ] open (priority) |
| 139 | Upstream fetch politeness: conditional GET (ETag / Last-Modified) and Retry-After backoff (plan doc docs/plans/139-upstream-fetch-politeness.md) | [ ] open (priority) |
| 140 | Weekly silver goal: target, pace and projection from session and sales ledgers (plan doc docs/plans/140-weekly-silver-goal.md) | [ ] open (priority) |

## As-built

`docs/research/0029-deep-dive-autonomy-efficiency.md` (findings A1-A7,
B1-B8, C1-C3 with evidence, severity, verdict and ranking), plans 135-140,
guard `tests/test_plan134_deep_dive.py`.

## As-built deviations

1. Evidence is code-cited, not measured from the runtime ledgers. Decision:
   cite file:line and constants; plans 136 and 138 open with a read-only
   "measure" slice on the main checkout. Alternatives: block the row until a
   session reads `headless_usage.jsonl` / `timings.jsonl`; guess numbers.
   Why: the lane's linked worktree permission set denied every read and
   write under the main checkout's `ops/loop/control/`, and the plan forbids
   waiting. Reverses if: a lane run can read the main checkout's control
   files (then the measured numbers replace the citations).
2. Progress file written in the lane worktree
   (`ops/loop/control/progress/p134-build.json`, gitignored), not the main
   checkout. Alternatives: no progress file. Why: the main-checkout write was
   denied; the loop's `blocked_marker` already reads the worktree copy first,
   and plan 137 makes the stall check read both. Reverses if: the lane
   permission set allows the main-checkout progress path.
3. No public web source was read (scope A / B are tree-internal; scope C was
   answered from the tree's own plan coverage). Alternatives: re-run the
   daily patch-note sweep. Why: research 0028 did that sweep the same day;
   repeating it would only duplicate. Reverses if: a scope C idea needs an
   external fact (plan 139 slice 0 does its own dated GET).
