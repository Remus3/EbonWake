# Plan 122 - Horse information OCR fills mounts and T10 breed materials

Status: open. Proposed by plan 120 (research 0021 section 2). Lane hint:
`build`.

Goal: the plan 044 mounts card fills from screenshots the operator takes at
the stable: the horse information window (kind, tier, level, gender, learned
skills) and an item count of the T10 breed materials. The Royal Fern Root
rate becomes derived from count reads over time instead of a typed average.

State today (read 2026-10-10): `server/ew/mounts.py` rows (`MOUNT_FIELDS`:
name, kind, tier, level, gender, skills), `materials` counts and `fern_rate`
are all typed through `POST /api/mounts`; `data/mounts.json` holds the T10
material keys and the pity rule. `failures` has no in-game source and stays
typed (research 0021 section 3).

Inputs (Game ToS floor): operator-saved screenshots read by the plan 063
pipeline, `data/mounts.json`, the operator's typed values. Nothing reaches
the game.

## Slices

1. Title cue: `data/ocr_regions.json` `titles.horse_info` (unverified).
2. Parser `ocrinfer.mount_fields(doc)` -> [{kind: "mount", name, value:
   {kind, tier, level, gender, skills}, conf, why}]: "Tier 8", "Lv. 30" (1..30),
   "Male" / "Female", skill lines matched against a skill-name list in
   `data/mounts.json` (new `skills` array, sourced, verified false).
3. Materials: a read naming a T10 material key with a count ("Royal Fern Root
   x 37", plan 113 catalog / loot reader) -> kind `mount_mat`; committed reads
   set `materials` through `mounts.ocr_set` (undo `ocr_restore`).
4. Fern rate: `mounts.fern_rate_derived` = positive count delta / days between
   the two newest reads at least 1 day apart (null otherwise); a typed
   `fern_rate` stays a newer-wins override.
5. Gate, review, undo and `auto_applied` as plan 111; rows matched by
   (kind, name); a new name with tier and level makes a new row.

## Tests first

- `tests/test_mounts_ocr.py`: synthetic docs: info window read, level bounds,
  unknown skill dropped, material count read, derived rate over 2 / 3 reads,
  same-day reads give no rate, typed rate newer wins, undo.

## Acceptance

Fixture horse info doc + two material reads 3 days apart fill a mount row and
the days-to-go counter from the derived rate; gates green; verifier PASS
within 3 rounds; one push.

Retires: typing mount stats, breed material counts and the fern rate.

Depends on: 111 (auto-apply gate), 113 (catalog reader), 044.
