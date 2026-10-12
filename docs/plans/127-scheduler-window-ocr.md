# Plan 127 - Scheduler window OCR: one shot ticks every pinned daily / weekly

Status: done 2026-10-12 (loop merge 62753d9; refute 0/3 PASS). Proposed by deep dive 0023 (section 1). Lane hint: `build`.

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

## As-built deviations (build lane, 2026-10-12)

Each self-adjudicated (decision / alternatives / why / reverses if).

1. Hook path. Decision: the OCR worker calls `AutoTick.scheduler(doc,
   shot_at, AUTO_APPLY_MIN)` through a new `AutoOcr(today_auto=)`
   collaborator (wired in `app.py`), and `AutoTick.on_doc` skips a
   Scheduler doc. Alternatives: do it all inside `on_doc`. Why: the
   `auto_applied` log, the review queue and Undo live in `AutoOcr`; `on_doc`
   returns a bool and cannot hand back the ticked / unknown rows; skipping
   the doc in `on_doc` stops the plan 114 `bs_weekly` cue (black spirit +
   weekly + complete over the whole text) from ticking a row the Scheduler
   lists as open. Reverses if: a second per-line window reader appears and a
   doc-consumer list is wanted.
2. Cue data shape. Decision: the `scheduler` entry carries `window` (title
   regexes that mark a Scheduler shot) and `open` (in-progress state words)
   besides `row_patterns`, `done`, `source`, `verified: false`;
   `load_cues` skips the entry and `today.load_scheduler` validates it.
   Alternatives: hard-code the window title / open words. Why: wording is
   data, not code (slice 1). Reverses if: never.
3. Line model. Decision: one OCR line = one quest (name + state + time on the
   same line); a line is a quest line when it names a row or carries a state
   word / remaining time; done = a done word and no open word; unmatched
   names need 3+ letters. Alternatives: pair a name line with the state on
   the next line. Why: no operator Scheduler shot exists yet
   (`verified: false`); the simplest model the fixture pins. Reverses if: a
   real shot shows the state on its own line.
4. Row match. Decision: data `row_patterns` first, then any daily / weekly
   Today row title found in the folded line (so a mapped unknown row and an
   operator row tick without a data change). A matched row ticks only when it
   has a ticking auto rule (`TodayService.auto_tick`). Alternatives: tick
   rule-less rows too. Why: plan 068 auto ticks need a rule; an operator row
   without one stays manual. Reverses if: the operator asks for every row.
5. Mapping an unknown row. Decision: review kind `scheduler_row` (accept /
   discard, no fix); accept adds a Today row titled by the line, kind daily
   or weekly (weekly when the line says Weekly or more than a day is left),
   the kind's default reset (021), rule `shot:scheduler`, ticked at once when
   the line read done. Each unknown name is queued once ever (store domain
   `autotick_sched.unknown`, 200 slugs), so a discard is final.
   Alternatives: write the mapping into the tracked data file. Why: a tracked
   file is never written at runtime. Reverses if: the operator wants a
   discarded line to come back.
6. Seed (slice 4). Decision: `today.SCHED_SEED` adds the weekly "Lyngbakr
   Ecology Survey" row (rule `shot:scheduler`) to the store the first time a
   Scheduler shot lists it, once ever (`autotick_sched.seeded`): a removed
   row is not re-added. Not in the fresh-store `SEED`. Alternatives: add it
   to `SEED` for every new store. Why: "when the Scheduler lists it";
   operators who never pin it see no new row. Reverses if: the row should
   show before the first Scheduler shot.
7. Gate. Decision: every done line carries `CONF_SCHED` 0.96 (row match +
   state on one line), so it clears `AUTO_APPLY_MIN`; there is no
   below-gate Scheduler suggestion. Alternatives: a fuzzy name score. Why:
   matching is regex / exact title, not fuzzy. Reverses if: fuzzy matching
   is added.
8. Undo. Decision: `auto_applied` kind `today` {row, title}; Undo is the
   Today untick (blocks the row until its next reset, plan 068). App: label
   "<title> ticked (Scheduler)" and review label "unknown scheduler row ...
   - accept adds it to Today" (`app/test/scheduler_ocr.test.js`).
9. Remaining time is parsed and listed on unknown rows; it does not gate a
   tick (the tick uses the period in force at the shot, as 114).
10. Progress file. The lane run's permissions denied the kit
    `write_progress` call outside the worktree (as plans 111 / 114), so
    `progress/p127-build.json` was not written; gates were run inline.
    Reverses if: the lane grants the kit `write_progress` path.
