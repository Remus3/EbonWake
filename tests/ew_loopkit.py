"""Shared tools/ew_loop.py test helpers (plan 156, TESTS-A-17 / -19).

test_ew_loop, test_ew_loop_routes, test_ew_loop_gate_cache and
test_usage_ledger import these from here instead of from test_ew_loop.

TESTS-A-19: `isolate_git(monkeypatch)` hides the machine's git global and
system config (GIT_CONFIG_GLOBAL -> os.devnull, GIT_CONFIG_NOSYSTEM=1) and
supplies a fixed identity through the environment, so a host `merge.ff=only`,
commit signing or global hooksPath cannot change a tmp_path git world - in
the test's own git calls and in the ew_loop code under test alike."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ew_loop  # noqa: E402

GIT_TIMEOUT_S = 60  # plan 150: a git stuck on a lock / prompt fails, never hangs
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}

ROADMAP = """# Ebonwake roadmap

| # | Plan | Status |
|---|---|---|
| 001 | Skeleton | [x] done 2026-10-04 |
| 012 | Grind spot recommender | [ ] open |
| 013 | Season pass tracker | [ ] open |
"""

HANDOFF = """EW NEXT SESSION
---------------
Next action: x

Carried forward (not acted on yet):
- OPERATOR (physical): press Ctrl+Alt+E and confirm the overlay toggles.
- OPERATOR: set profile.family in config.
- MAIN to record EW's port block in the registry.
- NOTE: OCR residual accepted.
- NOTE (new, operator 2026-10-06): one character, no alts.
- Fix the OCR cache key so a same-second rewrite is
  re-read.

Context: CLAUDE.md
"""


def isolate_git(monkeypatch):
    """TESTS-A-19: no host git config reaches any git the test spawns."""
    for k, v in GIT_ENV.items():
        monkeypatch.setenv(k, v)


class FakeSpawn:
    def __init__(self, results=None):
        self.calls = []
        self.results = list(results or [])

    def __call__(self, root, code, prompt, **kw):
        self.calls.append(dict(kw, prompt=prompt, code=code))
        if self.results:
            r = self.results.pop(0)
            return r(kw) if callable(r) else r
        return {"rc": 0, "error": None, "result": "ok"}


def make_root(tmp_path, roadmap=ROADMAP, handoff=HANDOFF, local=None):
    root = tmp_path / "repo"
    (root / "docs" / "plans").mkdir(parents=True)
    (root / "docs" / "research").mkdir(parents=True)
    (root / "docs" / "plans" / "ROADMAP.md").write_text(roadmap, newline="\n")
    (root / "docs" / "plans" / "012-grind-spots.md").write_text(
        "# Plan 012 - Grind spot recommender by AP/DP\n", newline="\n")
    (root / "EW-NEXT-SESSION.txt").write_text(handoff, newline="\n")
    if local is not None:
        (root / "config").mkdir()
        (root / "config" / "local.json").write_text(json.dumps(local))
    return root


def deps(root, **over):
    seen = {"launch": [], "record": []}
    base = dict(
        spawn=FakeSpawn(),
        lane_state=lambda: [{"index": i, "state": "FREE", "lane": None} for i in range(3)],
        pid_alive=lambda pid: True,
        main_tree=root,
        launch=lambda iid: seen["launch"].append(iid) or 4242,
        gates=lambda cwd: (True, "green"),
        leak_pre_push=lambda cwd, line: True,
        estimate=lambda kind, default=None: 2700.0,
        record=lambda kind, s, ok=True: seen["record"].append(kind),
        clock=lambda: 1_790_000_000.0,
        roster_path=None,  # plan 093: never the machine roster from FLEET_ROSTER
        should_yield=lambda: False,  # kit v25: never the live governor
        lane_cap=lambda: 3,
    )
    base.update(over)
    d = ew_loop.Deps(root, **base)
    d.seen = seen
    # plan 098: the detached review / push workers run inline in tests (same
    # process, same deps), so a tick's observable end state is unchanged
    if "launch_review" not in over:
        d.launch_review = lambda iid: ew_loop.review_worker(iid, deps=d) or 4243
    if "launch_push" not in over:
        d.launch_push = lambda: ew_loop.push_worker(deps=d) or 4244
    return d


def _inbox_root(tmp_path, roadmap="", local_extra=None):
    inbox, outbox = tmp_path / "in", tmp_path / "out"
    inbox.mkdir()
    outbox.mkdir()
    loop = {"inbox_dir": str(inbox), "outbox_dir": str(outbox)}
    loop.update(local_extra or {})
    root = make_root(tmp_path, roadmap=roadmap, handoff="", local={"loop": loop})
    return root, inbox, outbox


def git(cwd, *args):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                        "-c", "core.hooksPath=/dev/null", *args], cwd=str(cwd),
                       capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def real_git(args, cwd, input=None):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                           "-c", "core.hooksPath=/dev/null", *args], cwd=str(cwd),
                          capture_output=True, text=True, input=input, timeout=GIT_TIMEOUT_S)


def git_world(tmp_path, kind="plan"):
    root = make_root(tmp_path, handoff="")
    git(root, "init", "-q", "-b", "main")
    # LF on every host: ew_loop.tree_key drops GIT_* env, so it alone reads the
    # host config; a CRLF file would hash differently under a host autocrlf
    (root / ".gitignore").write_text("ops/\n", newline="\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    wt = tmp_path / "ew-worktrees" / "lane-1"
    git(root, "worktree", "add", "-q", "--detach", str(wt))
    (wt / "feature.txt").write_text("work\n", newline="\n")
    rec = {"id": "012", "kind": kind, "title": "Grind spot recommender",
           "label": "plan 012: Grind spot recommender", "state": "ran",
           "worktree": str(wt), "rc": 0, "lane": "build", "rounds": 0}
    ew_loop.Items(root).put(rec)
    return root, wt
