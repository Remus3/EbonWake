# Plan 158 - Store last-good snapshots: a corrupt operator doc restores, not empties

Status: open (deep dive 2026-10-18, research 0030). Lane hint: `build`.

## Problem

`server/ew/store.py` `Store.get` renames an unreadable domain doc to
`<domain>.json.corrupt-<ts>` and returns the empty default. For operator-typed
domains (checklists, grind and sales ledgers, notes, overrides, pet / mount
rosters, settings) that silently drops weeks of data: the next `put` writes
a fresh doc and the quarantined bytes are never looked at again. A crash or
power cut mid-write is guarded by the atomic replace, but a disk fault, an
antivirus truncation or an editor save by hand is not. Nothing in the
repo keeps a previous good copy (grep of plans: no backup / last-good plan).

## Slices

1. Failing test: put twice, truncate the file, `get` returns the FIRST
   put's data (not `{}`), the bad bytes are still kept as `.corrupt-<ts>`.
2. `Store.put` keeps one last-good copy per domain
   (`<domain>.json.good`, atomic write of the previous valid bytes, written only
   when the domain content actually changes, so a hot domain does not double its
   IO). `get` on a corrupt doc restores from `.good` when it parses, else falls
   back to the empty default as today.
3. Daily rotation: the first `put` of a local day also copies the doc to
   `backups/<domain>.<yyyymmdd>.json`, 7 days kept (same prune pass as plan 138
   ledger rotation; no new scheduler).
4. A restore is a signal: `signals` gets a one-line "restored <domain> from
   last-good" item (kit state vocabulary) so the operator sees it on the
   Home quiet line (plan 076) and the digest (plan 073); no toast.
5. Tests: restore, no-good fallback, unchanged-put writes no `.good`, prune
   keeps 7, a `.good` that is itself corrupt falls back to empty. tmp_path
   roots only (plan 157 guard).

## Acceptance

Each slice's test failed before the fix and passes after; ruff, touched tests
and (if app/ changed) npm test green; ASCII / LF; no machine path in any
tracked file; atomic writes only (CLAUDE.md Paths and runtime).

Depends on: 138.

## Alternatives rejected

- Zip export / import button: needs operator action; the failure is silent.
- Git-tracking `ops/runtime`: public repo, would leak operator data.
- SQLite store: stdlib allows it, but it is a rewrite of every domain reader.

## As-built deviations

1. Restore order is `.good`, then the newest VALID daily backup, then empty.
   Alternatives: `.good` only (slice 2 text). Why: the title promises restore
   from `.good` / 7 daily backups, and a corrupt `.good` with a good backup
   beside it would otherwise still empty the doc. Reverses if: a backup restore
   is shown to resurrect data the operator deleted on purpose.
2. Backup prune runs in `Store.put` on the first put of a local day (per
   domain, newest 7 kept), not in plan 138's `tools/ledger_rotate.py` pass.
   Alternatives: hook the tick's rotate_daily. Why: ledger_rotate rotates the
   loop's control ledgers in the MAIN checkout; the store lives under the
   server's runtime root (any host, any test root), and the day's first put is
   already the rotation moment - still no new scheduler. Pruned copies are
   unlinked: each is a redundant copy of a live doc, not irreplaceable (FLEET
   item 9). Reverses if: backups move under the control ledger tree.
3. The signal is a `restores: {count, items}` section on the /api/signals
   digest (beside plan 079 `overrides`; each item `level: warn`, `text:
   restored <domain> from last-good`) plus a Home warn pill
   (`C.restorePill`, opens System), not a new liveness row. Alternatives: a
   `store` row in REASONS. Why: rows are per-signal liveness with hint-file
   coverage; a restore is an event. Restores are held in memory for 24 h
   (`Store.restores()`). Reverses if: restores must survive a server restart.
4. A restore writes the recovered bytes back to `<domain>.json` (atomic), so
   the next read is plain and the next put rotates `.good` normally.
5. Progress file `progress/p158-build.json` was not written: the lane's
   permission mode denied writes outside the worktree and helper-script runs.
   Reverses if: the lane grants that write.
