# Plan 121 - Pet window OCR fills the pets roster

Status: open. Proposed by plan 120 (research 0021 section 2). Lane hint:
`build`.

Goal: the plan 043 pets card stops being a typed roster. A screenshot of the
in-game pet list (and of one pet's info page) the operator already takes is
read into roster rows: name, species, tier and talents. A typed edit stays a
newer-wins override, like every plan 111 read.

State today (read 2026-10-10): `server/ew/pets.py` rows are `ROW_FIELDS`
(name, species, tier, talents, alpha, out), all typed through `POST
/api/pets {add|edit}`; species names and skills come from `data/pets.json`.
No OCR kind targets pets.

Inputs (Game ToS floor): operator-saved screenshots (the game's own
screenshot key) read by the plan 063 pipeline, `data/pets.json` species names,
the operator's typed values. Nothing reaches the game; no memory, packets or
client files.

## Slices

1. Title cue: `data/ocr_regions.json` `titles.pet_list` / `titles.pet_info`
   (panel titles, `verified: false` until a real shot is measured).
2. Parser `ocrinfer.pet_fields(doc, species_names)` -> [{kind: "pet", name,
   value: {species, tier, talents}, conf, why}]: a row "Tier 4 <species>"
   with a species name from `data/pets.json` (case / punctuation-insensitive,
   one-edit fuzzy match drops conf by 0.05); talents only on a pet info shot
   ("Talent" lines, at most 5); tier outside 1..5 is no read.
3. Kind wiring: `pet` joins `ocrauto.KINDS` and `FIX_KINDS`; a read at or
   over the plan 111 gate upserts the roster row matched by (species, name)
   through a new `pets.ocr_set` (undo `ocr_restore`), else it queues for
   review; every apply lands in `auto_applied`.
4. Precedence: per field the newer of a typed edit (`typed_at`) and the read
   wins; `alpha` and `out` stay typed (the list shot does not show them
   reliably).
5. Surface: `/api/pets` rows gain `source` (`ocr:<file>` | typed) and
   `read_at`; the card shows "(from screenshot, 2h ago)".

## Tests first

- `tests/test_pets_ocr.py`: synthetic OCR docs (no images): list row read,
  fuzzy species, tier bounds, talents only on info shots, review below gate,
  undo restores the prior row, typed newer beats read, read newer beats typed.
- `app/test`: OCR card row text for kind `pet`.

## Acceptance

A fixture pet list doc + pet info doc fill a roster row with species, tier
and talents and the source label; undo restores the typed row; gates green;
verifier PASS within 3 rounds; one push.

Retires: typing pet tier / species / talents as a standing input.

Depends on: 111 (auto-apply gate), 043.
