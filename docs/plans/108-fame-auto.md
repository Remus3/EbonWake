# Plan 108 - Fame bonus auto: OCR (and profile fame) derive market.fame_pct; only an explicitly typed value outranks a read

Status: open (priority). Operator order session 28 (zero-touch wave: remove
operator manual input everywhere possible). Lane hint: `build`.

Goal: `market.fame_pct` stops being a setting the operator keeps current.
It is DERIVED from the newest family fame read and shown with its source;
the Settings number input becomes an override that wins only when the
operator explicitly typed it after the newest read.

State today (read 2026-10-10): plan 081 already parses the market sell
dialog's "Family Fame bonus +1.250%" line (`server/ew/ocrinfer.py:384`
`fame_field`, region `fame` in `server/ew/data/ocr_regions.json`) and
`server/ew/app.py:542` `_fame_live` feeds it into the plan 079 resolver.
Gaps:
- A `config/local.json` `market.fame_pct` is imported by `sync_config` as a
  ledger entry with `set_at` = the file mtime, so a config value written
  after the newest screenshot silently beats the OCR read (`_fame_live`
  compares against any entry, typed or config).
- The read is lost when it ages out of the ocr_auto commit list
  (`MAX_COMMITS`, `latest("fame")`), and EW falls back to config / 0.
- No source without a sell-dialog screenshot; the BDO-REST-API profile
  refresh already stores `combat_fame` / `life_fame` per character
  (`server/ew/progress.py:364`) but nothing maps it to the bonus tier.
- One OCR misread (e.g. 0.25 for 1.25) drops every net figure; fame only
  rises.

Inputs (ToS floor): screenshots the operator took (plan 063 auto-OCR), the
public BDO-REST-API profile already fetched (plan 004 / 041), a tracked
tier table. No memory read, no client file, no input to the game.

## Slices

1. Persisted derived value: store domain `fame` {value, at, source:
   ocr|profile, file?} written by ocr_auto on a committed `fame` read (and
   by slice 3); `_fame_live` reads it, never the bounded commit list, so a
   read survives commit-list rotation and restarts.
2. Precedence: a live read beats a ledger entry whose `source` is `config`
   always, and a `typed` entry only when the read is newer. A config value
   never outranks a read (it stays the fallback when no read exists). A
   typed override newer than the newest read still wins (as today), badged
   with set_at (plan 079).
3. Profile tier fallback: tracked `server/ew/data/fame_tiers.json`
   (`verified: false`, source URL + read date) mapping family fame (sum of
   the profile fame fields, newest refresh) to the market bonus percent.
   Used only when no OCR read exists, source `profile`, badged "estimated
   from profile fame" until a plan 085 hint row verifies it. No invented
   tier data: if no public page sources the table, ship the loader + an
   empty table and record the gap as an as-built deviation.
4. Monotonic guard: a read LOWER than the current derived value is queued
   for review (`ocr_review`, why "fame went down") unless two reads from
   different screenshots agree; a higher or equal read commits.
5. Settings surface: the `market.fame_pct` row
   (`app/shared/core/settings.part.js:144`) becomes a read-only "Family
   fame bonus: 1.25 % (OCR, 2 d ago)" line with an "override" disclosure
   holding the number input; clearing the override returns to the derived
   value.

## Tests first

- `tests/test_fame_auto.py`: config value newer than an OCR read -> the
  read wins; typed value newer than the read -> typed wins; read newer than
  typed -> read wins and the typed entry retires with signal `ocr_fame`;
  the read survives MAX_COMMITS + 1 later commits and a restart; a lower
  read is queued, two agreeing lower reads commit; profile tier fallback
  only with no read, source `profile`; empty tier table -> no fallback.
- `app/test/settings.test.js` (or new `fame_auto.test.js`): the fame row
  renders derived value + source + age; the input sits behind the
  disclosure.

Acceptance: with a fixture config `market.fame_pct: 0.5` (mtime now) and an
older OCR read of 1.25, the market tax block shows 1.25 source ocr; gates
green; verifier PASS within 3 rounds; one push.

Retires: the typed `market.fame_pct` Settings field as a required input
(kept only as an explicit override).

Depends on: 081.

## As-built deviations

Self-adjudicated in the build lane (refute-rounds: 0/3 at hand-in).

1. Tier table ships empty. Decision: `server/ew/data/fame_tiers.json` has
   `tiers: []`, `source: null`, `read: null`, `verified: false`; the loader
   (`server/ew/fameauto.py`) and the fallback are wired and tested with an
   injected table. Alternatives: tiers from memory (forbidden by slice 3: no
   invented tier data); block the plan on a research lane. Why: the build run
   had no granted web read, so no public page sourced the table. Reverses if:
   a deep-dive or data lane reads a public page with the tiers - fill the rows,
   set source / read, and `verified` only after a plan 085 hint row agrees
   with a sell dialog read.
2. Profile estimate is computed at read time, not written to store domain
   `fame`, and it never retires a ledger entry (typed or config) - it only
   beats the default. Alternatives: persist it beside the OCR read; let it
   beat config like an OCR read does. Why: it is an unverified estimate from
   partial data (the public profile has combat + life fame, not the age fame
   part of family fame), so an operator-sourced value stays more trustworthy;
   computing it on read keeps the one persisted value an actual screenshot
   read. Reverses if: the tier table is verified and family fame is fully
   covered by the profile.
3. Family fame = combat_fame + life_fame of the main character row of the
   newest refresh (the fields are family-level and repeat on each character
   row), not a sum over characters.
4. The Settings line uses the shared plan 081 `derivedText` wording ("Family
   fame bonus: 1.25 % (from screenshot, 2d ago)") instead of "(OCR, 2 d ago)",
   so every derived input reads the same across cards.
5. `AutoOcr.fame_read()` also reads the plan 081 `ocr_reads` list (a newer
   row there wins), so a store written before plan 108 keeps its read without
   a migration.
6. The monotonic guard applies only to a read from a shot at least as new as
   the current read (an older shot reading lower is history, not a drop); a
   review accept / fix commits regardless (the operator's call), and the
   agreeing review item is removed when the second read commits.
7. `/api/settings` (GET and POST) carries `derived` {key: row}; the clear
   button posts the existing plan 079 `{clear: "market.fame_pct"}`.
