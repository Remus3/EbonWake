#!/usr/bin/env python3
"""ETA timing log (operator standing order 4).

    eta.py record <kind> <seconds> [--ok|--failed]   append one finished run
    eta.py estimate <kind> [--default N]             print "[~Ns]" from history
    eta.py run <kind> -- <cmd...>                    time a command, record it

Log: ops/loop/control/timings.jsonl, one JSON object per line
{"kind", "seconds", "ok", "ts"}. Estimate = median of the last 5 OK runs of that
kind; with none, that kind's measured default (DEFAULTS) or 60 s. The short lane
names build / data / review alias the lane run kind lane-<lane>-code. Format follows FLEET item 3: s under 120 s,
m under 120 m, h beyond.
"""

import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "ops" / "loop" / "control" / "timings.jsonl"
WINDOW = 5
DEFAULT_S = 60.0
# Session 29 measured medians (seconds) of OK runs: lane-<lane>-code from this
# log (tools/ew_lane records every finished lane run), item-<kind> from loop
# item dispatched -> finished (runs over the 3600 s lane timeout excluded).
DEFAULTS = {
    "lane-build-code": 416.0,
    "lane-data-code": 491.0,
    "lane-review-code": 763.0,
    "item-plan": 877.0,
    "item-deep-dive": 388.0,
    "item-order": 301.0,
    "item-resolve": 254.0,
    "item-handoff": 225.0,
    "loop-review": 87.0,
}
ALIASES = {lane: f"lane-{lane}-code" for lane in ("build", "data", "review")}


def fmt(seconds):
    s = max(0, round(float(seconds)))
    if s < 120:
        return f"[~{s}s]"
    if s < 120 * 60:
        return f"[~{round(s / 60)}m]"
    return f"[~{round(s / 3600)}h]"


def record(kind, seconds, ok=True, log=LOG, clock=time.time):
    if not kind or any(c.isspace() for c in kind):
        raise ValueError("kind must be a non-empty token")
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    row = {"kind": kind, "seconds": round(float(seconds), 3), "ok": bool(ok),
           "ts": round(clock(), 3)}
    with log.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def history(kind, log=None):
    rows = []
    try:
        lines = Path(log or LOG).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return rows
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue  # a torn line is skipped, never fatal
        if row.get("kind") == kind and row.get("ok") is True:
            rows.append(float(row["seconds"]))
    return rows


def canonical(kind):
    return ALIASES.get(kind, kind)


def estimate(kind, default=None, log=None):
    kind = canonical(kind)
    rows = history(kind, log)[-WINDOW:]
    if rows:
        return statistics.median(rows)
    return float(DEFAULTS.get(kind, DEFAULT_S) if default is None else default)


def resolve_cmd(cmd):
    """Resolve argv[0] on PATH (PATHEXT on Windows: npm -> npm.cmd)."""
    exe = shutil.which(cmd[0]) if cmd else None
    return [exe, *cmd[1:]] if exe else list(cmd)


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) >= 3 and a[0] == "record":
        ok = "--failed" not in a
        record(a[1], float(a[2]), ok=ok)
        return 0
    if len(a) >= 2 and a[0] == "estimate":
        default = float(a[a.index("--default") + 1]) if "--default" in a else None
        print(fmt(estimate(a[1], default)))
        return 0
    if len(a) >= 4 and a[0] == "run" and a[2] == "--":
        print(f"{a[1]} ETA {fmt(estimate(a[1]))}", file=sys.stderr)
        t0 = time.time()
        rc = subprocess.run(resolve_cmd(a[3:])).returncode
        record(a[1], time.time() - t0, ok=(rc == 0))
        return rc
    print(__doc__, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main())
