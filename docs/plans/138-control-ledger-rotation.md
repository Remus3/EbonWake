# Plan 138 - Control ledger rotation: cap timings, usage, claims and finished lane status files

Status: open. Source: research 0029 finding B1 (plan 134). Lane hint:
`build`.

Problem: every tick parses all of `headless_usage.jsonl`
(`usage_ledger.backfill_kind`, `tools/ew_loop.py:1256`), every ETA estimate
parses all of `timings.jsonl` (`tools/eta.py:68`), and `claims.jsonl` plus
finished `progress/*.json` only grow (plan 102 hand-moved 33 stale progress
files). Nothing in `tools/` or `server/` rotates or caps a file.

## Slices

0. Measure (main checkout, read-only): sizes and row counts of the four
   ledgers and the count of `progress/*.json` by status and age; record them
   in this doc as the before numbers.
1. Tests first: `tests/test_ledger_rotate.py` for `tools/ledger_rotate.py`
   (stdlib, fixtures under tmp_path):
   - `headless_usage.jsonl`: rows older than 35 days move to
     `ops/loop/control/archive/headless_usage-YYYYMM.jsonl` (append). The
     live file keeps at least 8 days so the 24 h governor window
     (`usage_ledger.run_starts`) and MAIN's weekly build-vs-inbox split are
     unchanged; a test asserts `run_starts` counts the same before and after.
   - `timings.jsonl`: keep the newest 200 ok rows per kind (eta.py uses the
     last 5) plus all rows younger than 30 days; older rows to the archive.
   - `claims.jsonl`, `gitlock.jsonl`, `identity.jsonl`: keep 30 days.
   - `progress/*.json` with status `done` / `failed` and `updated` older than
     7 days move to `progress/archive/` (never `loop.json`, never a running
     or blocked file).
   - Concurrency: the same guard as `backfill_kind` - re-stat before the
     atomic replace and skip (retry next tick) when the size changed, so a
     kit append is never lost. Torn lines are kept, never dropped.
   - Idempotent: a second run moves nothing.
2. Wiring: the tick calls `ledger_rotate.rotate(root)` at most once per local
   day (marker file), after `reap_lost`; one step line with rows moved.
   `python tools/ledger_rotate.py --dry-run` prints the plan.
3. Moves only, never deletes (FLEET item 9); the archive dir is under the
   already gitignored `ops/loop/control/`.

## Acceptance

- `tests/test_ledger_rotate.py` green; fast tier green; ruff green.
- After one rotate on a copy of the measured ledgers the live usage file is
  at most 8-35 days of rows and `run_starts` / `eta.estimate` give the same
  answers as before.

## Game ToS

EW control files only; nothing reaches the game client.

Depends on: none.
