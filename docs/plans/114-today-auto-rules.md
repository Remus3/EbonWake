# Plan 114 - More Today auto rules: bind the remaining dailies / weeklies to session-log and screenshot cues

Status: open. Operator order session 28 (zero-touch wave). Lane hint:
`build`.

Goal: every seeded Today row that has an observable cue ticks itself; rows
with no ToS-allowed cue are listed honestly as manual.

State today (read 2026-10-10): `server/ew/today.py:25` SEED has 8 rows;
`SEED_AUTO` (line 59) binds only `attendance-reward: login` and
`black-spirits-adventure-dice: ready_minutes:60`. `AUTO_RE` allows
`login | logged_minutes:N | ready_minutes:N`; `server/ew/autotick.py`
evaluates them.

## Row -> cue

| Row | Cue (ToS-allowed) | Rule |
|---|---|---|
| Attendance reward | first logged_in after reset (session log) | `login` (exists) |
| Black Spirit's Adventure dice | 60 logged-in minutes (session log) | `ready_minutes:60` (exists; the roll stays a tick) |
| Daily Challenges (Y) | screenshot OCR of the Challenges window daily tab showing all rewards claimed / "Completed" | `shot:challenges_daily` |
| Barter run | screenshot OCR of the barter window "exchange" / barter completion text | `shot:barter` |
| Guild mission | screenshot OCR of the guild mission "Complete" / reward text | `shot:guild_mission` |
| Black Spirit weekly quests | screenshot OCR of the quest window weekly quest "Complete" | `shot:bs_weekly` |
| Weekly boss rewards | plan 031 boss loot ticks this week (incl. plan 111 auto ticks) >= 1 | `bosses:1` |
| Pearl Shop weekly free item | screenshot OCR of the Pearl Shop free item "purchase limit 0/1" or "Purchased" | `shot:pearl_free` |
| Event rows (plan 095 weekly games) | none observable without input | manual (listed) |

## Slices

1. Rule grammar: `AUTO_RE` adds `shot:<cue_id>` and `bosses:N`;
   `today.parse_auto` returns them; tracked `server/ew/data/today_cues.json`
   {cue_id: {patterns: [regex], all?: [regex], source, verified: false}} -
   data, not code, so a pattern fix is a data change.
2. Shot cue matcher: `autotick` gets the OCR text of each new logged-in
   shot from plan 063's read (no second OCR: ocr_auto calls an
   `on_doc(file, doc, shot_at)` hook) and ticks rows whose cue matches,
   `by: auto`, inside the row's own reset period; operator untick blocks
   until the next reset (existing rule).
3. Boss rule: `bosses:N` ticks when the week's `bosses.looted` count
   reaches N (weekly reset rule of the row).
4. Seed: SEED_AUTO gains the five new bindings; existing stores get the rule
   on rows that have none (same migration as plan 068).
5. Surface: Today row shows "auto: screenshot" / "auto: boss loot" chips;
   the manual rows show nothing new.

## Tests first

- `tests/test_today_auto_rules.py`: grammar accept / reject; each cue
  fixture OCR doc ticks only its row; a shot outside logged-in windows
  ticks nothing; untick blocks until reset; bosses:1 ticks on the first
  weekly loot and resets Thursday 00:00 UTC; seed migration adds rules
  only where missing; cue data file schema.
- `app/test/today.test.js`: the auto chip text per rule kind.

Acceptance: fixture shots for the five cue rows tick them with by auto;
event rows stay manual; gates green; verifier PASS within 3 rounds; one
push.

Retires: manual ticks for Daily Challenges, Barter run, Guild mission,
Black Spirit weekly quests, Weekly boss rewards and Pearl Shop free item
whenever the operator took the screenshot (they already do).

ToS check: screenshot files the operator saved + OCR of them, the session
log state, EW's own boss ticks. No screen capture by EW, no input to the
game window.

Depends on: 111.

## As-built deviations

1. Chip scope. Decision: `todayAutoChip` returns "auto: screenshot" /
   "auto: boss loot" for `shot:` / `bosses:` rows only, and the chip is
   hidden once the row is auto-ticked (the plan 068 "auto" pill + undo shows
   instead). Alternatives: a chip for every rule kind (login, minutes).
   Why: the plan says the manual rows show nothing new, and login / dice rows
   already have their own pills. Reverses if: the operator asks to see the
   rule on every row.
2. Logged-in test for shots. Decision: `AutoTick.on_doc` checks its own
   logged_in spans (strict), not the OCR worker's 60 s post-logout grace.
   Alternatives: reuse the worker's eligibility. Why: the plan requires that
   a shot outside logged-in windows ticks nothing. Reverses if: real shots
   taken in the logout fade are missed.
3. `bosses:N` counts loot ticks by when the tick was made
   (`BossService.looted_since`), not by the boss's spawn day. Alternatives:
   map each key's PT spawn day to UTC and count spawns after the reset. Why:
   ticks are made at or after the loot, the store already keeps the tick time
   and the Garmoth cap uses the same rule. Reverses if: back-dated ticks of a
   last-week boss are seen to tick the new week's row.
4. Cue patterns ship `verified: false` (community UI wording, no operator
   screenshot checked yet); a wording fix is a data change in
   `server/ew/data/today_cues.json`.
5. Existing tests that used "Barter run" as the rule-less row now use an
   operator-added row (every seed row has a rule after this plan).
6. Build lane could not write its progress file in the MAIN checkout (write
   outside the worktree was not permitted in that run); gates were run
   inline instead. Reverses if: the lane sandbox allows the kit
   `write_progress` path.
7. Merge with main (plan 115): `AutoOcr.__init__` conflict in
   `server/ew/ocrauto.py`. Decision: keep both keyword args and both attrs
   (`currency` from 115, `on_doc` from 114; `on_doc` last). Alternatives:
   fold `on_doc` into one hook dict. Why: both are independent optional
   collaborators wired by keyword in `app.py`; no ordering coupling. Reverses
   if: a third doc consumer appears and a hook list is wanted.
