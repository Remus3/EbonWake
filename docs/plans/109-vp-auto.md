# Plan 109 - Value Pack auto: VP armed from the buff OCR with its expiry; market.vp retires to a fallback

Status: open (priority). Operator order session 28 (zero-touch wave). Lane
hint: `build`.

Goal: `market.vp` is never typed in normal use. The Value Pack state and
its expiry come from the buff timer the auto-OCR arms; the Settings bool
becomes a fallback override. Wave goal (ZERO-TOUCH): after 108 + 109 the
only plan 079 ledger key that still needs an operator value is
`profile.multi_character`.

State today (read 2026-10-10): `server/ew/app.py:490` `_vp_live` returns
True while the plan 005 "Value Pack" grind buff timer has `left_s > 0`;
plan 066 OCR arms that row (`server/ew/ocrauto.py` `buff_fields`, name
match x time parse). Gaps:
- With no timer armed `_vp_live` returns None and the typed / config
  `market.vp` (expiry days:30, `server/ew/data/override_policy.json`) or the
  default False decides - a lapsed timer never says "VP off".
- The 30-day cap (`grind.MAX_BUFF_MINUTES = 43200`) and `TIME_AT_CAP` lower
  the confidence of a fresh 30-day VP read, so a just-bought VP is queued
  for review instead of armed.
- Settings still shows "Value Pack active" as a primary bool
  (`app/shared/core/settings.part.js:143`).
- The expiry is not surfaced (no "VP ends 11-02" on Timers / digest).

Inputs (ToS floor): operator screenshots of the buff bar / buff tooltip
(plan 063 auto-OCR) and the clock. Nothing reaches the game.

## Slices

1. Tri-state live signal: `_vp_live` returns `{value: True, signal:
   vp_timer, ends}` while armed and `{value: False, signal: vp_expired}`
   for `VP_GRACE_S` (module constant, 7 days) after an armed timer ran out
   with no newer read - net figures switch to no-VP at once. After the
   grace with no read: None (fallback chain as today).
2. Value Pack read confidence: a "Value Pack" name match with a time at or
   just under the 30-day cap is a normal read for this buff only (the cap is
   its length); a renewal read (ends later than the armed end) commits
   without review; a read ending earlier than the armed end is queued.
3. Expiry surfaces: Timers card row "Value Pack ends MM-DD HH:MM" (plan
   076), plan 074 digest row at T-24 h. Informational, no What now row.
4. Settings retire: the bool moves behind an "override" disclosure under a
   read-only line: "Value Pack: active until 11-02 (OCR)" / "off (expired
   10-05)" / "unknown - no VP assumed"; a typed override keeps days:30.
5. Zero-touch guard: `tests/test_zero_touch_keys.py` enumerates
   `override_policy.json` keys that have no live signal and no fixed
   default and asserts the list is exactly `profile.multi_character` plus
   named exemptions with a reason each (plan 080 config incident switches,
   pure preferences ui.* / overlay.mode.* / notify.mute_until, auto-detected
   bdo.*_dir, the profile.family identity key).

## Tests first

- `tests/test_vp_auto.py`: armed timer -> True with ends; ran out 1 h ago
  -> False signal vp_expired and a typed True override retires; 8 days after
  expiry -> fallback; a 29 d 23 h read commits at the gate; a renewal read
  extends; a shorter read is queued.
- `tests/test_zero_touch_keys.py`: the slice 5 guard.
- `app/test/settings.test.js`: the VP read-only line + disclosure; the
  Timers row formatter in ewcore.

Acceptance: a fixture read of "Value Pack 29 d 23 h" arms VP, market net
proceeds use the VP rate and Settings shows the derived line; the clock
passing the end flips tax to no-VP with no typed input; gates green;
verifier PASS within 3 rounds; one push.

Retires: the typed `market.vp` Settings bool as a required input (fallback
override only).

Depends on: 108.
