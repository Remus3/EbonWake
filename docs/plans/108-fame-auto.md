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
