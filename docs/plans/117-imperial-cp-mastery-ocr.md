# Plan 117 - Imperial CP + Imperial mastery from OCR

Status: open. Operator order session 28 (zero-touch wave 2). Lane hint:
`build`.

Goal: the Imperial delivery planner (plan 053) fills its two operator inputs,
contribution points (CP) and the per-type mastery payout bonus, from
screenshots the operator already takes: the Energy / CP bar readout and the
life-skill mastery window. A typed value stays possible but becomes an
expiring override, so a stale typed number never silently outlives the
screenshots.

State today (read 2026-10-10): `server/ew/imperial.py` takes CP from the plan
042 profile card, else the newer of a typed CP (`cp`, `cp_at`) and the newest
committed plan 081 OCR `cp` read (`ocrinfer.cp_field`, "Contribution Points
120 / 312" or "CP 120/312"); a typed CP never expires. Mastery is typed only
(`mastery` {type: pct}, no set time) and nothing reads it from a screenshot.

Inputs (ToS floor): operator screenshots + OCR (plan 063 / 081 / 111), the
operator's typed values. Nothing reaches the game.

## Slices

1. CP bar shapes: `ocrinfer.cp_field` also reads the bar label without
   "points" ("Contribution 120/312", "Contrib. 120 / 312") and a pair on an
   Energy / CP bar line ("Energy 210/300  CP 45/312" reads 312, never 300).
2. Mastery parser `ocrinfer.mastery_fields(doc)` -> [{kind: "mastery", name:
   cooking|alchemy, value: pct, conf, why}]: a line "Imperial <Cooking|
   Alchemy> Delivery ... +40.5%" (type on the line, conf 0.95), or "Imperial
   Delivery ... +40.5%" with exactly one of "Cooking Mastery" / "Alchemy
   Mastery" named in the doc (conf 0.9); a decimal comma drops conf to 0.85;
   a value over the planner bound (500) is no read. Part of
   `planner_fields`.
3. Kind wiring: `mastery` joins `ocrauto.PLANNER_KINDS` (so KINDS and
   FIX_KINDS); committed reads land in `ocr_reads.mastery` with their `name`;
   `latest("mastery:<type>")` returns the newest read of that type; review fix
   is the corrected percent. Undo removes the read like any planner read.
4. Imperial precedence per input (CP and each mastery type): profile CP
   first (CP only), then the newer of typed and the newest read
   (`derived.pick`), except a typed value older than `TYPED_TTL_S` (7 days)
   is EXPIRED: any read then wins whatever its age; with no read the typed
   value is still used, flagged `expired`. Typed mastery gains a set time
   (`mastery_at`); a pre-117 typed mastery with no set time loses to any read.
   `POST {mastery: {type, pct: null}}` clears a typed mastery.
5. Overrides: `typed_overrides()` lists the typed CP and each typed mastery
   in force with `expires_at`; `/api/overrides` shows the expiry countdown
   (it no longer forces `expires_at: null` on these rows).
6. Surface: `/api/imperial` `cp` gains `expires_at`, `expired`; each type row
   gains `mastery_source`, `mastery_at`, `mastery_age_s`, `mastery_typed`,
   `mastery_expires_at`, `mastery_expired`. The Today card shows
   "+40.5% mastery (from screenshot, 2h ago)" / "(typed)" / "(typed,
   expired)"; the OCR card lists CP and mastery review rows.

## Tests first

- `tests/test_imperial_ocr.py`: CP bar shapes (label without points, energy
  pair never read as CP); mastery line shapes (type on line, type from header,
  two headers = no type = no read, comma, over bound); worker commits a
  mastery read and undo removes it; review fix of a mastery read;
  `latest("mastery:cooking")` per type; imperial precedence (read beats older
  typed, newer typed beats read, typed past TTL loses to an older read, typed
  past TTL with no read stays and is flagged expired, pre-117 mastery loses to
  a read); typed_overrides carry expires_at; acceptance over the HTTP route:
  a fixture CP bar doc + mastery window doc fill cap and payout.
- `app/test/imperial.test.js`: mastery source text, expired CP text, mastery
  null body allowed; `app/test` OCR helpers: cp / mastery rows and fix body.

Acceptance: fixture CP bar + mastery window OCR docs set the cap (CP / 2) and
the mastery bonus on the card with source and age; a typed value expires to
the read after 7 days; gates green; verifier PASS within 3 rounds; one push.

Retires: typing CP and mastery as a standing input (both stay as overrides).

Depends on: 111 (plan 053, 081 in place).

## As-built deviations

1. Expired typed value with no read. Decision: it stays in force, flagged
   `expired` ("(typed, expired)" on the card), and is still listed in
   /api/overrides with `expires_in_s` 0. Alternatives: drop it (cap unknown,
   mastery 0). Why: dropping a correct number the operator typed only
   because no screenshot came in would make the planner worse, and the flag
   already says the value is unconfirmed. Reverses if: the overrides ledger
   gains a sweep that retires expired typed rows for every planner input.
2. TTL. Decision: `TYPED_TTL_S` = `derived.STALE_S` (7 days). Alternatives:
   a per-input policy row in `data/override_policy.json`. Why: plan 081's
   stale marker uses the same 7 days, so a read and a typed value age on one
   clock; CP and mastery both change slowly. Reverses if: a policy row for
   `imperial.*` keys is added (read it instead of the constant).
3. Mastery points are not converted. Decision: only the printed imperial
   delivery bonus percent is read; "Cooking Mastery 1,250" alone is no read.
   Alternatives: a points -> bonus table. Why: no table the lane can cite
   (no web access; plan 053 deviation 1 has the same limit). Reverses if: a
   sourced table lands in a tracked data file.
4. Mastery read storage. Decision: `ocr_reads.mastery` rows carry `name`
   (the type) and `AutoOcr.latest("mastery:<type>")` filters on it; the
   imperial `reads` callback stays one-argument. Alternatives: two kinds
   (`mastery_cooking`, `mastery_alchemy`); a second callback argument. Why:
   one kind matches the plan 063 {kind, name, value} contract (gear does the
   same with ap / aap / dp) and keeps the existing callback signature and its
   test fakes. Reverses if: a third per-name planner kind appears (then give
   `latest` a name argument).
5. App OCR card. Decision: `cp` and `mastery` join the dashboard's
   OCR_AUTO_KINDS (review / commit rows were filtered out before, so a held
   CP read was invisible), and a review fix may be a number with at most 2
   decimals (0..500) for a mastery percent. The old "fix value 1.5 is
   invalid" guard case became 1.555 / 501.5. Alternatives: whole-percent
   mastery fixes only. Why: imperial bonuses print with decimals; the server
   checks each kind's range anyway. Reverses if: a kind needs a decimal fix
   outside 0..500 (then pass the kind to the validator).
6. CP bar: the existing plan 081 reader already read "CP 45/312" on an
   Energy / CP line; the new label forms are "Contribution" and "Contrib."
   without "points". No Energy read is added (no planner input uses it).
