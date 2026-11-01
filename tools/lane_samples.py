#!/usr/bin/env python3
"""Order Nd11eb1 item 6 (EW-4, MAIN ruling 2026-11-01): lane transcript samples.

    lane_samples.py status     samples held, their size and the size cap, one line

1 lane in 20 plus every retry after a failure runs with session persistence on
(a known --session-id); when the run ends its transcript is copied to
<sidecar root>/EW/Scratch/lane-samples/. Nothing goes in the tree: this is a
public repo and raw transcripts carry paths and account ids. No sidecar = no
sample and no persistence (persist stays off, the kit's default).

The first FIRST_N samples are measured, then the size cap is set once and
recorded in cap.json. Over the cap the oldest samples leave by the Recycle Bin,
never a direct unlink; a recycle that fails keeps the file. Sampling never fails
a lane: every problem is a ledger line. Atomic writes, ASCII, stdlib only.
"""

import argparse
import contextlib
import json
import os
import re
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from loop_base import _NO_WINDOW, ascii_text, atomic_write, iso, read_json, read_jsonl  # noqa: E402

CODE = "EW"
ONE_IN = 20
FIRST_N = 20  # samples measured before the cap is set
CAP_FACTOR = 2  # cap = twice the first FIRST_N: room for about 2 x FIRST_N samples
SUB = "lane-samples"
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_RECYCLE_PS = ("Add-Type -AssemblyName Microsoft.VisualBasic; "
               "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($env:EW_RECYCLE_PATH, "
               "'OnlyErrorDialogs', 'SendToRecycleBin')")


def sample_dir(sidecar=None):
    """<sidecar root>/EW/Scratch/lane-samples, or None without a sidecar (kit
    fleet_lanes.sidecar_dir: None unless <root>/EW already exists)."""
    if sidecar is not None:
        return Path(sidecar) / SUB
    import ew_lane  # the kit loader; ew_lane imports this module at call time only
    scratch = ew_lane.lanes().sidecar_dir(CODE, "Scratch")
    return scratch / SUB if scratch is not None else None


def in_tree(path, root):
    """True when path is inside the repo checkout (never a place for a sample)."""
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return False
    return True


def begin(root, retry=False, sidecar=None):
    """The --session-id of a run to sample, or None to leave persistence off.
    A plain lane counts toward 1 in 20, the first one sampled; a retry after a
    failure is always sampled and does not advance the count. Never raises."""
    try:
        d = sample_dir(sidecar)
        if d is None or in_tree(d, root):
            return None
        d.mkdir(parents=True, exist_ok=True)
        if retry:
            return str(uuid.uuid4())
        state = read_json(d / "state.json", {})
        n = state.get("lanes", 0) if isinstance(state, dict) else 0
        n = n if isinstance(n, int) and not isinstance(n, bool) and n >= 0 else 0
        atomic_write(d / "state.json", json.dumps({"lanes": n + 1}))
        return str(uuid.uuid4()) if n % ONE_IN == 0 else None
    except Exception:  # noqa: BLE001 - sampling never fails a lane
        return None


def config_roots(environ=None, route_file=None):
    """Where a child's transcript can be: the config dirs of the headless route
    (the kit's single / account routes), CLAUDE_CONFIG_DIR, then ~/.claude."""
    env = os.environ if environ is None else environ
    out = []
    route = read_json(Path(route_file or Path.home() / ".fleet" / "headless_route.json"), {})

    def walk(node):
        if isinstance(node, dict):
            for key, val in node.items():
                if key == "config_dir" and isinstance(val, str) and val:
                    out.append(Path(val))
                else:
                    walk(val)
        elif isinstance(node, list):
            for val in node:
                walk(val)

    walk(route)
    if env.get("CLAUDE_CONFIG_DIR"):
        out.append(Path(env["CLAUDE_CONFIG_DIR"]))
    out.append(Path.home() / ".claude")
    return out


def find_transcript(session_id, roots):
    """<config dir>/projects/<cwd slug>/<session_id>.jsonl, or None."""
    for base in roots:
        hits = sorted((Path(base) / "projects").glob(f"*/{session_id}.jsonl"))
        if hits:
            return hits[0]
    return None


def _ledger(d, **row):
    with open(Path(d) / "ledger.jsonl", "a", encoding="ascii", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _samples(d):
    """Sample files oldest first (the name starts with the capture stamp)."""
    return sorted((Path(d) / "samples").glob("*.jsonl"), key=lambda p: p.name)


def recycle(path):
    """Send one file to the Recycle Bin (FLEET item 9). True when it left."""
    env = dict(os.environ, EW_RECYCLE_PATH=str(path))
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _RECYCLE_PS],
                   env=env, creationflags=_NO_WINDOW, capture_output=True, timeout=60, check=False)
    return not Path(path).exists()


def set_cap(d, clock=time.time):
    """Measure the first FIRST_N samples and record the cap, once. The cap, or
    None while still measuring."""
    doc = read_json(Path(d) / "cap.json", None)
    if isinstance(doc, dict) and isinstance(doc.get("cap_bytes"), int):
        return doc["cap_bytes"]
    sizes = [r["bytes"] for r in read_jsonl(Path(d) / "ledger.jsonl")
             if isinstance(r.get("bytes"), int)][:FIRST_N]
    if len(sizes) < FIRST_N:
        return None
    cap = CAP_FACTOR * sum(sizes)
    atomic_write(Path(d) / "cap.json", json.dumps({
        "cap_bytes": cap, "measured_n": FIRST_N, "total_bytes": sum(sizes),
        "median_bytes": int(statistics.median(sizes)), "max_bytes": max(sizes),
        "set": iso(clock()), "why": f"{CAP_FACTOR} x the first {FIRST_N} samples"}, indent=1))
    return cap


def enforce_cap(d, cap, recycle_fn=recycle):
    """Over the cap: oldest samples to the Recycle Bin, never the newest. Stops at
    the first file that would not leave. Returns the names sent."""
    gone = []
    files = _samples(d)
    total = sum(p.stat().st_size for p in files)
    for p in files[:-1]:
        if total <= cap:
            break
        size = p.stat().st_size
        if not recycle_fn(p):
            _ledger(d, event="recycle-failed", sample=p.name)
            break
        gone.append(p.name)
        total -= size
    return gone


def finish(root, session_id, label, roots=None, sidecar=None, clock=time.time, recycle_fn=recycle):
    """The sampled run ended: copy its transcript into the sidecar, then measure
    and enforce the cap. Returns the sample path or None. Never raises."""
    if not session_id:
        return None
    try:
        d = sample_dir(sidecar)
        if d is None or in_tree(d, root):
            return None
        src = find_transcript(session_id, config_roots() if roots is None else roots)
        now = clock()
        tag = _SAFE.sub("-", ascii_text(str(label), 40)).strip("-") or "lane"
        if src is None:
            _ledger(d, ts=iso(now), event="no-transcript", item=tag, session_id=session_id)
            return None
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
        dest = d / "samples" / f"{stamp}-{tag}-{session_id}.jsonl"
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.write_bytes(src.read_bytes())
        os.replace(tmp, dest)
        _ledger(d, ts=iso(now), event="sample", item=tag, session_id=session_id,
                bytes=dest.stat().st_size, sample=dest.name)
        cap = set_cap(d, clock)
        if cap is not None:
            for name in enforce_cap(d, cap, recycle_fn):
                _ledger(d, ts=iso(clock()), event="recycled", sample=name)
        return dest
    except Exception as exc:  # noqa: BLE001 - sampling never fails a lane
        with contextlib.suppress(Exception):
            _ledger(d, ts=iso(clock()), event="error", detail=ascii_text(repr(exc), 200))
        return None


def status_line(sidecar=None):
    d = sample_dir(sidecar)
    if d is None:
        return "lane samples: no sidecar"
    files = _samples(d)
    doc = read_json(d / "cap.json", None)
    cap = doc.get("cap_bytes") if isinstance(doc, dict) else None
    state = read_json(d / "state.json", {})
    lanes = state.get("lanes", 0) if isinstance(state, dict) else 0
    return (f"lane samples: {len(files)} held, {sum(p.stat().st_size for p in files)} bytes, "
            f"cap {cap if cap is not None else f'unset, measuring first {FIRST_N}'}, "
            f"{lanes} lanes counted")


def main(argv=None):
    ap = argparse.ArgumentParser(description="EW lane transcript samples")
    ap.add_argument("cmd", choices=("status",))
    ap.parse_args(argv)
    print(status_line())
    return 0


if __name__ == "__main__":
    sys.exit(main())
