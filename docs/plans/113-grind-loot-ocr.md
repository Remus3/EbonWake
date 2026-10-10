# Plan 113 - Grind loot OCR kind: loot-window shot -> item names via itemnames -> counts priced by arsha, applied to the auto session

Status: open. Operator order session 28 (zero-touch wave). Lane hint:
`build`.

Goal: loot counts read from a loot / acquisition window screenshot value
the auto grind session without the operator picking items or typing counts,
for any marketable item, not only the spot's tracked loot table.

State today (read 2026-10-10): `server/ew/ocrauto.py:574` `_loot_read`
calls `ocr.extract_loot(lines, t["names"])` with the RUNNING session's spot
loot-table names only (`grind.loot_target`), stores `ocr_loot`, and
`loot_prefill` offers the counts as a prefill the operator confirms on
Stop. Items off the spot table (event drops, new patch loot) are dropped as
`unmatched`; an auto session closed by `auto_stop` never applies the
prefill.

Inputs (ToS floor): operator screenshots + OCR, the plan 028 item-name
index (`server/ew/itemnames.py`: tracked seed + cached arsha names + arsha
`/util/db` GET), arsha v2 `na` market prices (read-only GET, plan 002
cache). No authenticated market call.

## Slices

1. Name pool: `extract_loot` second pass over `unmatched` lines against
   `ItemNames.entries()` (exact fold first, then edit distance <= 2 for
   names >= 8 chars); a catalog hit is a row with `id`, `marketable: true`,
   `source: "catalog"` and conf scaled down (CATALOG_CONF_SCALE, e.g. 0.9).
2. New OCR kind `loot` in `ocrauto.KINDS` (accept / fix / discard): rows
   under the gate go to review like other kinds; rows at or above it update
   `ocr_loot`.
3. Apply on auto close: `auto_stop` (and plan 112 `auto_fill`) applies the
   `ocr_loot` counts as the session's `loot` (plan 039 `loot_value`, VP /
   fame from `tax()`), pricing catalog items from the plan 002 cache (no
   fetch in the close path; missing price -> `unknown`, valued later by the
   next refresh). `valued_silver` = loot value when present, else the plan
   112 silver delta.
4. Surface: Grind tab row "Loot (OCR): 12 items, 38.2M" with the list in a
   details row and per-row source (table / catalog).

## Tests first

- `tests/test_grind_loot_ocr.py`: a loot line off the spot table matched
  via a fixture catalog; distance-2 match on a long name, none on a short
  one; catalog rows carry id + lowered conf; auto close applies loot and
  values it from a fixture price cache with VP / fame; missing price ->
  unknown; a newer shot replaces the running total (existing rule).
- `tests/test_ocr.py`: `extract_loot` second-pass cases.
- `app/test/grind_loot.test.js`: the Loot (OCR) row text.

Acceptance: a fixture loot-window OCR doc with 2 table items + 1 catalog
item closes the auto session with 3 loot rows and the hand-computed value;
gates green; verifier PASS within 3 rounds; one push.

Retires: the loot prefill confirm on Stop and typed loot counts for auto
sessions.

Depends on: 112.
