# Plan 118 - Deadeye enhance state from OCR: enhancement window shot reads failstack, cron count and Agris pity

Status: open. Operator order session 28 (zero-touch wave 2). Lane hint:
`build`.

Goal: a screenshot of the enhancement window sets the character's current
failstack, the crons on hand and the Agris pity stacks of the item being
enhanced, so the plan 036 Stacks card and the plan 035 EV calc run without
typing. Typed entry stays as an optional override.

State today (read 2026-10-10):
- `server/ew/deadeye.py` keeps `fs_bank` (stored stacks), `agris` (rows
  `{family, step, stacks}`) and `crons` (`{owned, weekly_income}`), all
  operator-typed through `fs_add` / `fs_use` / `agris_set` / `crons_set`.
- `server/ew/enhance.py` `EnhanceService.query` takes `fs` from the query
  string (default 0); the dashboard EV form types it.
- Plan 111 / 115 give the pattern: an `ocrinfer` parser yields fields, the
  `ocrauto.AutoOcr` gate (`AUTO_COMMIT_MIN`) commits at or above it with an
  undo id, holds and low reads go to the review queue.

Inputs (ToS floor): operator screenshots + their OCR text (plan 063), the
tracked plan 035 rate table (families, steps, Agris thresholds), the plan
007 enhancement plan. Nothing reaches the game: no memory, no input, no
client files.

## Slices

1. Parser `ocrinfer.enhance_fields(doc, keys, fallback=None)` -> fields
   for one enhancement-window shot (a line naming "Enhance" /
   "Enhancement" anchors it; no anchor, no fields):
   - `enh_fs` {name "fs", value 0..999}: "Failstack: 45", "Failstacks +45",
     "Enhancement Chance Increase +45", "FS 45".
   - `enh_crons` {name "crons", value 0..10^9}: a "Cron Stone(s)" line
     (fold + edit distance <= 2) with "Owned: 1,234", "x 1,234", "120 /
     1,234" (needed / owned -> owned), or the amount on the line beside /
     below it (plan 115 neighbour rule); a cost line without an owned label
     is skipped.
   - `enh_agris` {name "<family> <step>", value {family, step, stacks}}:
     an "Agris" line with "3 / 20" (stacks / threshold) or "Stacks: 3"; the
     key comes from the item line ("+15 Sovereign Longbow", "TET: Kharazad
     Ring": family by the plan 035 guess, step = the first level above the
     current one with a rate row) or, with no item line, from the `fallback`
     (the plan 036 advice's next step) at conf x 0.9.
   conf = label / name ratio x amount sanity (plan 115 digit-group
   constants); two different values for one kind on one shot -> conf 0.5;
   an Agris "/ N" threshold that disagrees with the table -> conf 0.5.
2. Kind wiring: `enh_fs`, `enh_crons`, `enh_agris` in `ocrauto.KINDS`, all
   three in FIX_KINDS (an Agris fix is the stacks count); commit ->
   `DeadeyeService.ocr_set(kind, value, source="ocr:<file>", at=shot_at,
   uid)`, undo -> `DeadeyeService.ocr_restore`.
3. Deadeye store: `reads` {fs_now, crons, agris: {"family|step": ...}}
   (each `{id, value, at, set_at, source}`) and `typed_at` {crons, agris:
   {...}}. A read sets `crons.owned` / the Agris row / the current FS;
   newest wins: a read older than the stored read or than the last typed
   value of that slot is skipped (`ocr_check` -> skip), a typed
   `crons_set owned` / `agris_set` stamps `typed_at`. An Agris read above
   the table threshold is held for review.
4. EV calc: `EnhanceService(fs_now=...)`; `GET /api/deadeye/enhance`
   without `fs` uses the current FS read (`fs_source: "ocr"`), else 0
   (`fs_source: "default"`); a typed `fs` wins (`fs_source: "query"`).
5. Surface: the Stacks card shows "failstack now +45 (OCR)", crons owned
   "(OCR)" and Agris rows "(OCR)"; the OCR card labels the three kinds;
   the EV form's FS placeholder is the current FS read.

## Tests first

- `tests/test_enhance_ocr.py`: anchor required; each FS shape; cron
  owned / x / needed-over-owned / line-below shapes; cost line skipped;
  Agris with item line, with fallback (conf x 0.9), threshold mismatch
  conf 0.5; two FS values conf 0.5; commit sets FS / crons / Agris and
  undo restores; an older shot skipped; a newer typed value wins over an
  older read; an Agris read above threshold held; the EV query without
  `fs` uses the read; review fix of an Agris read sets the stacks.
- `app/test/enhance_ocr.test.js`: OCR kind labels / fix bodies and the
  Stacks "(OCR)" labels.

Acceptance: a fixture enhancement-window OCR doc sets FS 45, crons 1,234
and Sovereign TET pity 3 with undo; the EV query without `fs` evaluates at
45; gates green; verifier PASS within 3 rounds; one push.

Retires: typing the current failstack into the EV form, the crons owned
and the Agris pity stacks after every enhancement session.

Depends on: 111 (auto-apply gate), 036, 035.

## As-built deviations (build lane, 2026-10-10)

Each self-adjudicated (decision / alternatives / why / reverses if).

1. Current FS, not the bank. Decision: the failstack read lands in
   `reads.fs_now` (shown as "failstack now +N (OCR)" and used as the EV
   default), never as a `fs_bank` row. Alternatives: add the read as a
   bank row. Why: the enhancement window shows the stack on the character,
   while the bank holds stored stacks (Advice / saved / Valks' Cry) that the
   window does not list; a bank row per shot would double-count. Reverses
   if: a verified window layout shows stored stacks too.
2. Gate. Decision: the plan 063 commit gate (`AUTO_COMMIT_MIN`, 0.9) with
   an undo id per commit, no `auto_applied` log row. Alternatives: the plan
   111 AUTO_APPLY_MIN (0.95) plus a log row. Why: these are plain field reads
   like silver / currency (plan 115 uses the same gate); plan 111's log
   covers suggestions that used to be review-only. Reverses if: a wrong
   enhancement read is committed in use.
3. Layout unverified. Decision: line shapes are the plan list (failstack /
   chance-increase label, cron owned / x / needed-over-owned, Agris "n / T"
   or "Stacks: n") behind an "Enhance(ment)" anchor; no fixed regions.
   Alternatives: `ocr_regions.json` crops. Why: no verified window
   screenshot in the tree; the anchor keeps tooltip / inventory text out.
   Reverses if: a verified layout gives fixed regions.
4. Plural cron name. Decision: both "cron stone" and "cron stones" are
   matched names (edit distance from the closer one). Why: the window prints
   the plural; distance 1 from the singular pushed an exact read under the
   gate.
5. EV default. Decision: `fs_now` never expires; the reply carries
   `fs_source` and the dashboard prefills the EV form's FS (value, not
   placeholder) with it. Alternatives: expire after N hours; placeholder
   only. Why: the FS only changes when the operator enhances, which is when
   they take the shot; a typed FS still wins. Reverses if: stale reads
   mislead in use.
6. Progress file. The lane run's permissions denied the write of
   `progress/p118-build.json` outside the worktree (same as plan 111
   deviation 9), so the v7 checklist was not written. Reverses if: the lane
   grants the kit `write_progress` call.
7. Tests. The JS test lives in `app/test/enhance_ocr.test.js`; it checks
   the kinds through `normalizeOcrAuto` (OCR_AUTO_KINDS is not exported and
   the export surface is pinned). Fixtures use the table's Sovereign TET
   threshold (20).

refute-rounds: 0/3
