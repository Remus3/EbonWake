# Audit 2026-10-17 - ops-ci-config (plan 152)

Slice: every tracked ops/ file outside ops/fleet_kit/ (only
`ops/loop/slots.py`; everything else under ops/ is gitignored runtime state),
.github/ (workflows, dependabot, issue and PR templates), config/local.example.json,
pytest.ini, ruff.toml, .gitignore, .gitattributes and the root files (README,
NOTICE, SECURITY, CONTRIBUTING, conftest.py) plus the ci/ requirement pins the
workflow installs. Method per `docs/plans/152-audit-ops-ci-config.md`: every
file read in full; each real finding fixed root-cause-first. All four tests in
`tests/test_repo_root_docs.py` were run red before their fix (4 failed), then
green after it.

Game ToS floor: no finding. No file in the slice touches the game process,
client files, packets or the authenticated market. The README and templates
state the floor correctly.

## Files read (in full)

| File | Lines | Findings |
|---|---|---|
| ops/loop/slots.py | 272 | OPS-CI-CONFIG-07, -08, -09, -10 (kit defects for MAIN) |
| .github/workflows/ci.yml | 51 | OPS-CI-CONFIG-05 (NOT-A-BUG) |
| .github/workflows/codeql.yml | 46 | OPS-CI-CONFIG-05 (NOT-A-BUG) |
| .github/dependabot.yml | 23 | none |
| .github/ISSUE_TEMPLATE/bug_report.yml | 52 | none |
| .github/ISSUE_TEMPLATE/config.yml | 1 | none |
| .github/ISSUE_TEMPLATE/feature_request.yml | 21 | none |
| .github/PULL_REQUEST_TEMPLATE.md | 29 | none |
| config/local.example.json | 51 | none (keys round-trip in tests/test_settings.py) |
| pytest.ini | 9 | none |
| ruff.toml | 7 | none |
| .gitignore | 49 | OPS-CI-CONFIG-04, -06 (NOT-A-BUG) |
| .gitattributes | 6 | none (no .bat/.cmd or untyped binaries tracked) |
| README.md | 205 | OPS-CI-CONFIG-01, -02, -03 |
| NOTICE | 14 | none |
| SECURITY.md | 70 | none |
| CONTRIBUTING.md | 68 | none |
| conftest.py | 4 | none |
| ci/requirements-ci.in | 2 | none |
| ci/requirements-ci.txt | 46 | none |
| ci/requirements-dev.in | 10 | none |
| ci/requirements-dev.txt | 69 | none |

## Findings

| ID | File:line | Sev | What was wrong | Test | Status |
|---|---|---|---|---|---|
| OPS-CI-CONFIG-01 | README.md:46,74-76,122-123 | M | Privacy and data-source text said the profile card sends the family name to "the public profile API" / reads "the public BDO-REST-API profile endpoint". Plan 061: the public host is robots-disallowed and never called; only a self-hosted `profile.base_url` instance is (server/ew/progress.py:28). A privacy statement naming the wrong recipient. | tests/test_repo_root_docs.py::test_readme_never_claims_the_public_profile_api_is_called | FIXED |
| OPS-CI-CONFIG-02 | README.md:94 | L | Said the market watchlist goes in config/local.json; there is no such key (it is runtime state set from the Market tab). | tests/test_repo_root_docs.py::test_readme_does_not_put_the_watchlist_in_local_json | FIXED |
| OPS-CI-CONFIG-03 | README.md:181-182 | L | Status still said the work loop's scheduled task read-back was pending; it is installed and read back (CLAUDE.md Loop item 1). | tests/test_repo_root_docs.py::test_readme_status_does_not_call_the_loop_unread | FIXED |
| OPS-CI-CONFIG-04 | .gitignore:37-43 | L | No ignore for an in-checkout virtualenv; CI deps (pytest, ruff) are commonly installed into `.venv/`, whose pyvenv.cfg carries an absolute machine path, so a broad `git add` would stage it (public repo). | tests/test_repo_root_docs.py::test_gitignore_covers_local_virtualenvs | FIXED |
| OPS-CI-CONFIG-05 | .github/workflows/ci.yml:6-10, codeql.yml:6-10 | L | Push `paths-ignore` skips CI for docs/Markdown-only pushes, so the CI leak sweep and ASCII test do not run on them. | - | NOT-A-BUG: deliberate CI-minute saving for hand-off pushes; the pre-commit / pre-push leak sweep and the loop's whole-suite gate (tests/test_ascii_lf.py) cover every such push locally, and pull requests have no paths-ignore. |
| OPS-CI-CONFIG-06 | .gitignore:15-29, ci.yml:8 | L | `ops/loop/control/*` makes the explicit control-file lines and the workflows' `ops/loop/control/**` paths-ignore redundant. | - | NOT-A-BUG: the explicit lines are kit-required and pinned by tests/test_fleet_kit_conformance.py::test_race_guard_paths_gitignored; redundancy is harmless. |
| OPS-CI-CONFIG-07 | ops/loop/slots.py:95-99,114,131,193 | M | `_read` returns any JSON value: a lock holding a list / number / string, a non-numeric `ts` or a null `pid` raises AttributeError / ValueError / TypeError out of `is_stale` -> `reap` -> `hold` (and `release` on `rec.update`), so a corrupt lock crashes the caller instead of being reclaimed fail-open as the docstring promises. | - | FILED (kit defect for MAIN): byte-pinned shared file. EW no longer holds it at runtime (ADR 0007), so no EW path is exposed. |
| OPS-CI-CONFIG-08 | ops/loop/slots.py:245-246 | L | `hold` stamps `ts` once before the wait loop, so time spent waiting for a slot counts toward the HARD_STALE ceiling; a holder that waited long can be reaped while alive. | - | FILED (kit defect for MAIN). |
| OPS-CI-CONFIG-09 | ops/loop/slots.py:110 | L | The unreadable-lock branch of `is_stale` uses `time.time()` and ignores the caller's `now`, so the function is not deterministic under an injected clock. | - | FILED (kit defect for MAIN). |
| OPS-CI-CONFIG-10 | ops/loop/slots.py:40 | L | Hardcoded `C:\ProgramData\...` default root (a machine path in a tracked file). | - | NOT-A-BUG here: already inventoried (docs/research/0014) and allowlisted (tools/leak_sweep.py STRUCT_ALLOW_FILES); the kit's fleet_lanes derives the same path from env ProgramData. Listed for MAIN with -07. |

## Kit defects for MAIN

`ops/loop/slots.py` is the shared byte-identical governor (SHA-pinned by
tests/test_fleet_kit_conformance.py::test_shared_slots_governor_is_byte_identical),
so it is not edited here:

1. OPS-CI-CONFIG-07 (M): make `_read` return `{}` for any non-dict JSON and
   coerce `ts` / `pid` defensively (bad value -> treat as unreadable, mtime
   fallback), so a corrupt lock is reclaimed rather than raising out of
   `reap` / `hold` / `release`.
2. OPS-CI-CONFIG-08 (L): stamp `ts` at acquisition (inside the loop, per
   `try_acquire` attempt), not before the wait.
3. OPS-CI-CONFIG-09 (L): use the `now` argument in the mtime branch.
4. OPS-CI-CONFIG-10 (L): derive the default root from env ProgramData, as
   fleet_lanes already does.
