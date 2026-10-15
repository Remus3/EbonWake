# Plan 132 - My Info (P) exact XP OCR: absolute XP samples for the rate fit

Status: open. Source: deep dive 0026 (Global Lab notes posted 2026-10-08: My
Info (P) shows current XP, XP needed for the next level and absolute max XP;
patch live 2026-10-15). Lane hint: `build`. Depends on: 116, 063, 018.

Problem: plan 116 derives XP rate from level and XP % reads. At Lv 66-75 a
level needs billions of XP, so two-decimal percent steps are coarse and short
sessions fit poorly. The new My Info window prints absolute numbers.

## Slices

1. OCR kind `myinfo_xp` (plan 063 registry): reads level, current XP, XP to
   next level from a My Info (P) shot; digit-group guard from plan 016;
   confidence-gated auto-apply per plan 111.
2. Store absolute `xp` beside `pct` in the leveling sample; the rate fit
   prefers absolute deltas and falls back to percent. Cross-check: pct must
   equal xp / (xp + to_next) within 0.01, else the read is held.
3. Seed per-level XP-to-next from reads (data file grows from observation, each
   row sourced "operator shot"); level-up inside a window is handled by sum.
4. Plan 130 suspect windows still exclude samples; chip unchanged.
5. Tests: fixture shots with commas dropped, mismatch hold, level-up delta,
   fallback to percent, ASCII.

## Out of scope

Adventurer's Note (F2) figures (a later kind); any game input.
