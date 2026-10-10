# Plan 124 - XP book stock and Imperial delivered count from reads

Status: open. Proposed by plan 120 (research 0021 section 2). Lane hint:
`build`.

Goal: two small typed counters retire by reusing readers that already exist:
(a) a loot / catalog read (plan 113) naming an XP book adds it to the plan
011 book stock (`leveling.book_add`), so `book_use` (plan 111) draws from a
stock nobody typed; (b) the Imperial delivery window's remaining-count text
sets today's delivered boxes per type (`imperial.deliver`).

State today (read 2026-10-10): `book_add` ({size, n}) and `deliver` ({type,
add}) are typed only; book names and sizes live in `data/xp_books.json`; the
daily cap is CP / 2 (plans 053 / 117).

Inputs (Game ToS floor): operator-saved screenshots through the plan 063
pipeline. Nothing reaches the game.

## Slices

1. Book stock: when a committed `loot` read's item matches an
   `xp_books.json` name, `leveling.book_add({size, n: count, activity:
   "loot"})` runs once per read id (idempotent; undo of the loot read takes
   the books back).
2. Delivered: parser `ocrinfer.imperial_delivery_fields(doc)` -> {kind:
   "imperial_left", name: cooking|alchemy, value: remaining}: "Remaining
   Deliveries: N" (or "N / M") under an "Imperial <Cooking|Alchemy> Delivery"
   title (`titles.imperial_delivery`, unverified); delivered today = cap -
   remaining, set (not added) through a new `imperial.ocr_delivered`, only
   for a shot taken after today's reset.
3. Gate, review, undo and `auto_applied` as plan 111.

## Tests first

- `tests/test_leveling_books_loot.py`: book loot read adds stock once, re-run
  no-op, undo removes; non-book loot ignored.
- `tests/test_imperial_delivered_ocr.py`: remaining parse per type, shot
  before reset ignored, cap unknown queues for review, typed tick newer wins.

## Acceptance

A fixture loot doc with "Secret Book of Old Moon x 2" grows the stock by 2;
a fixture delivery doc sets delivered = cap - remaining; gates green;
verifier PASS within 3 rounds; one push.

Retires: typing XP book stock and delivered box ticks.

Depends on: 113 (loot reader), 117 (CP cap), 111.
