# Plan 115 - Event currency balance OCR kind feeding eventcurrency

Status: open. Operator order session 28 (zero-touch wave). Lane hint:
`build`.

Goal: the plan 095 currency balance comes from a screenshot of the event
exchange / inventory tooltip, so the typed "balance now" is optional and
drops are counted.

State today (read 2026-10-10): `server/ew/eventcurrency.py` projects
`earned_so_far` from login days and ticks; a typed balance lives in store
domain `event_wishlist.balances` {event: {value, set_at, expires_at}}
(plan 095 deviation 4) and replaces earned when set; random field drops are
never projected, so without typing the shortfall is overstated.

Inputs (ToS floor): operator screenshots + OCR (plan 063), the tracked
`server/ew/data/event_currency.json` currency names. Nothing reaches the
game.

## Slices

1. Parser `ocrinfer.currency_field(doc, rules)` -> [{kind:
   "currency_balance", name: event no, value: int, conf, why}]: a line with
   a currency name from active events (fold + edit distance <= 2) and an
   integer within 60 px on the same or next line ("Seals of Purification
   x 140", "140 Seals of Purification", exchange window "Owned: 140"); conf
   from name ratio x digit-group sanity; a value below the current earned
   projection minus spends is held for review.
2. Kind wiring: `currency_balance` in `ocrauto.KINDS` + FIX_KINDS; commit
   -> `CurrencyService.set_balance(event, value, source="ocr:<file>",
   at=shot_at)` stored beside typed balances with `source`.
3. Precedence: the newest of OCR / typed wins (typed newer than the read
   still wins, badged); an OCR balance expires at the event end like the
   typed one; drops are now inside the balance, so `guaranteed` = balance
   + remaining projected sources.
4. Surface: Events currency row shows "140 (OCR, 2 h ago)".

## Tests first

- `tests/test_eventcurrency_ocr.py`: three line shapes parsed; unknown
  currency ignored; inactive event ignored; distance-2 name; held when far
  below earned; commit replaces earned and expires at event end; a newer
  typed balance wins over an older read and vice versa.
- `app/test/eventcurrency.test.js`: the OCR source label.

Acceptance: a fixture exchange-window OCR doc sets the 10673 balance and
the Events row shows the read with source; gates green; verifier PASS
within 3 rounds; one push.

Retires: the typed event currency "balance now" field.

Depends on: 095.
