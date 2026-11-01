"""W44 (MAIN ORDER Nee58d0 item 3): the idle deep-dive backs off to weekly
after 3 dives in a row proposed 0 plans, and resets to daily on any plan
proposed (dives 0042 / 0043 proposed none at about $0.50 a night)."""
import datetime as _dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ew_loop  # noqa: E402
from ew_loopkit import ROADMAP, deps, git, make_root, real_git  # noqa: E402
from loop_roadmap import dive_backoff, dive_history  # noqa: E402

D = _dt.date


def test_three_zero_dives_back_off_until_a_week_after_the_last():
    h = [("20261029", 0), ("20261030", 0), ("20261031", 0)]
    assert dive_backoff(h, D(2026, 11, 1)) is True
    assert dive_backoff(h, D(2026, 11, 6)) is True
    assert dive_backoff(h, D(2026, 11, 7)) is False  # weekly dive is due


def test_weekly_zero_dive_keeps_weekly():
    h = [("20261030", 0), ("20261031", 0), ("20261107", 0)]
    assert dive_backoff(h, D(2026, 11, 8)) is True
    assert dive_backoff(h, D(2026, 11, 14)) is False


def test_any_plan_proposed_resets_to_daily():
    h = [("20261029", 0), ("20261030", 0), ("20261031", 0), ("20261107", 1)]
    assert dive_backoff(h, D(2026, 11, 8)) is False
    h = [("20261029", 0), ("20261030", 2), ("20261031", 0)]
    assert dive_backoff(h, D(2026, 11, 1)) is False


def test_fewer_than_three_dives_never_back_off():
    assert dive_backoff([], D(2026, 11, 1)) is False
    assert dive_backoff([("20261030", 0), ("20261031", 0)], D(2026, 11, 1)) is False


@pytest.mark.git
def test_history_reads_plans_added_by_each_deep_dive_commit(tmp_path):
    root = tmp_path / "r"
    (root / "docs" / "research").mkdir(parents=True)
    (root / "docs" / "plans").mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    (root / "docs/research/0001-deep-dive-20261030.md").write_text("x\n")
    (root / "docs/plans/001-a.md").write_text("# Plan 001 - a\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "dive 1")
    (root / "docs/plans/002-b.md").write_text("# Plan 002 - b\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "not a dive")
    (root / "docs/research/0002-deep-dive-20261031.md").write_text("y\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "dive 2")
    assert dive_history(root, real_git) == [("20261030", 1), ("20261031", 0)]
    assert dive_history(tmp_path / "missing", real_git) == []


@pytest.mark.git
def test_tick_skips_the_dive_while_backed_off(tmp_path, monkeypatch):
    rm = ROADMAP.replace("[ ] open", "[x] done")
    root = make_root(tmp_path, roadmap=rm, handoff="")
    d = deps(root)
    today = _dt.datetime.fromtimestamp(d.clock()).date()
    zero = [((today - _dt.timedelta(days=k)).strftime("%Y%m%d"), 0) for k in (3, 2, 1)]
    monkeypatch.setattr(ew_loop, "dive_history", lambda tree, g: zero)
    ew_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == []
    monkeypatch.setattr(ew_loop, "dive_history", lambda tree, g: zero[:2] + [(zero[2][0], 1)])
    ew_loop.tick(deps=d, no_push=True)
    assert len(d.seen["launch"]) == 1 and d.seen["launch"][0].startswith("DD-")
