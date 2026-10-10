# Plan 126 - Stored failstack bank and enhance step completion from OCR

Status: open. Proposed by plan 120 (research 0021 section 2). Lane hint:
`build`.

Goal: close the two typed gaps plan 118 left in the Deadeye card: (a) the
stored failstack list (Advice of Valks / saved stacks shown in the
enhancement window's stored list) fills `fs_bank`; (b) an item tooltip or an
enhancement-success shot naming the item at its new grade ("PEN: <item>",
"TET <item>", "+15 <item>") marks the matching open enhancement step done.

State today (read 2026-10-10): plan 118 reads the current failstack, crons
owned and Agris pity (`enh_fs`, `enh_crons`, `enh_agris`); `fs_add` (bank
rows {kind, value, count}) and `step_done` ({id, done}) stay typed.

Inputs (Game ToS floor): operator-saved screenshots through the plan 063
pipeline. Read only; nothing is clicked, enhanced or sent to the game.

## Slices

1. Parser `ocrinfer.fs_bank_fields(doc)` -> [{kind: "enh_bank", value:
   {kind: advice|saved, value, count}}]: "Advice of Valks (+N)" lines with a
   count, "Stored +N" rows; N in the plan 036 bounds.
2. Bank set: committed reads replace the bank rows of the kinds the shot
   shows (`deadeye.ocr_bank`, undo `ocr_restore`); typed rows newer-wins.
3. Parser `ocrinfer.gear_grade_fields(doc)` -> {kind: "enh_grade", name:
   item, value: level}: grade prefix (+1..+15 / PRI..PEN per
   `deadeye.LEVELS`) followed by an item name; a match against an open step's
   item text (normalized) at or above its target level marks it done
   (`step_done`, by: auto); never marks a step undone.
4. Gate, review, undo and `auto_applied` as plan 111.

## Tests first

- `tests/test_deadeye_bank_ocr.py`: bank lines, bounds, replace by kind, undo;
  grade prefixes per family, step match at / above target, below target
  ignored, no step undone, ambiguous item queues.

## Acceptance

A fixture stored-list doc sets the bank rows and a fixture tooltip doc
"TET Blackstar Longbow" marks the TET step done with an Undo; gates green;
verifier PASS within 3 rounds; one push.

Retires: typing the failstack bank and ticking enhancement steps by hand.

Depends on: 118 (enhance window reads), 111, 036.
