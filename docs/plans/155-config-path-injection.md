# Plan 155 - Server config readers honour the injected config_path

Status: open (follow-on of the 20261017 hardening audit, session 36). Source:
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
