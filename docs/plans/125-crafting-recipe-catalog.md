# Plan 125 - Crafting recipe catalog data file: pick a recipe, do not type it

Status: open. Proposed by plan 120 (research 0021 section 2). Lane hint:
`data`.

Goal: the plan 054 cooking / alchemy calculator stops needing every input,
output and proc line typed. A tracked, sourced `data/recipes.json` lists the
common recipes (Imperial box contents first, then the operator's frequent
crafts); the dashboard offers "add from catalog", which writes an ordinary
recipe row the operator can still edit.

State today (read 2026-10-10): `server/ew/crafting.py` recipes
(`RECIPE_KEYS`: name, kind, inputs, outputs, procs) are typed only; prices
already come from the plan 002 market cache.

Inputs (Game ToS floor): public recipe pages read once by hand or by a
read-only GET with robots.txt checked first, cited in the file (`source`,
`read`, `verified: false` per row until checked against the in-game recipe
book). No client data files; nothing reaches the game.

## Slices

1. Source ruling: pick the citable source (official wiki or a public guide);
   read its robots.txt and record the ruling in this doc. No scraping where
   disallowed; then rows are written by hand from the page.
2. `server/ew/data/recipes.json`: {id, name, kind, inputs [{id?, name, qty}],
   outputs [{id, name, qty_avg}], procs, source, verified}; market ids from
   the existing item catalog; validated by a schema test.
3. `crafting.catalog()` + `GET /api/crafting?catalog=1`; `POST
   /api/crafting {from_catalog: id}` copies the row into the operator's
   recipes (then normal edit / delete).
4. Dashboard: "Add from catalog" picker on the Crafting card (app/shared
   crafting module, node --test).

## Tests first

- `tests/test_crafting_catalog.py`: data schema (ids unique, kinds, qty
  bounds, every input / output id in the item catalog or name-only), copy
  from catalog yields an editable recipe priced like a typed one, unknown id
  400, a broken data file degrades the picker only.
- `app/test`: picker list and POST body.

## Acceptance

A catalog recipe added from the picker prices identically to the same recipe
typed by hand; gates green; verifier PASS within 3 rounds; one push.

Retires: typing recipe lines for catalog recipes.

Depends on: 054.
