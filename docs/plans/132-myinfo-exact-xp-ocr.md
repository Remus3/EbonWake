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

## As-built (build lane, 2026-10-15)

Code: `ocrinfer.myinfo_xp_field` (kind `myinfo_xp`, value {level, xp,
to_next, pct}); `ocrauto` registers the kind (accept / discard only, not in
FIX_KINDS), auto-applies at `max(ocr.auto_commit_min, AUTO_APPLY_MIN)` with an
`auto_applied` row and Undo, holds a pct mismatch (`hold: "mismatch"`) and the
plan 066 / 116 history holds (older / below / back); `leveling` keeps `xp` /
`to_next` on OCR samples, `rate_xp_h` / `xp_gain` (level-up summed), the exact
percent in the percent fit, view keys `rate_xp_h`, `rate_source` (xp | pct),
`xp`, `to_next`, `level_xp`. App: review / applied rows and labels
(`ocr.part.js`), "512M XP/h" on the overlay leveling line. Tests:
`tests/test_myinfo_xp.py`, `app/test/myinfo_xp.test.js`.

## As-built deviations

Each self-adjudicated (decision / alternatives / why / reverses if).

1. Label wording. Decision: labels matched are "Current EXP", "EXP to Next
   Level" / "EXP needed|required" / "needed|remaining EXP" and "Max EXP"
   (number on the line, else the next unlabelled neighbour line).
   Alternatives: wait for a live shot. Why: the patch is live today and no
   shot exists yet; the Global Lab notes name the three figures. Reverses if:
   a real My Info shot words them differently (edit the three regexes).
2. Digit-group guard. Decision: the sum current + to next = max is the guard
   (conf 0.97 whatever the separators; a mismatch 0.5). Without the max line
   the conf is the weaker part's (comma grouped 0.97, dropped commas / dot
   grouped 0.9, broken groups 0.6). Alternatives: the plan 016 tsv box-bottom
   rule. Why: three printed numbers check each other with no image access; a
   dropped comma keeps the sum, a cut group breaks it. Reverses if: a live
   shot shows the max line missing on most reads (then add the box rule).
3. Gate. Decision: auto-apply at plan 111 AUTO_APPLY_MIN (0.95), not the
   0.9 level-read gate; 0.9-0.95 reads queue. Why: plan text names plan 111.
   Reverses if: dropped-comma reads without the max line queue too often.
4. Held reads do not self-resolve. Decision: plan 116 agreement stays for
   `level` reads only; a held `myinfo_xp` read waits in review. Why: the
   agreement path commits as `level` (no xp); exact reads rarely conflict.
   Reverses if: held My Info reads pile up in review.
5. Level totals table. Decision: observed totals live in the store
   (`leveling.level_xp` {"<level>": {total, ts, source: "operator shot"}}),
   not a tracked data file; Undo of the read removes its row. Alternatives: a
   tracked `server/ew/data/` file. Why: the server never writes tracked files;
   the store is the runtime data file that grows from observation. Reverses
   if: a later plan wants a shipped seed table (copy the store rows into one).
6. Rate output. Decision: `rate_pct_h` stays the headline (exact percent
   from absolute reads), `rate_xp_h` is added and `eta_next_s` uses to_next /
   rate_xp_h when the newest sample is an absolute read. Why: every consumer
   (books, deadlines, home) reads the percent rate; changing its unit would
   break them. Reverses if: a consumer needs XP units.
7. Progress file. The lane run's permissions denied the write outside the
   worktree (as in plans 111 / 116), so `progress/p132-build.json` was not
   written. Reverses if: the lane grants the kit `write_progress` call.
8. Merge resolution (refute round 1/3). Decision: the plan 131 and plan 132 branches both
   edited the OCR kind lists, so conflict markers were left in `ocrauto.py` and
   `ocr.part.js`; both sides are kept (`daynight.KIND` and `MYINFO_KIND` in
   KINDS / the log-applied tuple; `gametime` and `myinfo_xp` in the applied and
   auto kind lists, validator and label). Alternatives: drop either side. Why:
   the two kinds are independent. Reverses if: plan 131 or 132 renames its kind.
