#!/usr/bin/env python3
"""Plan 173: plan doc / ROADMAP consistency lint (stdlib only).

Checks over docs/plans:
- first-line: each NNN-*.md starts with `# Plan NNN - Title`, NNN equal to
  the filename prefix;
- duplicate: no plan number is used by two docs;
- no-row: each doc has a `| NNN | ... |` row in ROADMAP.md (or in
  ROADMAP-history.md, where finished rows are archived);
- missing-doc: every `docs/plans/...` path a ROADMAP row cites exists.
Rows without a doc are fine (order rows). LEGACY holds the exceptions that
existed when the lint landed, so only new drift fails; a fixed exception
must leave LEGACY (stale_allow reports it).

Usage: python tools/plan_lint.py [--root DIR] [--no-legacy]
Exit 0 clean, 1 findings. Messages are ASCII.
"""

import argparse
import re
import sys
from collections import namedtuple
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

Finding = namedtuple("Finding", "kind number message")

DOC_RE = re.compile(r"^(\d{3})-.*\.md$")
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|")
CITE_RE = re.compile(r"docs/plans/[A-Za-z0-9_\-./]*[A-Za-z0-9_\-]")

# (kind, number) pairs present when plan 173 landed (2026-11-10). Only ever
# shrinks: 089/090 are kit-adoption docs, 121-126 OCR/catalog docs carried in
# order sections, 162 is cited from row 159 - none has its own numbered row.
LEGACY = frozenset({
    ("no-row", "089"), ("no-row", "090"),
    ("no-row", "121"), ("no-row", "122"), ("no-row", "123"),
    ("no-row", "124"), ("no-row", "125"), ("no-row", "126"),
    ("no-row", "162"),
})


def _rows(path):
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ROW_RE.match(line)
        if m:
            out.append((m.group(1).zfill(3), line))
    return out


def _ascii(text):
    return text.encode("ascii", "replace").decode("ascii")


def _all_findings(root):
    root = Path(root)
    plans = root / "docs" / "plans"
    found = []
    docs = {}
    for p in sorted(plans.glob("*.md")):
        m = DOC_RE.match(p.name)
        if not m:
            continue
        num = m.group(1)
        docs.setdefault(num, []).append(p.name)
        text = p.read_text(encoding="utf-8", errors="replace")
        first = text.splitlines()[0] if text else ""
        if not re.match(r"^# Plan %s - \S" % num, first):
            found.append(Finding("first-line", num, _ascii(
                "plan %s: %s first line must be '# Plan %s - Title', got %r"
                % (num, p.name, num, first[:60]))))
    for num, names in sorted(docs.items()):
        if len(names) > 1:
            found.append(Finding("duplicate", num, _ascii(
                "plan %s: number used by %s" % (num, ", ".join(names)))))
    rows = _rows(plans / "ROADMAP.md")
    row_nums = {n for n, _ in rows} | {
        n for n, _ in _rows(plans / "ROADMAP-history.md")}
    for num in sorted(docs):
        if num not in row_nums:
            found.append(Finding("no-row", num, _ascii(
                "plan %s: %s has no ROADMAP row '| %s | ... |'"
                % (num, docs[num][0], num))))
    for num, line in rows:
        for cite in CITE_RE.findall(line):
            if not (root / cite).exists():
                found.append(Finding("missing-doc", num, _ascii(
                    "plan %s: ROADMAP row cites %s, which does not exist"
                    % (num, cite))))
    found.sort(key=lambda f: (f.number, f.kind, f.message))
    return found


def lint(root=ROOT, allow=None):
    """Findings for the tree at root, minus the allow-list (LEGACY default)."""
    allow = LEGACY if allow is None else set(allow)
    return [f for f in _all_findings(root) if (f.kind, f.number) not in allow]


def stale_allow(root=ROOT, allow=LEGACY):
    """Allow-list entries that no longer match a finding, sorted."""
    live = {(f.kind, f.number) for f in _all_findings(root)}
    return sorted(set(allow) - live)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--no-legacy", action="store_true",
                    help="ignore the legacy allow-list")
    args = ap.parse_args(argv)
    found = lint(args.root, allow=() if args.no_legacy else None)
    for f in found:
        print(f.message)
    print("plan_lint: %d finding(s)" % len(found))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
