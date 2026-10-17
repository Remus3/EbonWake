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

## Game ToS

Reads EW's own control files only; nothing reaches the game client.

Depends on: none.
