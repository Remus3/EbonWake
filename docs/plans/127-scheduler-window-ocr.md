# Plan 127 - Scheduler window OCR: one shot ticks every pinned daily / weekly

Status: open. Proposed by deep dive 0023 (section 1). Lane hint: `build`.

Goal: the Black Spirit's Scheduler (Menu F8, Family-wide, patch 2026-09-10)
shows every pinned daily / weekly recurring quest with its state and
remaining time. One operator screenshot of it becomes a bulk cue for the
Today rows, so plan 114's one-window-per-row cues are not the only route.

Not a mirror of the Scheduler (0020 ruled that a duplicate of Today); this
only READS a shot the operator already takes.

Inputs (Game ToS floor): operator-saved screenshots through the plan 063
pipeline, `AutoTick.on_doc` hook (plan 114). Nothing is clicked or sent to
the game.

## Slices

1. Cue data: `server/ew/data/today_cues.json` gains a `scheduler` entry
   {row_patterns: {row_id: [regex]}, done: [regex], source, verified: false}
   - quest-name wording is data, not code.
2. Parser `ocrinfer.scheduler_rows(doc)` -> [{row, state: done|open, remaining_s?}]:
   a row line is matched to a Today row by its patterns; "Completed" / a
   checked state word on the line sets done; a "Nd Nh" / "HH:MM" remaining
   time is parsed when present.
3. Apply: done rows tick (`by: auto`, inside the row's reset period, operator
   untick blocks to next reset, as 114); open rows are never unticked.
   Unmatched quest lines are listed once in the review queue as "unknown
   scheduler row" so the operator can map them (adds a seed row, 021 reset
   rule picked by daily / weekly).
4. Seed: weekly Lyngbakr Ecology Survey row (added 2026-09-10) in SEED when
   the Scheduler lists it.
5. Gate, review, undo and `auto_applied` as plan 111.

## Tests first

- `tests/test_scheduler_ocr.py`: fixture doc with 4 rows (2 done, 1 open, 1
  unknown) ticks only the 2; remaining-time parse; open never unticks; shot
  outside logged-in windows ticks nothing; unknown row queued once; operator
  untick blocks.

## Acceptance

A fixture Scheduler doc ticks the matched done rows with an Undo; gates
green; verifier PASS within 3 rounds; one push.

Retires: ticking each Scheduler-visible daily / weekly by hand.

Depends on: 114, 111, 021.
