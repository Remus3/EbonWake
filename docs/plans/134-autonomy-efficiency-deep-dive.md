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

(filled by the lane)
