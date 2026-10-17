# Plan 136 - Loop status card: last tick age, lanes, stuck items, halt and backoff on the dashboard

Status: open. Source: research 0029 finding A2 (plan 134). Lane hint:
`build`.

Problem: the operator is mostly away and QAs at a glance, but the loop's
state lives only in `ops/loop/control/progress/loop.json` and the item
records. HALT, a usage backoff, items parked in `adjudicate` / `gave-up` /
`merge-conflict`, and a tick that stopped firing (scheduled task broken) never
show in the app.

## Slices

0. Measure (main checkout, read-only): record in this doc the current
   `loop.json` keys, the item states present in `loop_items/*.json` and the
   last 20 `loop-tick` durations from `timings.jsonl`, so the card's fields
   are grounded in real files.
1. Tests first: `tests/test_loopstatus.py` for pure
   `server/ew/loopstatus.py`: `summary(root, now) -> {state, fire,
   last_tick_utc, tick_age_s, tick_s, stale, halted, backoff_until,
   in_flight: [...], stuck: [{id, state, since}], counts: {state: n}}`.
   - `stale` when `tick_age_s > 2 * eta_s` of loop.json (tick period
     15 min, so about 30 min).
   - `stuck` = items in `adjudicate`, `gave-up`, `merge-conflict`,
     `blocked` (with `needs`).
   - Missing / torn files -> `{state: "unknown"}`, never a 500.
   - Fixture trees under tmp_path only (fleet_test_guard).
2. `GET /api/loop` (read-only, `server/ew/app.py`), cached 10 s. No POST:
   HALT stays a file the operator or a session places.
3. Dashboard: a "Loop" card on the System tab under Signal health: state pill
   (kit tokens.json state vocabulary), tick age, in-flight lanes with their
   checklist line, stuck items, halt / backoff line. Home gets one quiet line
   only when `stale`, `halted` or `stuck` is non-empty.
   `app/test/loopstatus.test.js` for the pure render helpers.
4. Endpoint consumer test (`app/test/endpoint_consumers.test.js`) lists
   `/api/loop`.

## Acceptance

- `tests/test_loopstatus.py` and the app tests green; ruff green.
- With HALT present the card shows "halted"; with a loop.json older than
  2x eta it shows "stale"; an `adjudicate` item is listed by id.
- Read-only: the route never writes under `ops/loop/control/`.

## Measured (slice 0)

Grounded in the writers (`tools/ew_loop.py` `Tick.write` / `tick`,
`backoff_hit`, `tools/loop_base.py` `Items`), not the live files (see
deviation 1):
- `progress/loop.json`: `task` ("loop"), `pct`, `step`, `eta_s` (the tick
  period, config `tick_s`, default 900), `status` ("done"), `updated` (ISO
  UTC), `state` (idle | running | halted | backoff | limit | refused), `fire`
  (run count), `tick_s` (this tick's own duration, target under 60 s), `log`
  (last 40 steps), `checklist` (kit rows `{id, task, state, eta_s}`, at most
  20). A HALT tick still writes it (state halted, empty checklist).
- `backoff.json`: `{delay_s, until (epoch s), reason, since}`; cleared to
  `{delay_s: 0, until: 0}`.
- `loop_items/<id>.json` states: open, dispatched, ran, committed, merged,
  no-change, failed, lost, refused, paused, blocked (`needs`), adjudicate,
  merge-conflict, merge-refused, failed-dirty, lane-dirty, gave-up; each
  carries `updated` (ISO UTC, set on every put), most `title`, in-flight ones
  `lane` and `dispatched`.
- `loop-tick` durations: not read (deviation 1); the card shows the last
  tick's own `tick_s` instead of a history.

## As-built deviations

1. Slice 0 measured from code, not from the main checkout's files.
   Decision: the lane's sandbox denies reads (and the progress-file write)
   outside its worktree, so the keys / states above come from the code that
   writes them. Alternatives: block on the operator (forbidden by standing
   order 6); guess. Why: the writer code is the contract the files follow.
   Reverses if: a session reading the live files finds a key or state the
   card does not handle.
2. Render helpers live in `app/dashboard/loopstatus.js` (window.EWLoop,
   `require()`-able), not in an EWCore part. Decision: a standalone module.
   Alternatives: a new `core/loop.part.js` (touches PARTS, both pages, the
   pinned `ewcore_exports.json` surface and the overlay, which never shows
   the card). Why: smallest change, dashboard-only consumer. Reverses if: the
   overlay needs the loop state.
3. Extra summary fields beyond the plan: `eta_s`, `backoff_reason`, and per
   row `title` (stuck, in-flight), `error` (stuck), `needs` (blocked),
   `lane` + `line` (in-flight). A loop.json with an unparsable `updated` is
   `stale` (age unknown). State precedence: halted > stale > backoff >
   loop.json `state`; missing / torn loop.json -> `unknown` but HALT, backoff
   and items still read. Why: the card needs them; no extra file is read.
   Reverses if: never (additive).
4. The server reads the MAIN checkout's control files (`main_root`, from a
   linked worktree's `.git` file); a test server (a `store_root`) reads that
   root's parent, and `loop_root=` overrides. Why: a server started from a
   worktree must still show the real loop; tests stay under tmp_path.
   Reverses if: never.

## Game ToS

Reads EW's own control files only; nothing reaches the game client.

Depends on: none.
