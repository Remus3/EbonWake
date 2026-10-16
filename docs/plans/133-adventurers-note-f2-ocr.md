# Plan 133 - Adventurer's Note (F2) level-figures OCR: a second exact-XP window

Status: open. Source: deep dive 0027 (Global Lab notes posted 2026-10-08: the
My Info icon opens Adventurer's Note F2 with detailed level figures; plan 132
listed it as out of scope). Lane hint: `build`. Depends on: 132, 063, 016.

Problem: plan 132 reads exact XP only from My Info (P). If P is cropped, covered
or its layout shifts, the rate fit falls back to percent. F2 shows the same
level figures; a second kind gives redundancy and a cross-check.

## Slices

1. OCR kind `adv_note_xp` (plan 063 registry): level, current XP, XP to next
   level from an F2 shot; plan 016 digit-group guard; plan 111 auto-apply gate.
2. Reuse the plan 132 sample writer; source tag `f2` beside `myinfo`. When both
   kinds read within 10 minutes and differ by over 0.01 percent, hold both and
   raise a plan 130 advisory.
3. Layout fixtures only from operator shots; no scraping.
4. Tests: comma-drop fixtures, agreement, disagreement hold, ASCII.

## Out of scope

Any game input or memory read; Guild Fame, Life Skill gear panels.
