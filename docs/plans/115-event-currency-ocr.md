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

## As-built deviations

1. Spends. Decision: the hold floor is the logged projection at the shot
   (login days + ticks, no balance) minus the event's wishlist cost.
   Alternatives: no subtraction (every real exchange purchase would be held);
   a spend ledger (no input exists - purchases are never read). Why: the
   wishlist is the most the operator plans to spend, so a read under that
   floor is a misread or an unplanned spend, both worth a look. Reverses if:
   exchange purchases become an input (then subtract them instead).
2. Storage. Decision: the read lives in `event_wishlist.ocr` {event: {id,
   value, at (shot), set_at, expires_at, source}} beside `balances`, not in
   the same entry. Alternatives: one entry per event with a `source` field.
   Why: "newest wins" compares the typed `set_at` with the shot time, so an
   older shot processed after a typed value must not erase it; two entries
   keep both and the undo of a read restores the read it replaced. Reverses
   if: the typed field is removed (then one entry suffices).
3. Typed field kept. Decision: the typed "balance now" input stays as an
   optional override (slice 3 still ranks a newer typed value over a read);
   the plan's "Retires" line is met by the read replacing the need to type.
   Alternatives: delete the input. Why: slice 3's precedence needs a typed
   value to exist; the operator can still correct a read without a shot.
   Reverses if: a later plan drops typed precedence.
4. Older shot. Decision: a read from a shot older than the stored read is
   dropped silently (not queued); a review accept / fix of one is refused.
   Why: the newer read already reflects drops since; queueing would only add
   noise. Reverses if: reads start arriving out of order in practice.
5. Ambiguity. Decision: two different amounts for one currency on one shot
   (e.g. an exchange cost row "80 Seals of Purification" and the owned
   count) keep the amount on a line labelled owned / have / balance; with no
   label the field drops to conf 0.5 (review). A line with cost / price /
   required is never read. Why: exchange rows print costs beside the same
   currency name. Reverses if: a verified exchange layout gives fixed regions.
6. Label age is rendered server-side in `label(row, now)` and mirrored by
   `currencyText(r, now)` ("just now" / "N min ago" / "N h ago" (< 48 h) /
   "N d ago"); the row carries `balance_at`.
