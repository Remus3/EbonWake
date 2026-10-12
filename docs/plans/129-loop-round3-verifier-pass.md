# Plan 129 - Loop round-3 verifier pass and per-round findings

Status: open. Source: adjudicator ruling on DD-20261012 (2026-10-12). Lane
hint: `build`.

Problem: in `tools/ew_loop.py` (review loop, ~630-680) a deep-dive item whose
round-3 fix left the gates and `extra_checks` (~764-781) clean is marked
`adjudicate` without any verifier review, because the verifier spawn is
guarded by `rounds < MAX_ROUNDS`. DD-20261012 reached 3/3 on automatic
extra_checks findings alone, and the session adjudicator had to reconstruct
what each round found because findings are not kept on the loop item.

## Slices

1. Round-3 verifier pass: when `rounds == MAX_ROUNDS` and the gates plus
   `extra_checks` are clean, spawn exactly one verifier (same prompt / route
   as earlier rounds). PASS -> verdict PASS and merge as usual; anything else
   -> verdict `adjudicate`, WIP unmerged. Never a fix round 4 (CLAUDE.md
   rule 7): the pass is review only, no producer answer follows.
2. Per-round findings: append `{"round", "source": gates|extra_checks|
   verifier, "findings": [...]}` (ASCII, each capped) to a `round_log` list on
   the loop item JSON, so an adjudicator reads what each round found.
3. Tests (tests/test_ew_loop.py): round-3 clean -> one verifier spawn; PASS
   merges; non-PASS -> adjudicate; round-3 with findings -> adjudicate with no
   spawn; round_log written per round.

## Done when

Targeted tests green, whole suite green, a deep-dive item that ends round 3
clean is verified once instead of parked.
