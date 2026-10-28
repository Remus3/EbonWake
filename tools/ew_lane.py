#!/usr/bin/env python3
"""EW laned headless driver (operator standing order 10, fleet kit v8).

    ew_lane.py status
    ew_lane.py run <lane> --prompt-file F [--writes-code] [--timeout S] [--dry-run]

Roster lanes: build, data, review. Up to lane_cap() run at once (kit v25:
the live machine config `fleet_lanes.load_config()`, default 3). Each run goes
through the kit's `fleet_lanes.run_lane` (repo lane lock + its OWN clean git
worktree `<repo parent>/ew-worktrees/lane-<i>`, detached at main's HEAD) and
spawns through `fleet_headless.spawn` ONLY (account B proxy, fail closed - FLEET
item 10) with exactly ONE governor slot taken AT the call (`governor="queued"`).
No slot is held around git. Every run writes a progress file (FLEET item 12)
and records its duration in the ETA log (`tools/eta.py`).

Lanes never commit. After a code run the main session commits in the printed
worktree (detached HEAD) and merges that commit into main with --no-ff. A lane
worktree left dirty is refused by the kit on the next claim (never cleaned), so
commit or hand-resolve it first. Gitignored config the gates need
(config/leak_needles.json, config/local.json) is copied into the worktree when
missing. The prompt file is read, never echoed to chat.
"""

import argparse
import importlib.util
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANES = ("build", "data", "review")
CODE = "EW"
SEED_CONFIG = ("config/leak_needles.json", "config/local.json")
# Headless -p has no prompt to approve edits; code lanes run in acceptEdits so
# file edits land in the lane worktree. Bash stays on the project allow list
# plus the gate commands below; commits and merges are done by the main session.
GATE_TOOLS = ("Bash(python -m pytest:*),Bash(npm test:*),Bash(node --test:*),"
              "Bash(python tools/leak_sweep.py:*),Bash(python -m ruff:*),"
              "Bash(python tools/ocr_bench.py:*),Bash(python tools/ew_tests.py:*)")
# Plan 163: a dependency-bump / alert-closing item needs npm, the Dependabot
# alert reads and git add of a regenerated lockfile (N82830d failed 3/3 on
# denials). gh is read-only by prompt (GETs); {owner}/{repo} are gh placeholders.
DEP_TOOLS = ("Bash(npm install:*),Bash(npm ci:*),Bash(npm ls:*),Bash(npm view:*),"
             "Bash(npm outdated:*),Bash(npm audit:*),"
             "Bash(git add:*),Bash(git status:*),Bash(git diff:*),"
             "Bash(gh api repos/{owner}/{repo}/dependabot/alerts:*),"
             "Bash(gh pr view:*),Bash(gh pr list:*)")
CODE_EXTRA = ("--permission-mode", "acceptEdits", "--allowedTools",
              GATE_TOOLS + "," + DEP_TOOLS)
sys.path.insert(0, str(ROOT / "tools"))
import eta  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


def kit():
    return _load("fleet_headless", "ops/fleet_kit/fleet_headless.py")


def lanes():
    return _load("fleet_lanes", "ops/fleet_kit/fleet_lanes.py")


def lane_cap():
    """Kit v25 LANE-CAP: the live per-tree lane cap, the machine config's
    lane_cap_max clamped to its governor_width (no config: 3). Re-read on
    every call; EW keeps no hard-coded cap (ADR 0007: no reason for less)."""
    return lanes().lane_cap(None)


def slot_count():
    """Kit v25: the machine-wide governor slot count EW's spawns queue for
    (live governor_width; no config: 3). spawn(governor="queued") takes its
    slot with cap=None, so EW borrows idle slots up to lane_cap()."""
    return int(lanes().load_config()["governor_width"])


def should_yield():
    """Kit v25 FAIR RELEASE, read only: True = do not start the next lane
    cycle (another tree waits, no slot free, EW above its fair share). The
    caller only declines to start work; it never stops a running worker.
    An unreadable governor reads False (the kit's own slot wait still bounds)."""
    try:
        return bool(lanes().should_yield(CODE))
    except Exception:  # noqa: BLE001 - advisory only
        return False


def check_lane(lane):
    if lane not in LANES:
        raise SystemExit(f"unknown lane {lane!r}; lanes: {', '.join(LANES)}")
    return lane


def seed_config(worktree, root=ROOT):
    """Copy gitignored gate config into a lane worktree when missing. Idempotent."""
    copied = []
    for rel in SEED_CONFIG:
        src, dst = Path(root) / rel, Path(worktree) / rel
        if src.is_file() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            copied.append(rel)
    return copied


def progress_task(index):
    """FLEET item 13 d: a lane's progress file is progress/lane-<i>.json, i = its
    lane-lock index (kit `fleet_checklist.lane_task`), so the widget reads one
    named file per live lane. The lane name rides in the step text."""
    return _load("fleet_checklist", "ops/fleet_kit/fleet_checklist.py").lane_task(index)


def run_lane(lane, prompt, writes_code=False, timeout=3600, dry_run=False, root=ROOT,
             spawn=None, lane_ctx=None, progress=None, record=eta.record,
             clock=time.time, model=None, effort=None, eta_kind=None):
    """One headless run on one lane. Returns the kit usage line plus "worktree".
    Progress goes to the MAIN checkout's progress/lane-<i>.json once the lane
    index is claimed; a dry run or a refused claim has no index and writes none.
    model / effort (plan 099 routing) reach the kit spawn only when given; a
    by-hand run without them keeps the kit default (pick_model / pick_effort).
    eta_kind (the loop item kind, e.g. item-plan) sets the progress ETA and is
    recorded beside the lane kind, so mixed item sizes on one lane stop skewing
    each other's estimate."""
    check_lane(lane)
    route = {k: v for k, v in (("model", model), ("effort", effort)) if v is not None}
    run_id = f"lane-{lane}"
    if progress is None:
        progress = kit().write_progress
    kind = f"lane-{lane}-{'code' if writes_code else 'read'}"
    eta_s = eta.estimate(eta_kind, default=eta.estimate(kind)) if eta_kind         else eta.estimate(kind)
    if dry_run:
        return {"lane": lane, "dry_run": True, "eta": eta.fmt(eta_s)}
    if lane_ctx is None:
        lane_ctx = lanes().run_lane
    if spawn is None:
        spawn = kit().spawn
    main = lanes().main_tree(root)
    task = None
    t0 = clock()
    ok = False
    try:
        with lane_ctx(root, CODE, lane, run_id, cap=lane_cap()) as claim:
            task = progress_task(claim["index"])
            wt = Path(claim["worktree"])
            seed_config(wt, root)
            progress(main, task, 20, f"{lane}: running headless in {wt.name}", eta_s,
                     "running")
            line = spawn(root, CODE, prompt, note=run_id, writes_code=writes_code,
                         timeout=timeout, cwd=wt, stdin=True,
                         extra=CODE_EXTRA if writes_code else (),
                         governor="queued", governor_timeout=timeout, kind="build",
                         slot_id=lane, progress_task=task, **route)
        line = dict(line, worktree=str(wt))
        ok = line.get("rc") == 0 and not line.get("error")
        return line
    finally:
        spent = clock() - t0
        record(kind, spent, ok=ok)
        if eta_kind:
            record(eta_kind, spent, ok=ok)
        if task is not None:
            progress(main, task, 100, f"{lane}: {'finished' if ok else 'failed'}", 0,
                     "done" if ok else "failed")


def status(root=ROOT):
    rows = []
    for row in lanes().repo_lane_state(root, lane_cap()):
        rows.append(" ".join(f"{k}={v}" for k, v in sorted(row.items())))
    for lane in LANES:
        rows.append(f"{lane}: eta={eta.fmt(eta.estimate(f'lane-{lane}-code'))}")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="EW laned headless driver")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    r = sub.add_parser("run")
    r.add_argument("lane")
    r.add_argument("--prompt-file", required=True)
    r.add_argument("--writes-code", action="store_true")
    r.add_argument("--timeout", type=int, default=3600)
    r.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print("\n".join(status()))
        return 0
    prompt = Path(a.prompt_file).read_text(encoding="utf-8")
    line = run_lane(a.lane, prompt, a.writes_code, a.timeout, a.dry_run)
    if a.dry_run:
        print(f"{a.lane}: dry-run ok")
        return 0
    print(f"{a.lane}: rc={line.get('rc')} error={line.get('error')} "
          f"worktree={line.get('worktree')}")
    # plan 149 TOOLS-07: the same success test run_lane records (rc 0, no error)
    return 0 if line.get("rc") == 0 and not line.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
