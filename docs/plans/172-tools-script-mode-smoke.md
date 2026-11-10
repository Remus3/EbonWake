# Plan 172 - tools script-mode smoke test

Status: proposed. Source: research 0046, ROADMAP row 171.

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
