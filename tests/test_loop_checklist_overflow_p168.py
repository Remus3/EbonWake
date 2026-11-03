"""Plan 168: the loop checklist's overflow past the kit ROWS_MAX is counted.

tools/ew_loop.py Tick.checklist() keeps at most fleet_checklist.ROWS_MAX (20)
rows; the rows it drops are counted and written beside the rows in
progress/loop.json as "checklist_dropped" (EW analogue of SS FIX N44eed9 (a))."""

import json
import types

import pytest

from ew_loopkit import deps, ew_loop, make_root

ROWS = 25


def _roadmap(n):
    rows = "".join(f"| {200 + i:03d} | Overflow plan {i} | [ ] open |\n" for i in range(n))
    return "# Ebonwake roadmap\n\n| # | Plan | Status |\n|---|---|---|\n" + rows


def _bare_tick(root):
    load = ew_loop.ew_lane._load
    d = types.SimpleNamespace(
        root=root, clock=lambda: 1_790_000_000.0,
        estimate=lambda kind, default=None: 600.0,
        inbox=load("fleet_inbox", "ops/fleet_kit/fleet_inbox.py"),
        checklist=load("fleet_checklist", "ops/fleet_kit/fleet_checklist.py"))
    return ew_loop.Tick(d)


def _work(n):
    return [{"id": f"{200 + i:03d}", "title": f"Overflow plan {i}"} for i in range(n)]


def test_checklist_counts_rows_past_rows_max(tmp_path):
    t = _bare_tick(make_root(tmp_path, roadmap="", handoff=""))
    cap = t.d.checklist.ROWS_MAX
    out = t.checklist([], _work(ROWS), [])
    assert len(out) == cap == 20
    assert t.checklist_dropped == ROWS - cap == 5
    assert [r["id"] for r in out] == [f"{200 + i:03d}" for i in range(cap)]


def test_checklist_under_cap_drops_nothing(tmp_path):
    t = _bare_tick(make_root(tmp_path, roadmap="", handoff=""))
    assert len(t.checklist([], _work(3), [])) == 3
    assert t.checklist_dropped == 0


@pytest.mark.git
def test_loop_json_carries_dropped_count_at_25_rows(tmp_path):
    root = make_root(tmp_path, roadmap=_roadmap(ROWS), handoff="")
    doc = ew_loop.tick(deps=deps(root), no_push=True)
    assert len(doc["checklist"]) == 20 and doc["checklist_dropped"] == ROWS - 20
    disk = json.loads((root / "ops/loop/control/progress/loop.json").read_text())
    assert disk["checklist_dropped"] == ROWS - 20 and len(disk["checklist"]) == 20


@pytest.mark.git
def test_loop_json_dropped_is_zero_when_all_rows_fit(tmp_path):
    doc = ew_loop.tick(deps=deps(make_root(tmp_path)), no_push=True)
    assert doc["checklist_dropped"] == 0
