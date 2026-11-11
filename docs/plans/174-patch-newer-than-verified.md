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
