# Plan 170 - Olvia Academy semester epoch

Status: proposed. Source: research 0044 (Global Lab 2026-11-06).

## Problem

Plan 024 warns when the Lv 60 ETA lands after enrolment closes, but has no
notion of a semester: the 4th Semester runs from the 2026-11-12 maintenance to
before the 2027-02-25 maintenance, weekly quests end 2027-02-24 23:59, and the
3rd cohort auto-graduates with lecture progress reset at the 11-12
maintenance. Typed progress goes stale silently at that reset.

## Scope

1. Semester table as sourced data (number, start, end, weekly-quest end),
   consumed by plan 024's enrolment check and the plan 018 patch epoch.
2. At the semester boundary, stale-mark typed lecture progress (plan 079
   override ledger form) instead of carrying it over.
3. One line in the before-maintenance digest (plan 074): graduation reset and
   weekly-quest end.

## Tests

Failing test first: boundary stale-mark, enrolment check per semester,
digest line.

## Depends-on

024

## As-built

- `server/ew/olvia.py` + tracked `server/ew/data/olvia_semesters.json` (S4:
  2026-11-12T07:00Z .. 2027-02-25T07:00Z, weekly quests to 2027-02-24T23:59Z,
  needs_level 60, graduation_reset, verified false).
- Plan 024: each semester is a tracked deadline row `olvia-semester-<n>`
  (needs_level by the weekly-quest end); `/api/leveling` adds `semester`
  (running, else next) and `semester_error`.
- Plan 079: ledger key `olvia.lecture` (typed lectures done, int 0..100;
  POST /api/leveling {"lecture": n | null}); an entry set before the newest
  graduation_reset start is retired `semester_reset`; the view's `lecture`
  shows it as `stale` until new progress is typed.
- Plan 074: digest `ending` row kind `olvia` at a boundary maintenance
  (title <= 80 chars, the dashboard validTitle cap).
- Tests: `tests/test_olvia.py`; `tests/test_leveling.py` two exact-row
  asserts filter `olvia-semester-*`; `tests/test_zero_touch_keys.py` exempts
  `olvia.lecture`.

## As-built deviations

1. Plan 018 patch epoch NOT fed. Decision: the semester is its own epoch
   (`semester` view row), not an XP epoch. Alternatives: add the semester
   start to xp_epochs. Why: an XP epoch cuts the XP rate history (plan 018:
   rates only from samples after it); a semester start rescales no XP, so it
   would drop valid samples. Reverses if: a semester start ships an XP
   rescale (then add a normal xp_epochs row).
2. Enrolment cut-off = weekly-quest end. Decision: enrol_by_utc =
   quests_by_utc = weekly_quests_end_utc. Alternatives: semester end_utc.
   Why: no separate S4 enrolment date is published; plan 024 needs
   quests >= enrol and the weekly quests are the last thing to act on.
   Reverses if: an official notice gives an enrolment close date.
3. Ledger expiry `days:120` as a backstop. Decision: no new expiry rule;
   the boundary retire runs in OlviaService on every read / write.
   Alternatives: a new `until:semester_end` rule in overrides.py. Why: keeps
   the plan 079 rule set closed; the boundary sweep is the primary reset.
   Reverses if: another key needs a data-driven boundary rule.
4. No dashboard input yet. Decision: API only (POST op + view fields); the
   digest row renders through the existing ending-row path. Why: scope
   limited to server + data; the Leveling card control is a follow-up.
   Reverses if: the operator wants the input on the Leveling card (new row).
5. Semester rows join only with the tracked deadlines file (deadlines=None);
   a test injecting `deadlines` gets semesters only when it passes them.
   Why: keeps every existing fixture exact.
