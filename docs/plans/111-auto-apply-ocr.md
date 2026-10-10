# Plan 111 - Auto-apply high-confidence OCR suggestions (book use, zone reads, world boss loot ticks) with undo and an audit log

Status: open (priority). Operator order session 28 (zero-touch wave). Lane
hint: `build`.

Goal: a suggestion EW is confident about is applied, not parked. The
review queue keeps only low-confidence items; every auto-apply is
undoable and listed.

State today (read 2026-10-10):
- Book use: `server/ew/ocrauto.py:497` `_suggest_book` queues an
  `ocrinfer.book_suggestion` for every XP jump - "always reviewed", and
  `FIX_KINDS` excludes it (accept / discard only).
- Zone reads: plan 088 `zoneinfo.parse` fields go through the commit gate
  (`ocr.auto_commit_min`, 0.9) but a read below it is queued; a zone read
  is accept / discard only.
- World boss: `server/ew/autotick.py` `boss_suggestions` marks a boss
  "probably done" when a screenshot falls within BOSS_WINDOW_MIN (20) of a
  plan 031 spawn - a suggestion only, never a loot tick
  (`bosses.py` store domain `bosses.looted`).

Inputs (ToS floor): screenshot files + their OCR text (plan 063), the
plan 031 spawn table, the clock. Nothing reaches the game.

## Slices

1. Auto-apply gate: module constant `AUTO_APPLY_MIN = 0.95` in
   `server/ew/ocrauto.py` (no new setting - plan 080 purged tunables);
   a suggestion at or above it is applied through the same path its
   "accept" uses, with `via: "auto"` and an undo id; below it queues as
   today.
2. Book use confidence: `book_suggestion` gains a `conf` from how exactly
   the XP jump matches one book size (`xpbooks.SIZES`) within the
   tolerance, times the level read confidence, and 0 when two sizes fit or
   the jump spans a level-up with an unknown rate.
3. Boss loot tick: a shot inside the window whose OCR text fuzzy-matches the
   boss name (plan 031 table names, `ocr` fold) or its loot box name, while
   logged in, ticks `bosses.looted` with `by: auto` (conf = name match x
   window proximity); a time-only match stays a suggestion. Garmoth weekly
   cap respected.
4. Audit log: store domain `auto_applied` {items: [{id, at, kind, value,
   conf, file, undo_id, undone}]}, MAX 200, newest first; GET in the
   `/api/ocr/auto` body as `applied`. Undo reuses `OcrAuto.undo` (book,
   zone) and a new `bosses.untick(day, boss, by="undo")`.
5. Surface: the OCR card shows "Applied automatically" (last 10, Undo
   button each) above the review queue; a toast per auto-apply (plan 070
   policy, quiet while the game is closed).

## Tests first

- `tests/test_auto_apply.py`: a 0.96 book suggestion applies and logs; a
  0.94 one queues; two-sizes-fit -> conf 0 queues; undo reverts the book
  count and marks the log row undone; a zone read at 0.96 commits, 0.8
  queues; boss shot inside the window with the boss name in OCR text ticks
  `by: auto`, time-only stays a suggestion, Garmoth cap blocks a second
  weekly tick; log bounded at 200.
- `app/test/ocr_auto.test.js`: the applied-list formatter and Undo body.

Acceptance: fixture shots for one book jump, one zone panel and one boss
loot screen auto-apply with log rows; Undo on each restores the prior state;
the review queue holds only the low-confidence fixtures; gates green;
verifier PASS within 3 rounds; one push.

Retires: the accept click on confident book-use, zone and boss suggestions.

Depends on: 088.

## As-built deviations (build lane, 2026-10-10)

Each self-adjudicated (decision / alternatives / why / reverses if).

1. Zone gate. Decision: a zone read still commits at the plan 088 gate
   (`AUTO_COMMIT_MIN`, 0.9) and every committed zone read gets an
   `auto_applied` row with Undo. Alternatives: raise zone reads to 0.95.
   Why: "below it queues as today" - a 0.90-0.95 read commits today; raising
   it would park reads 088 already applies (the opposite of zero-touch).
   Reverses if: a 0.90-0.95 zone read is found wrong in use.
2. Boss untick. Decision: no new `untick(day, boss, by=)` signature; the
   existing `BossService.untick({boss, day})` serves Undo, and every untick
   (operator or Undo) lists the key in store `bosses.no_auto` so a later shot
   never re-ticks it; the auto tick is `BossService.auto_tick(day, boss)` with
   `by: {key: "auto"}`. Alternatives: a `by` kwarg that only Undo blocks.
   Why: an operator untick means "not looted" just as much as Undo does;
   one call shape keeps the POST API unchanged. Reverses if: the operator
   wants an untick that a later loot screen may re-tick.
3. Loot box names. Decision: matched by the boss name only (plan 040 fold /
   edit distance); the loot window reads "<boss>'s ...". Alternatives: a
   loot-box name table. Why: the plan 031 table carries no loot-box names and
   none is sourced. Reverses if: a sourced loot-box table lands.
4. Window proximity. Decision: 1.0 at or after the spawn (within
   BOSS_WINDOW_MIN), 0.5 before it (the boss was not up). Alternatives: a
   linear fall-off. Why: loot exists only after the spawn; any shot after it
   inside the window is equally plausible. Reverses if: false ticks appear
   late in the window.
5. Level-up span. Decision: a jump across a level-up yields no book
   suggestion at all (book_suggestion is same-level only, as before) rather
   than conf 0. Why: nothing to queue either way.
6. Undo route. Decision: POST `/api/ocr` `{"undo": "a<n>"}` (the existing
   undo body, routed by id prefix to `AutoOcr.undo_applied`). Why: no new
   route; the bridge validator already gates `/api/ocr`.
7. Toast. Decision: new notify rule `ocrApplied` (one toast per new live
   row, never on the baseline look); toast.js polls `/api/ocr/auto`; plan
   070 `promptGate` holds it while the game is closed.
8. Tests. JS tests live in `app/test/ocr_auto_applied.test.js` (not appended
   to ocr_auto.test.js); the Garmoth test fills the real weekly cap (3)
   rather than a "second" tick. `test_ocr_infer` book-review test moved to a
   below-gate jump (a 7.6 % jump now auto-applies).
9. Progress file. The lane run's permissions denied writes outside the
   worktree (Write tool and helper scripts), so
   `progress/p111-build.json` was not written. Reverses if: the lane grants
   the kit `write_progress` call.
