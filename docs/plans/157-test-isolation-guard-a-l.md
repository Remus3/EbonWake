# Plan 157 - Extend the test-isolation guard to tests/test_[a-l]*.py

Status: open (follow-on of the 20261017 hardening audit, session 36). Source:
TESTS-B-07 (docs/audit/20261017-tests-b.md). Lane hint: `build`.

## Problem

Plan 151 added a guard that fails a test touching live repo state; it covers tests/test_[m-z]*.py only.

## Slices

1. Extend the guard's scope to every tests/test_*.py file; run it, and fix each a-l fixture it flags (tmp_path roots, no writes under the repo).
2. Keep the guard fast (no extra whole-suite run); record the extension in docs/audit/20261017-tests-b.md.

## Acceptance

Each slice's test failed before the fix and passes after; ruff, touched tests
and (if app/ changed) npm test green; ASCII / LF; the audit doc row for each
source ID is updated to FIXED with this plan number.

Depends on: 151, 156.

## As-built deviations

1. Decision: widen `SLICE` in the existing tests/test_tests_b_hygiene_p151.py
   instead of adding a second guard file. Alternatives: a new p157 file
   importing the p151 helpers (two guards over overlapping files, a
   test-module import plan 156 removed). Why: one guard, one scan, no double
   AST pass. Reverses if: the guard must differ per slice.
2. Decision: exempt, by explicit (file, function) name in `FALLBACK_TESTS`,
   the 3 make_server calls whose subject is the default fallback
   (test_hermetic_p150 `test_server_defaults_are_isolated`, test_config_path_p155
   `test_server_reads_only_the_injected_config_path` /
   `test_server_without_config_path_keeps_the_default_file`). They run under
   the plan 150 hermetic host, so the fallback reaches a tmp copy.
   Alternatives: give them the isolation kwargs (destroys what they test); a
   per-file allowlist (too coarse). Why: precise and self-checking
   (`test_fallback_exemptions_name_real_functions` fails on a stale name).
   Reverses if: plan 150's hermetic host fixture is removed.
3. Decision: add `ew_testkit.offline_market(tmp_path)` and use it in the 10
   a-l files with no local `_no_network` / market import. Alternatives: copy
   the `_no_network` + ArshaClient block into each. Why: plan 156 made
   ew_testkit the shared-helper home. Reverses if: never (test-only helper).
4. Slice 1 red state: the widened guard failed on 24 files (B-01); B-02 was
   already clean outside [m-z], so no B-02 fix was needed.
