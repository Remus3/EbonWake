"""Kit v25 LANE-CAP guard (MAIN ORDER 2026-10-27, section 5 item 4).

EW's lane driver reads its lane cap and governor slot count from the live
machine config (FLEET_LANES_CONFIG / ~/.fleet/lanes.json) with no hard-coded
3 left, and a True should_yield only declines to start the next cycle: it
never kills or terminates a worker.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import ew_lane  # noqa: E402
import ew_loop  # noqa: E402
from ew_loopkit import deps, make_root  # noqa: E402


def test_cap_and_slot_count_follow_machine_config(tmp_path, monkeypatch):
    cfg = tmp_path / "lanes.json"
    cfg.write_text(json.dumps({"governor_width": 5, "lane_cap_max": 5}), encoding="ascii")
    monkeypatch.setenv("FLEET_LANES_CONFIG", str(cfg))
    assert ew_lane.lane_cap() == 5
    assert ew_lane.slot_count() == 5
    assert ew_loop.Deps(ROOT).lane_cap() == 5
    cfg.unlink()
    assert ew_lane.lane_cap() == 3
    assert ew_lane.slot_count() == 3


def test_no_hard_coded_cap_left_in_driver():
    for rel in ("tools/ew_lane.py", "tools/ew_loop.py"):
        text = (ROOT / rel).read_text(encoding="ascii")
        assert not re.search(r"\bLANE_CAP\s*=", text), rel
        assert not re.search(r"cap=3\b|width=3\b|range\(3\)", text), rel


def _no_kill(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a worker was killed or terminated")
    monkeypatch.setattr(os, "kill", boom)
    monkeypatch.setattr(subprocess.Popen, "kill", boom)
    monkeypatch.setattr(subprocess.Popen, "terminate", boom)


def test_should_yield_pauses_worker_without_kill(tmp_path, monkeypatch):
    _no_kill(monkeypatch)
    root = make_root(tmp_path)
    items = ew_loop.Items(root)
    items.put({"id": "012", "kind": "plan", "state": "dispatched", "lane": "data",
               "prompt": "p", "title": "t", "label": "l", "attempts": 1})
    ran = []
    d = deps(root, should_yield=lambda: True)
    rc = ew_loop.lane_worker("012", deps=d, run_lane=lambda *a, **k: ran.append(a))
    rec = items.get("012")
    assert rc == 0 and ran == []
    assert rec["state"] == "paused" and rec["error"] == "paused: should_yield"
    assert rec["attempts"] == 0  # a yield costs no attempt


def test_admission_refusal_is_a_pause_retried_next_tick(tmp_path):
    root = make_root(tmp_path)
    items = ew_loop.Items(root)
    items.put({"id": "012", "kind": "plan", "state": "dispatched", "lane": "data",
               "prompt": "p", "title": "t", "label": "l", "attempts": 1})

    def run_lane(*a, **k):
        raise RuntimeError("LaneRefused: admission: free RAM 1000 MB below floor 2048 MB")

    ew_loop.lane_worker("012", deps=deps(root), run_lane=run_lane)
    rec = items.get("012")
    assert rec["state"] == "paused" and rec["attempts"] == 0
    assert ew_loop.dispatchable(rec)


def test_should_yield_reads_kit_and_is_advisory(monkeypatch):
    class FakeLanes:
        def should_yield(self, code):
            assert code == "EW"
            raise OSError("governor unreadable")
    monkeypatch.setattr(ew_lane, "lanes", lambda: FakeLanes())
    assert ew_lane.should_yield() is False
