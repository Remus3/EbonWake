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

## As-built (build lane, 2026-10-16)

Code: `ocrinfer.adv_note_xp_field` (kind `adv_note_xp`, same value / guards
as `myinfo_xp` via the shared `_exact_xp_field`), `ocrinfer.xp_cross` (pure
cross-check), `XP_SOURCES` {myinfo_xp: myinfo, adv_note_xp: f2};
`leveling.ocr_sample(..., xp_src=)` keeps `xp_src` on the sample; `ocrauto`
registers the kind (accept / discard only, AUTO_APPLY_MIN gate, applied row
with Undo), holds a disagreement (`hold: "disagree"`, `conflict: [ts]`) and
`AutoOcr.xp_advisories()` feeds `GET /api/known-issues` (area leveling / all).
App: `ocr.part.js` review / applied rows labelled "F2 Lv ...". Tests:
`tests/test_adv_note_xp.py`, `app/test/adv_note_xp.test.js`.

## As-built deviations

Each self-adjudicated (decision / alternatives / why / reverses if).

1. F2 detection. Decision: a shot is F2 only when a line carries the
   "Adventurer's Note" title (apostrophe optional); otherwise it is read as
   My Info. Alternatives: layout regions. Why: the figures and labels are the
   same in both windows and no operator shot exists yet (slice 3: fixtures
   only from operator shots - the fixtures here are synthetic text docs, not
   scraped). Reverses if: a live F2 shot shows no title line (then add a region
   or label rule).
2. What "differ by over 0.01 percent" compares. Decision: the level total
   (xp + to_next) of the two reads, same level, shots within 600 s
   (inclusive), tolerance 0.01 percent of the larger total. Alternatives: the
   two reads' pct values. Why: pct legitimately moves while grinding between
   two shots minutes apart, the level total does not; XP going back is
   already held by the plan 116 `back` rule for both kinds. Different-level
   pairs (a level-up between shots) are not compared. Reverses if: a live
   disagreement shows equal totals with wrong current XP.
3. "Hold both". Decision: the new read is queued (`hold: "disagree"`), the
   committed other-kind sample is marked superseded (plan 116: kept, listed,
   not counted). Accept commits the new read and keeps the other superseded
   (Undo of that commit counts it again); discard counts the other again.
   Alternatives: un-commit the earlier sample into review. Why: reuses the
   plan 116 supersede / Undo path, nothing is deleted. Reverses if: the
   operator wants both reads side by side in review.
4. Plan 130 advisory. Decision: a runtime row (id `ocr-xp-disagree`, area
   leveling, `exclude_samples: false`, `verified: false`) derived from the
   review queue and appended by `GET /api/known-issues`, so the existing
   Leveling known-issue chip shows it; never written to the tracked
   `known_issues.json`. Alternatives: a new chip / store domain. Why: the
   tracked file is hand-curated and read at start; the server never writes
   tracked files. Reverses if: plan 130 grows a runtime advisory store.
5. Progress file. The lane run writes `progress/p133-build.json` only if the
   permissions allow the write outside the worktree (as in plans 111 / 116 /
   132). Reverses if: the lane grants the kit `write_progress` call.
