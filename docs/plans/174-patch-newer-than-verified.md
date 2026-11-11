# Plan 174 - Patch newer than verified: flag data rows when a newer official patch exists

Status: proposed. Source: research 0047.

## Problem

Patches land weekly (2026-10-22, 10-29, 11-05). Data rows are verified
against one patch (plan 085) and nothing says a newer one has shipped, so a
changed number can sit unnoticed.

## Scope

1. Read the official patch-notes list already fetched by plan 064 (no new
   fetch path, robots gate unchanged); take the newest NA patch date.
2. Compare with the verifier's last-verified patch date (plan 085 output).
3. If newer, the signal digest (plan 073) shows one line "data verified
   against <date>, patch <date> is newer" with a fix hint to rerun the
   verifier. Suggest-only; no auto-edit of data.
4. Clears when the verifier records the newer date.

## Tests

Failing test first: fixture patch list newer than verified date -> flag;
equal -> none; missing verifier state -> quiet (no flag).

## Depends-on

None

## As-built deviations (build lane, self-adjudicated 2026-11-11)

Built: `dataverdicts.newest_patch()` / `newer()` (pure), `VerdictService(listed=)`
-> `signal()["newer"]`, `NoticeClient.listed()` (cleaned rows of the cached
list, no fetch), `signals` data reason `patch_newer`, hint
`data.patch_newer`. Tests: `tests/test_patch_newer.py`.

1. "Newest NA patch date" = the newest dated `Patch Notes` title on plan
   064's cached notice list (every board, `patchverify.note_date`: title date,
   else list stamp; undated titles skipped). "Last-verified date" = the
   verifier's `last_notice.date` (newest patch-notes page whose text it
   checked). Alternatives: the newest `confirmed` verdict date (would flag
   forever when a patch is silent on every hinted row). Why: plan 085 checks
   every hinted row against each cached page, so the last checked page is the
   verified-against patch. Reverses if: verdicts become per-row partial.
2. Level `warn` (reason `patch_newer`), detail = the one line; contradicted
   and error rows win, and a contradicted row carries the newer line as its
   last evidence line. Alternatives: `ok` with a line (no hint: hints are per
   reason). Why: the fix hint needs a reason; Home's pill fires only on `bad`,
   so a weekly transient warn stays quiet. Reverses if: the warn proves noisy
   between patch day and the next notice fetch.
3. "Rerun the verifier" hint points to Events (a notice refresh reads the
   newest patch notes first, plan 085 fetch order; verdicts recompute on
   read). No new endpoint. Reverses if: a manual verifier button lands.
