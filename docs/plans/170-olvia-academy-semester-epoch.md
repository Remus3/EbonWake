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
