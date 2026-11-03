# Plan 168 - Loop checklist overflow is counted, not silent

Status: built (lane, 2026-11-03). Source: ROADMAP row 168, the EW analogue of SS
FIX N44eed9 (a) (ROADMAP section for that FIX, item (a)).

## Problem

`tools/ew_loop.py` `Tick.checklist()` keeps at most the kit
`fleet_checklist.ROWS_MAX` (20) rows. Its `add()` dropped every row past the cap
with no count and no marker, so `ops/loop/control/progress/loop.json` read as a
complete remaining list when it was not.

## Built

1. `Tick.checklist()` counts each row past `ROWS_MAX` in `Tick.checklist_dropped`
   (reset to 0 on every call; initialised to 0 in `Tick.__init__`).
2. `Tick.write()` writes `"checklist_dropped": N` beside `"checklist"` in
   `progress/loop.json` on every tick (0 when everything fits).
3. Tests: `tests/test_loop_checklist_overflow_p168.py` - 25 rows keep the first 20
   and count 5 (direct `checklist()` call, no git), 3 rows count 0, and a tick
   with 25 open ROADMAP rows writes `checklist_dropped: 5` to loop.json (git).

Kit check: kit v28 `fleet_checklist.py` has no overflow form (it still slices
`remaining()[:ROWS_MAX]`), so EW's own count is used. When a kit version ships an
overflow marker or count, EW adopts it and this key is retired.

## As-built deviations

- D1 Key always present. Decision: write `checklist_dropped` on every tick, 0
  included. Alternatives: write it only when N > 0. Why: a reader (lane widget,
  status answer) can tell "nothing dropped" from "an older tick format" without a
  missing-key branch. Reverses if: a kit schema check refuses unknown or zero-value
  keys in loop.json.
- D2 JSON only, no rendered marker. Decision: `render_checklist` / the item-13 a
  block is unchanged. Alternatives: a `+N more` row or trailing sentence. Why:
  FLEET item 13 a reserves the one trailing sentence for ordering constraints and
  the render is the pinned kit's; the row asked for the count in loop.json.
  Reverses if: a kit version ships an overflow form for the render.
