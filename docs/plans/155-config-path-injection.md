# Plan 155 - Server config readers honour the injected config_path

Status: built, pending merge (follow-on of the 20261017 hardening audit, session 36). Source:
TESTS-A-01, TESTS-A-15 (docs/audit/20261017-tests-a.md), TESTS-B-06 (docs/audit/20261017-tests-b.md). Lane hint: `build`.

## Problem

`config_market` / `config_market_watch` / `config_hash` (server/ew/app.py about lines 136-195) and EWServer's market / profile config read REPO_ROOT config instead of the injected `config_path`, so tests and alternate roots read the live config; `loopstatus.main_root` does not resolve a relative gitdir.

## Slices

1. Tests first: an EWServer / helper built with a tmp config_path reads market, watch, profile and hash values from that file only (live config/local.json untouched); main_root resolves a relative gitdir in a linked worktree fixture.
2. Fix: thread config_path through the readers (default unchanged = REPO_ROOT config); resolve relative gitdir against the .git file's directory.

## Acceptance

Each slice's test failed before the fix and passes after; ruff, touched tests
and (if app/ changed) npm test green; ASCII / LF; the audit doc row for each
source ID is updated to FIXED with this plan number.

Depends on: 150, 151.

## As-built

- `config_hash` / `config_market_watch` / `config_market` (server/ew/app.py)
  and `progress.config_profile` take `path=None`; a given path is read instead
  of `<root>/config/local.json`. EWServer passes its `config_path` to all four
  (None keeps the REPO_ROOT default). tests/ew_hermetic.py's `rooted` wrapper
  forwards `path=`.
- `loopstatus.main_root` resolves a relative gitdir against the worktree root
  (the .git file's directory) with `os.path.normpath`.
- Tests: tests/test_config_path_p155.py (3 of 4 red before the fix; the
  no-config_path case pins the unchanged default).

## As-built deviations

- Decision: a `path=` keyword on the existing readers instead of deriving a
  root from `config_path` (`config_path.parent.parent`). Alternatives: derive
  the root; new path-only readers. Why: an injected file need not sit at
  `<root>/config/local.json` (the new test uses `alt/settings.json`), and the
  keyword keeps every existing `root` caller unchanged. Reverses if: the
  config file is ever split so one path no longer holds all four sections.
- Decision: the hand overrides of `s.market.settings` in test_market_vp /
  test_planner_inputs / test_vp_auto (TESTS-B-06 workarounds) are left in
  place. Alternatives: drop them now. Why: they are harmless and out of this
  plan's slices; removing them widens the diff into three unrelated files.
  Reverses if: a later test-hygiene plan adopts them.
