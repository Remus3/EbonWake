"""Plan 136: the loop status card - a read-only summary of the loop tick's own
control files (ops/loop/control/ in the MAIN checkout): last tick age, HALT,
usage backoff, in-flight lanes with their checklist line, and items parked in
adjudicate / gave-up / merge-conflict / blocked. Never writes; a missing or
torn file reads as unknown, never an error.

Grounding (tools/ew_loop.py Tick.write / tools/loop_base.py): loop.json keys
task, pct, step, eta_s (the tick period, 900), status, updated (ISO UTC),
state (idle | running | halted | backoff | limit | refused), fire, tick_s (the
tick's own duration), log, checklist [{id, task, state, eta_s}]; backoff.json
{delay_s, until (epoch), reason, since}; loop_items/<id>.json {id, state,
title, updated, lane?, needs?, error?}."""

import datetime as _dt
import json
import threading
import time
from pathlib import Path

CONTROL_REL = Path("ops/loop/control")
TICK_S = 900  # loop_base.TICK_S: the default tick period
CACHE_S = 10.0
STUCK_STATES = ("adjudicate", "gave-up", "merge-conflict", "blocked")
IN_FLIGHT = ("dispatched", "ran", "committed")  # loop_base.IN_FLIGHT
TEXT_MAX = 120


def _iso(ts):
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).replace(microsecond=0).isoformat()


def _epoch(text):
    if not isinstance(text, str):
        return None
    try:
        t = _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=_dt.timezone.utc)
    return t.timestamp()


def _read(path):
    """A JSON object, or None for a missing / torn / non-object file."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _text(v):
    s = " ".join(str(v).split()) if v is not None else ""
    return s.encode("ascii", "replace").decode("ascii")[:TEXT_MAX]


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def eta_label(s):
    """FLEET item 3 ETA form: seconds under 120 s, minutes under 120 m, else hours."""
    s = int(s)
    if s < 120:
        return f"~{s}s"
    if s < 7200:
        return f"~{round(s / 60)}m"
    return f"~{round(s / 3600)}h"


def main_root(root):
    """The main checkout of `root`: a linked worktree's `.git` file names
    <main>/.git/worktrees/<name>; anything else is its own main checkout."""
    root = Path(root)
    try:
        head = (root / ".git").read_text(encoding="utf-8").strip()
    except OSError:
        return root
    if not head.startswith("gitdir:"):
        return root
    gitdir = Path(head[len("gitdir:"):].strip())
    if gitdir.parent.name == "worktrees" and gitdir.parent.parent.name == ".git":
        return gitdir.parent.parent.parent
    return root


def _line(row, fallback):
    if not isinstance(row, dict):
        return fallback
    state = _text(row.get("state")) or fallback
    eta = _num(row.get("eta_s"))
    return f"{state}, {eta_label(eta)}" if eta and eta > 0 else state


def summary(root, now):
    """{state, fire, last_tick_utc, tick_age_s, tick_s, eta_s, stale, halted,
    backoff_until, backoff_reason, in_flight, stuck, counts}. state: halted >
    stale > backoff > loop.json's own state; unknown when loop.json is missing
    or torn (and no HALT)."""
    ctl = Path(root) / CONTROL_REL
    loop = _read(ctl / "progress" / "loop.json")
    halted = (ctl / "HALT").exists()
    out = {"state": "unknown", "fire": None, "last_tick_utc": None, "tick_age_s": None,
           "tick_s": None, "eta_s": TICK_S, "stale": False, "halted": halted,
           "backoff_until": None, "backoff_reason": None, "in_flight": [], "stuck": [],
           "counts": {}}
    rows = {}
    if loop is not None:
        eta = _num(loop.get("eta_s"))
        out["eta_s"] = eta if eta and eta > 0 else TICK_S
        fire = _num(loop.get("fire"))
        out["fire"] = int(fire) if fire is not None else None
        out["tick_s"] = _num(loop.get("tick_s"))
        at = _epoch(loop.get("updated"))
        if at is not None:
            out["last_tick_utc"] = _iso(at)
            out["tick_age_s"] = max(int(now - at), 0)
        out["stale"] = at is None or now - at > 2 * out["eta_s"]
        out["state"] = _text(loop.get("state")) or "unknown"
        for r in loop.get("checklist") or []:
            if isinstance(r, dict) and r.get("id"):
                rows[str(r["id"])] = r
    back = _read(ctl / "backoff.json") or {}
    until = _num(back.get("until"))
    if until and until > now:
        out["backoff_until"] = _iso(until)
        out["backoff_reason"] = _text(back.get("reason")) or None
    for p in sorted((ctl / "loop_items").glob("*.json")):
        rec = _read(p)
        if rec is None or not rec.get("id"):
            continue
        iid, state = _text(rec["id"]), _text(rec.get("state")) or "open"
        out["counts"][state] = out["counts"].get(state, 0) + 1
        if state in STUCK_STATES:
            row = {"id": iid, "state": state, "since": _text(rec.get("updated")) or None,
                   "title": _text(rec.get("title"))}
            if state == "blocked":
                row["needs"] = [_text(n) for n in rec.get("needs") or [] if n]
            if rec.get("error"):
                row["error"] = _text(rec["error"])
            out["stuck"].append(row)
        elif state in IN_FLIGHT:
            out["in_flight"].append({"id": iid, "state": state, "lane": rec.get("lane"),
                                     "title": _text(rec.get("title")),
                                     "line": _line(rows.get(iid), state)})
    if halted:
        out["state"] = "halted"
    elif out["stale"]:
        out["state"] = "stale"
    elif out["backoff_until"]:
        out["state"] = "backoff"
    return out


class LoopStatus:
    """GET /api/loop: summary() cached CACHE_S seconds (read-only)."""

    def __init__(self, root, clock=time.time, summarize=summary):
        self.root, self.clock, self._summarize = root, clock, summarize
        self._lock = threading.Lock()
        self._at, self._doc = None, None

    def clear(self):
        with self._lock:
            self._at, self._doc = None, None

    def view(self):
        now = self.clock()
        with self._lock:
            if self._at is None or now - self._at >= CACHE_S or now < self._at:
                self._doc = self._summarize(self.root, now)
                self._at = now
            return self._doc
