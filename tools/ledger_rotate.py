#!/usr/bin/env python3
"""Plan 138: cap the control ledgers and finished progress files.

    ledger_rotate.py [--dry-run] [--root R]   rotate now (or print the plan)

Old rows move to ops/loop/control/archive/<ledger>-YYYYMM.jsonl (append, by
the row's own month); finished progress files move to progress/archive/.
Moves only, never deletes (FLEET item 9). Rules:
  headless_usage.jsonl   rows older than 35 days (never under 8 days, so the
                         24 h governor window and MAIN's weekly split hold)
  timings.jsonl          keep the newest 200 ok rows per kind (eta.py reads
                         the last 5) plus every row younger than 30 days
  claims / gitlock / identity.jsonl   rows older than 30 days
  progress/*.json        status done / failed, updated over 7 days ago
                         (never loop.json, never a running or blocked file)
Torn or timestamp-less lines always stay. A ledger that changed size while
it was being rewritten is skipped and retried next run, so a kit append is
never lost (the usage_ledger.backfill_kind guard). Idempotent. The tick runs
rotate_daily once per local day after reap_lost. Stdlib only.
"""

import argparse
import datetime as _dt
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL_REL = Path("ops/loop/control")
ARCHIVE = "archive"
MARKER = "ledger_rotate.json"
DAY_S = 86400
USAGE_KEEP_DAYS = 35
USAGE_MIN_KEEP_S = 8 * DAY_S
TIMINGS_KEEP_DAYS = 30
TIMINGS_KEEP_OK = 200
KIT_LOG_KEEP_DAYS = 30
KIT_LOGS = ("claims", "gitlock", "identity")
PROGRESS_KEEP_DAYS = 7
PROGRESS_FINISHED = ("done", "failed")
PROGRESS_NEVER = ("loop.json",)


def _epoch(value):
    """Epoch seconds of a number or an ISO string (naive = local), else None.
    Plan 149 TOOLS-06: a time the archive month cannot be taken of (non-finite,
    out of range) is None, so that row stays like a timestamp-less one."""
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            e = float(value)
        elif isinstance(value, str):
            dt = _dt.datetime.fromisoformat(value)
            e = (dt.astimezone() if dt.tzinfo is None else dt).timestamp()
        else:
            return None
        _dt.datetime.fromtimestamp(e)  # the archive bucket must be computable
    except (ValueError, OverflowError, OSError):
        return None
    return e


def _parse(raw):
    try:
        r = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return r if isinstance(r, dict) else None


def row_epoch(r):
    """A row's time: "ts" (usage, timings) else "at" (kit claims / gitlock /
    identity logs)."""
    for key in ("ts", "at"):
        e = _epoch(r.get(key))
        if e is not None:
            return e
    return None


def age_rule(days):
    """Rule: a row moves when it is older than days."""
    def rule(rows, now):
        return {i for i, r, e in rows if now - e > days * DAY_S}
    return rule


def timings_rule(rows, now):
    """Old rows move unless they are among their kind's newest TIMINGS_KEEP_OK
    ok rows (file order is time order: eta.record appends)."""
    keep_ok, seen = set(), {}
    for i, r, _e in reversed(rows):
        if r.get("ok") is True:
            k = r.get("kind")
            seen[k] = seen.get(k, 0) + 1
            if seen[k] <= TIMINGS_KEEP_OK:
                keep_ok.add(i)
    return {i for i, r, e in rows
            if now - e > TIMINGS_KEEP_DAYS * DAY_S and i not in keep_ok}


def plan_jsonl(path, rule, now, min_keep_s=0):
    """{"data", "keep": [line bytes], "move": [(epoch, line bytes)]} or None."""
    try:
        data = Path(path).read_bytes()
    except FileNotFoundError:
        return None
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    rows = []
    for i, raw in enumerate(lines):
        r = _parse(raw)
        e = row_epoch(r) if r is not None else None
        if e is not None:
            rows.append((i, r, e))
    when = {i: e for i, _r, e in rows}
    moving = {i for i in rule(rows, now) if now - when[i] > min_keep_s}
    return {"data": data,
            "keep": [ln for i, ln in enumerate(lines) if i not in moving],
            "move": [(when[i], ln) for i, ln in enumerate(lines) if i in moving]}


def _append(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as fh:
        fh.write(b"".join(ln + b"\n" for ln in lines))


def rotate_jsonl(path, rule, now, archive_dir, min_keep_s=0, dry_run=False,
                 _before_replace=None):
    """Rows moved (0 when none), or None when the file changed meanwhile or a
    writer held it (retry next run). The archive is appended only after the
    re-stat, then the live file is replaced: a failed replace can duplicate a
    row in the archive, never lose one."""
    path = Path(path)
    plan = plan_jsonl(path, rule, now, min_keep_s)
    if plan is None or not plan["move"]:
        return 0
    if dry_run:
        return len(plan["move"])
    tmp = path.with_name(path.name + ".p138.tmp")
    tmp.write_bytes(b"".join(ln + b"\n" for ln in plan["keep"]))
    if _before_replace is not None:
        _before_replace()
    try:
        if path.stat().st_size != len(plan["data"]):
            tmp.unlink()
            return None
        by_month = {}
        for e, ln in plan["move"]:
            by_month.setdefault(_dt.datetime.fromtimestamp(e).strftime("%Y%m"), []).append(ln)
        for m, lines in sorted(by_month.items()):
            _append(Path(archive_dir) / f"{path.stem}-{m}.jsonl", lines)
        os.replace(tmp, path)
    except OSError:  # a writer holds it open (Windows): retry next run
        try:
            tmp.unlink()
        except OSError:
            pass
        return None
    return len(plan["move"])


def _free_name(d, name):
    p = d / name
    n = 1
    while p.exists():
        p = d / f"{Path(name).stem}.{n}{Path(name).suffix}"
        n += 1
    return p


def rotate_progress(progress_dir, now, dry_run=False):
    """Finished progress files moved to progress/archive/ (never overwritten)."""
    progress_dir, n = Path(progress_dir), 0
    for p in sorted(progress_dir.glob("*.json")):
        if p.name in PROGRESS_NEVER:
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if not isinstance(doc, dict) or doc.get("status") not in PROGRESS_FINISHED:
            continue
        e = _epoch(doc.get("updated"))
        if e is None or now - e <= PROGRESS_KEEP_DAYS * DAY_S:
            continue
        if not dry_run:
            arch = progress_dir / ARCHIVE
            arch.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(p, _free_name(arch, p.name))
            except OSError:
                continue
        n += 1
    return n


def rotate(root, now=None, dry_run=False):
    """One pass over every ledger: {name: moved, "progress": n, "skipped": [...]}."""
    now = time.time() if now is None else now
    ctl = Path(root) / CONTROL_REL
    arch = ctl / ARCHIVE
    jobs = [("headless_usage", age_rule(USAGE_KEEP_DAYS), USAGE_MIN_KEEP_S),
            ("timings", timings_rule, 0)]
    jobs += [(name, age_rule(KIT_LOG_KEEP_DAYS), 0) for name in KIT_LOGS]
    res = {"skipped": []}
    for name, rule, floor in jobs:
        n = rotate_jsonl(ctl / f"{name}.jsonl", rule, now, arch, min_keep_s=floor,
                         dry_run=dry_run)
        if n is None:
            res["skipped"].append(name)
        res[name] = n or 0
    res["progress"] = rotate_progress(ctl / "progress", now, dry_run=dry_run)
    return res


def total(res):
    return sum(v for k, v in res.items() if k not in ("skipped", "progress")) + res["progress"]


def summary(res):
    rows = sum(v for k, v in res.items() if k not in ("skipped", "progress"))
    line = f"ledgers rotated: {rows} row(s), {res['progress']} progress file(s) archived"
    if res["skipped"]:
        line += ", skipped " + ", ".join(res["skipped"])
    return line


def rotate_daily(root, now=None):
    """rotate() at most once per local day (marker file); None when already
    done today. A day with a skipped ledger is not marked, so the next tick
    retries it."""
    now = time.time() if now is None else now
    marker = Path(root) / CONTROL_REL / MARKER
    day = _dt.datetime.fromtimestamp(now).strftime("%Y-%m-%d")
    try:
        if json.loads(marker.read_text(encoding="utf-8")).get("day") == day:
            return None
    except (OSError, ValueError, AttributeError):
        pass
    res = rotate(root, now)
    if not res["skipped"]:
        marker.parent.mkdir(parents=True, exist_ok=True)
        tmp = marker.with_name(marker.name + ".tmp")
        tmp.write_text(json.dumps({"day": day, "res": res}), encoding="ascii", newline="\n")
        os.replace(tmp, marker)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="EW control ledger rotation (plan 138)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--now", type=float, default=None)
    a = ap.parse_args(argv)
    res = rotate(Path(a.root), now=a.now, dry_run=a.dry_run)
    verb = "would move" if a.dry_run else "moved"
    for k, v in res.items():
        if k != "skipped":
            print(f"{verb} {k}: {v}")
    if res["skipped"]:
        print("skipped (changed meanwhile): " + ", ".join(res["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
