# Plan 116 - Leveling auto: OCR / profile level reads make typed XP samples optional; deadlines derived

Status: open. Operator order session 28 (zero-touch wave). Lane hint:
`build`.

Goal: the XP rate, next-level ETA and deadline rows run from automatic
samples only; the onboarding step "Log an XP sample" and the typed deadline
rows stop being needed.

State today (read 2026-10-10): plan 066 parses level + XP % from
screenshots (`server/ew/ocrinfer.py:163` `level_field`) and commits a
sample unless `check_level` (line 428) holds it - a typed sample at or
after the shot always wins, and a held read waits in review. Plan 041
profile refreshes record level markers (no XP %). Onboarding still lists
"Log an XP sample - Progress > type your level and percent"
(`server/ew/onboarding.py:56`, satisfied by any sample). Deadlines (plan
024) are tracked `data/deadlines.json` rows plus operator-added
`deadlines_added`.

Inputs (ToS floor): screenshots + OCR, the public BDO-REST-API profile
(plan 004 / 041), the plan 064 official notice cache (no new GET). Nothing
reaches the game.

## Slices

1. Onboarding: the leveling step reads "done" when any sample exists
   (typed, ocr or profile) and its copy changes to "Take a screenshot with
   the XP bar visible (or refresh the profile)" - no typing asked.
2. Held reads resolve themselves: a read held as "XP went back" or "level
   below known" is auto-accepted when a later independent read (different
   shot, >= 2 min apart) agrees within 0.5 % - the older conflicting sample
   is marked superseded, not deleted; a single read stays held.
3. Profile anchor: a profile level marker newer than the newest sample with
   a higher level starts a new segment (rate restarts at that level), so a
   missed screenshot day does not produce a fake rate.
4. Derived deadlines: plan 064 notice parser offers deadline rows
   ("reach Lv N by <date>" / "enrol by" in an event Detail page, pattern
   data in `server/ew/data/deadline_patterns.json`, verified false) as
   suggest-then-auto rows (plan 111 gate: conf >= AUTO_APPLY_MIN adds them
   with `source: notice`, undoable); tracked rows stay; typed rows remain
   possible but are no longer the only path.
5. Leveling card: samples list badges source (typed / OCR / profile); the
   typed sample form moves into the details row.

## Tests first

- `tests/test_leveling_auto.py`: onboarding done from an OCR-only sample;
  held read + agreeing later read -> both committed, conflicting sample
  superseded; single held read stays; profile marker starts a segment;
  notice text fixture -> deadline row source notice; low-conf pattern ->
  suggestion only; dedupe against tracked rows.
- `app/test/leveling.test.js`: source badges, form location.

Acceptance: from a fixture of three OCR level reads and one profile refresh
(no typed sample) the leveling view shows a rate, ETA and one derived
deadline with its status; gates green; verifier PASS within 3 rounds; one
push.

Retires: the typed level / XP % sample (KEEP-RECORD only) and typed
deadline rows as the only deadline source.

Depends on: 111.

## As-built deviations (build lane, 2026-10-10)

Each self-adjudicated (decision / alternatives / why / reverses if).

1. Notice row tag. Decision: a derived row keeps `source` = the notice URL
   (the plan 024 citation field) and the view marks it `by: "notice"` (plus
   `conf`, `group_no`); tracked / typed rows read `by: "tracked"` /
   `"typed"`. Alternatives: overwrite `source` with "notice". Why: `source`
   is the row's citation everywhere (tooltip, verify); losing the URL breaks
   that. Reverses if: a consumer needs `source == "notice"`.
2. Notice deadline undo. Decision: the row's x (`deadline_del`) is the undo;
   the id goes to `deadlines_deleted`, so a later notice sync never re-adds
   it. Low-conf rows are `deadline_suggestions` with Accept
   (`deadline_accept`) / x. No `auto_applied` row. Alternatives: log notice
   rows in the plan 111 OCR audit log. Why: that log is the OCR card's (its
   Undo routes through AutoOcr); notice rows live in leveling. Reverses if:
   the operator wants one cross-domain auto log.
3. Sync gate. Decision: derived deadlines sync on every notice read, gated
   per row by conf (`leveling.NOTICE_AUTO_MIN` = plan 111 0.95, a test pins
   them equal), not by the plan 064 `auto_add` switch. Why: plan 116 names
   the plan 111 gate; claim windows (086) also sync always. Reverses if: the
   operator wants notice deadlines behind auto_add.
4. Profile segment fallback. Decision: a newer-higher profile marker
   restarts the rate there; until two reads follow it the rate measured
   before the marker stands (no delta ever spans the gap). Alternatives: no
   rate until two post-marker reads. Why: the plan 041 test pins "rate from
   the typed samples" under a marker, and a pre-gap rate is a real one; the
   fake rate the plan targets is the delta across the gap, which never
   forms. Reverses if: a stale pre-level rate misleads in use.
5. Agreement rule. Decision: both reads at or over the OCR commit gate
   (0.9), from different shot files, >= 120 s apart, within 0.5 cumulative
   level-percent (level x 100 + pct); "older than a typed / later sample"
   holds never self-resolve. Superseded = counted samples older than the
   later read that sit above both reads (a profile marker counts as its
   level start). Both commits are logged in `auto_applied`; Undo of the later
   one un-supersedes them. Review items carry `hold` (older / below / back).
6. Parse version. Decision: `maintdigest.PARSE_V` 3 -> 4 (cached Detail
   reads re-read once inside the plan 064 budget) and "lv" added to the
   sentence-split abbreviations ("Lv. 61" ends no sentence);
   `test_claimwindows` now pins `PARSE_V >= 3`. Why: `deadlines` is a new
   parsed field of the Detail page; no new GET or host.
7. Onboarding. Decision: title "Record your XP", hint "Take a screenshot
   with the XP bar visible (or refresh the profile) for the ETA."; the old
   `test_leveling_needs_a_typed_sample` (marker is no sample) became
   `test_leveling_done_from_any_sample` - the plan reverses that rule.
8. Patterns. Decision: three specific patterns (reach / enrol, both word
   orders) at 0.96-0.97 and one generic sign-up / join pattern at 0.8 (a
   suggestion); two different levels in one sentence x 0.8. Dedupe: same
   level and enrolment within 2 days of a tracked / set row. The file ships
   `verified: false` (estimated wording, no live notice measured yet).
   Reverses if: a live notice words it differently (edit the data file).
9. Progress file. The lane run's permissions denied writes outside the
   worktree (Write tool and helper script), as in plan 111, so
   `progress/p116-build.json` was not written. Reverses if: the lane grants
   the kit `write_progress` call.
