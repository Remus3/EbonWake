"""Post-merge identity check for bot PRs (MAIN ORDER N38ca97, DEPENDABOT-MERGE-RULE).

A bot PR (Dependabot or any other bot) lands ONLY by path A (squash on GitHub
with the operator as author and committer, every Co-authored-by trailer
removed) or path B (close the PR, re-apply the bump as an operator commit).
A squash done on GitHub never runs the local commit-msg hook, so the kit's
fleet_identity strip does not apply there and a bad commit is on the remote
before pre-push sees anything. This check closes that gap: run it right after
every bot-PR merge.

    python tools/bot_pr_check.py [--repo DIR] [--remote origin] [--branch main]
                                 [--range REV_RANGE] [--no-fetch]

It records the remote-tracking tip, fetches, and scans the NEW default-branch
commit(s) (old tip..new tip; the tip commit alone when nothing new arrived;
--range overrides) for a non-operator / bot author or committer (kit
fleet_identity classes) and for ANY `Co-authored-by:` line (stricter than the
kit, which flags only a trailer naming Claude or a bot). Operator identities
come from local git config `fleet.operatorIdent`, as in the kit.

Exit 0 clean, 1 on a hit (fix it with ops/fleet_kit/fleet_rewrite.py under the
N7e0676 bot-contributor scope), 2 when git or the operator set is unavailable.
Each run appends one line to ops/runtime/bot_pr_check.jsonl (gitignored).
Output names a commit by short hash and a class, never a name or an address.
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_REL = Path("ops/runtime/bot_pr_check.jsonl")
COAUTHOR_RX = re.compile(r"^\s*co-authored-by\s*:", re.I)
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def _identity():
    name = "fleet_identity"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "ops/fleet_kit/fleet_identity.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       timeout=300, creationflags=_NO_WINDOW)
    return r.stdout.strip() if r.returncode == 0 else None


def coauthor_hits(rows):
    """[(short sha, 'co-authored-by')] for any Co-authored-by line, any name."""
    out = []
    for r in rows:
        if any(COAUTHOR_RX.match(ln) for ln in r["msg"].split("\n")):
            out.append((r["sha"][:10], "co-authored-by"))
    return out


def scan(repo, rev_args, idents):
    """Sorted [(short sha, class)] for the commits named by rev_args, or None."""
    fi = _identity()
    rows = fi.commits(repo, rev_args)
    if rows is None:
        return None, 0
    found = set(fi.violations(rows, idents)) | set(coauthor_hits(rows))
    return sorted(found), len(rows)


def _log(repo, row):
    path = Path(repo) / LOG_REL
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="ascii", newline="\n") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    except OSError:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=str(ROOT))
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--range", dest="rev_range")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    repo = Path(a.repo)
    tracking = f"{a.remote}/{a.branch}"
    idents = _identity().operator_idents(str(repo))
    if not idents:
        print("BOT-PR-CHECK: no fleet.operatorIdent in local git config", file=sys.stderr)
        return 2
    before = _git(repo, "rev-parse", "--verify", "-q", tracking)
    if not a.no_fetch and _git(repo, "fetch", "-q", a.remote, a.branch) is None:
        print("BOT-PR-CHECK: fetch failed", file=sys.stderr)
        return 2
    after = _git(repo, "rev-parse", "--verify", "-q", tracking)
    if a.rev_range:
        rev_args = [a.rev_range]
    elif not after:
        print(f"BOT-PR-CHECK: no {tracking}", file=sys.stderr)
        return 2
    elif before and before != after:
        rev_args = [f"{before}..{after}"]
    else:
        rev_args = ["-n", "1", after]
    found, n = scan(str(repo), rev_args, idents)
    if found is None:
        print("BOT-PR-CHECK: could not list " + " ".join(rev_args), file=sys.stderr)
        return 2
    _log(repo, {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "range": " ".join(rev_args),
                "commits": n, "hits": [f"{s} {c}" for s, c in found]})
    if found:
        for short, cls in found:
            print(f"BOT-PR-CHECK: {short} {cls}")
        print("BOT-PR-CHECK: FAIL - record it and fix with ops/fleet_kit/fleet_rewrite.py "
              "(bot-contributor scope)")
        return 1
    print(f"BOT-PR-CHECK: {n} commit(s) clean")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "ascii")
    sys.exit(main())
