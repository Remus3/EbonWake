# Plan 172 - tools script-mode smoke test

Status: built (lane, 2026-11-10); also closes row 171. Source: research 0046, ROADMAP row 171.

## Problem

`python tools/lane_samples.py status` crashed on a circular import that only
exists when the file runs as `__main__`; tests import modules, so nothing
caught it. Other tools/*.py entry points may hide the same class of defect.

## Scope

1. A test enumerates tools/*.py files that define `if __name__ == "__main__"`
   and runs each as `python tools/<x>.py --help` (or its documented read-only
   status verb) in a subprocess with a tmp_path runtime root.
2. Pass = rc 0 or the tool's documented usage rc, and no `ImportError` /
   `Traceback` in stderr. A small allow-list names tools that need live state.
3. Fix each failure found at the root (import order), not by catching it.

## Tests

Failing test first: it fails on lane_samples.py until row 171 lands.
Marked `@pytest.mark.git` or `server` only if a case needs it; otherwise fast
tier.

## Depends-on

171

## As-built deviations

- Numbering: the task said to number from 171; row 171 exists, so 172.
  Alternative: renumber row 171 (rejected, it is filed and cited). Reverses
  if: never needed.
- Row 171 fixed here (scope item 3), not left for a separate lane: the cycle
  was lane_samples (__main__) -> loop_base -> ew_lane -> lane_samples (second
  copy) -> `from loop_base import _NO_WINDOW` on a half-built loop_base.
  Root fix: tools/ew_lane.py imports lane_samples at call time inside
  run_lane (what lane_samples.sample_dir's comment already assumed), no
  top-level import. Alternatives: defer loop_base in lane_samples (rejected:
  six names, every call site changes); catch ImportError (rejected by scope 3).
  Why: one-line move breaks the cycle for every import order; monkeypatched
  tests patch the module object, which the call-time import returns. Reverses
  if: ew_lane needs lane_samples at import time (then split the shared
  helpers out of loop_base instead).
- Two checks per entry point (tests/test_tools_script_mode.py): (1) the
  file's top level exec'd as __main__ up to its main guard (exact script-mode
  import order, zero side effects) for ALL entry points; (2) a real `--help`
  (or `lane_samples.py status`, the row 171 acceptance) for the rest. Runs
  against a tmp_path copy of tools/, server/ and ops/fleet_kit/ (the plan's
  "tmp_path runtime root": EW resolves roots from the file path, not env).
  Alternative: --help only (rejected: install_hooks, launch,
  verify_action_pins and ew_facts act on any argv - git config, process
  launch, network, live state - so they would be allow-listed out and their
  imports never checked). Reverses if: never needed.
- Documented usage rc table: eta 64, loop_task / logon_task 2,
  profile_selfhost 2 (prints help, returns 2); all others 0.
- Progress JSON (ops/loop/control/progress/p172-build.json) not written: the
  lane's permissions denied the write outside the worktree and any script run
  that would call fleet_headless.write_progress. Reverses if: the lane allow
  list grants the kit progress writer.
