# Plan 123 - Warehouse storage and sold-items ledger from OCR

Status: open. Proposed by plan 120 (research 0021 section 2). Lane hint:
`build`.

Goal: the plan 045 inventory card's two remaining typed lists fill from
screenshots: the warehouse window (town name, slots used / total) sets the
per-town storage row, and the in-game Central Market sales list (sold items
and collected silver) logs sales into the Value Pack ledger.

State today (read 2026-10-10): `server/ew/inventory.py` `town_add / edit`
({name, used, total, note}) and `sale` ({price, vp}) are typed only; plan 081
already reads total weight / inventory slots (`weight`, `slots`).

Inputs (Game ToS floor): operator-saved screenshots of in-game windows read
by the plan 063 pipeline. The authenticated web market is never called (no
buy / sell / register, no login); nothing reaches the game.

## Slices

1. Title cues: `titles.warehouse`, `titles.market_sales` in
   `data/ocr_regions.json` (unverified).
2. Parser `ocrinfer.warehouse_fields(doc)` -> {kind: "storage", name: town,
   value: {used, total}}: the town from the panel title ("<Town> Storage" /
   "<Town> Warehouse") matched to a town list (new tracked
   `data/towns.json`, sourced, verified false); "120/192" pair, used <= total.
3. Parser `ocrinfer.market_sale_fields(doc)` -> [{kind: "sale", value:
   {price, item?}, conf}]: one row per sold line with a grouped silver amount
   (plan 063 silver confidence rules); a sale row is deduped by (price, item,
   shot day) so re-shooting the same list never logs twice.
4. Wiring: `storage` and `sale` join `ocrauto.KINDS` / `FIX_KINDS`;
   committed storage reads upsert the town row (`inventory.ocr_town`), sale
   reads append through `inventory.sale` with the live VP state; undo and
   `auto_applied` as plan 111; typed rows stay newer-wins.

## Tests first

- `tests/test_inventory_ocr.py`: warehouse title + pair read, unknown town
  queues, used > total no read, sale lines with grouped / ungrouped silver,
  dedup on a repeated shot, undo removes the logged sale.

## Acceptance

A fixture warehouse doc sets a town row and a fixture sales doc logs its
sales once (twice-read shot logs once) with the VP at log time; gates green;
verifier PASS within 3 rounds; one push.

Retires: typing per-town storage and the sales log.

Depends on: 111 (auto-apply gate), 081, 045.
