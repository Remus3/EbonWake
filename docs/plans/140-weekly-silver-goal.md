# Plan 140 - Weekly silver goal: target, pace and projection from session and sales ledgers

Status: open. Source: research 0029 finding C1 (plan 134). Lane hint:
`build`.

Problem: EW measures silver (grind log silver/h `server/ew/grind.py:70`,
session silver delta `:1351`, silver-OCR rate and delta
`server/ew/ocrinfer.py:772,814`, sold-items ledger plan 123) but never says
whether this week is on pace, the question that sizes a grind session.

## Slices

1. Tests first: `tests/test_silvergoal.py` for pure
   `server/ew/silvergoal.py`:
   - week = the plan 021 weekly reset window (NA, the same rule the Today
     weeklies use); no new reset constant.
   - `earned_week(sources, week)`: sum of grind-session silver (auto rows of
     plan 112 and typed rows) plus sold-items net (plan 123), de-duplicated so
     a sale is not counted twice when a silver-OCR delta also covers it
     (sales win; the OCR delta fills only gaps).
   - goal: an explicit override (plan 079 ledger key `grind.week_goal`,
     expiring with the week) else the median of the last 4 full weeks'
     earned plus 10 percent, else none (card hidden, zero-touch).
   - `pace`: needed per remaining day, projection at the trailing 7-day
     rate, `on_track` bool; all integer silver.
2. `GET /api/silvergoal` read-only; the goal override uses the existing
   override write route (no new POST route).
3. Grind tab card "This week": earned / goal bar, needed per day, projection;
   What-now (plan 069) gains one suggestion only when `on_track` is false and
   the game is running. `app/test/silvergoal.test.js` for the render helpers.

## Acceptance

- New Python and app tests green; ruff green.
- With 4 weeks of fixture history and no override the goal equals median
  plus 10 percent; an override wins until the weekly reset.
- A sale also seen as an OCR silver delta is counted once.

## Game ToS

Reads EW's own ledgers built from operator screenshots, the session log and
public APIs; no game input, memory read or client file.

Depends on: none.

## As-built deviations

1. Typed goal write path. Decision: POST /api/grind `{"week_goal": silver |
   null}` (an op on the existing grind route; null clears) writes ledger key
   `grind.week_goal`, like plan 131's night toggle. Alternatives: a settings
   SPEC key through POST /api/settings (would write a weekly value into
   config/local.json and leave it there after expiry); a new POST route
   (forbidden by the plan). Why: no new route, nothing written to the config
   file, same pattern as the other grind ledger key. Reverses if: the
   settings route gains non-file ledger keys.
2. New override expiry rule `until:week_reset` (overrides.RULE_RE /
   expiry_at): the next NA weekly reset after set-at, via
   today.next_weekly_reset - no new reset constant. Alternatives: `days:7`
   (outlives the week it was typed in). Why: the plan asks for "expiring
   with the week". Reverses if: the ledger gains a generic reset-rule expiry.
3. Zero-touch guard: `grind.week_goal` is an EXEMPT key (pure preference;
   the history goal applies without it) in tests/test_zero_touch_keys.py.
   Alternatives: none (the guard fails any new typed key). Reverses if: a
   live goal signal appears.
4. Session silver is the row's `silver` (typed or OCR delta), not the plan
   039 loot value. Alternatives: loot value as the Summary card uses. Why:
   unsold loot is not earned silver, and counting it double-counts when it
   sells. Reverses if: the operator asks for loot value in the weekly figure.
5. History weeks: the last 4 full weeks that END after the first ledger
   entry; a quiet week after that counts as 0. Fewer than 4 such weeks use
   what exists; none, or a median of 0, means no goal. Alternatives: require
   4 full weeks (no goal for a month after install). Why: zero-touch sooner.
   Reverses if: a 1-week median proves noisy in use.
6. Card with no goal: the "This week" card folds to its pill ("no goal
   yet") plus a closed `weekly silver goal` details form, so a goal can be
   typed before a full week of history exists. Alternatives: fully hidden
   (no way to type the first goal). Reverses if: the goal form moves to
   Settings.
7. What-now source `silver` (weight 0.3, undated, nominal 4 h, horizon 7 d)
   in data/whatnow_weights.json; the candidate needs `running` (game state
   running / logged_in), `hidden: false`, `on_track: false` and a positive
   needed-per-day. Alternatives: due the weekly reset (a low score until the
   last day). Why: an undated low-weight row surfaces while playing without
   crowding timed actions. Reverses if: it outranks timed rows in use.
