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
