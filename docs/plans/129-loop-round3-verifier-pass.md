# Plan 129 - Loop round-3 verifier pass and per-round findings

Status: done 2026-10-12 (loop merge 55569e5; refute 0/3 PASS). Source: adjudicator ruling on DD-20261012 (2026-10-12). Lane
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

## As-built deviations

1. Round label and a `final` key. Decision: the post-fix-3 pass is labelled
   refute round 3/3 (prompt and `round_log`), and its `round_log` entries
   carry `"final": true`. Alternatives: label it round 4 (reads as a round 4,
   which rule 7 forbids); no extra key (two round-3 verifier entries would be
   indistinguishable). Why: an adjudicator sees which entry was the
   review-only pass. Reverses if: rule 7 counts the pass as its own round.
2. What is logged. Decision: `gates` and `extra_checks` entries only when they
   found something; a `verifier` entry for every verdict (PASS logs
   `findings: []`), and a crashed verifier logs its rc line. Each finding is
   ASCII, its last 2000 chars kept (`ROUND_LOG_CAP`), at most 10 per entry.
   Alternatives: log clean gates too (noise; the gate cache already records
   them); keep the head of a finding (a verifier's verdict and numbered
   findings end its reply). Why: every round leaves at least one entry with
   what it found. Reverses if: an adjudicator needs clean-gate entries.
3. A crashed final-pass verifier is retried next tick under the existing
   `verify_errors` cap (3, counted over the item), not treated as non-PASS.
   Alternatives: adjudicate on the first crash. Why: a crash is no verdict,
   same as earlier rounds. Reverses if: crashes of the final pass are seen to
   loop.
4. `test_refute_rounds_cap_at_three_then_adjudicate_unmerged` now expects 4
   verifier spawns (3 rounds + the round-3 pass) and still 3 fix spawns.

## Done when

Targeted tests green, whole suite green, a deep-dive item that ends round 3
clean is verified once instead of parked.
