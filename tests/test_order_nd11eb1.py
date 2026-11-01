"""Order Nd11eb1 (Fleet Insights W44): SS delivery through MAIN's roster, a recorded
budget reset lowers the governor's count, parked items in the loop status, the
spend line, lane transcript samples, and raw timing asserts stay out of the suite.
Git-free, tmp_path only: no real sidecar, config dir or Recycle Bin is touched."""

import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import ew_lane  # noqa: E402
import ew_loop  # noqa: E402
import lane_samples  # noqa: E402
import loop_inbox  # noqa: E402
import usage_ledger  # noqa: E402

from ew_loopkit import FakeSpawn, _inbox_root, deps  # noqa: E402

NOW = 1_790_000_000.0
HOUR = 3600


def iso(epoch):
    return _dt.datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="seconds")


def usage_row(end, dur=60.0, **extra):
    return dict({"ts": iso(end), "note": "lane-build", "kind": "build", "duration_s": dur,
                 "rc": 0}, **extra)


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="ascii", newline="\n")


# ---------------------------------------------------------------- item 1

def _main_tree(tmp_path, repos):
    main = tmp_path / "mainrepo"
    (main / "moon_sync_inbox").mkdir(parents=True)
    (main / "ops").mkdir()
    (main / "ops" / "fleet_roster.json").write_text(json.dumps({"repos": repos}))
    return main


def test_mains_inbox_row_finds_the_roster_for_every_code(tmp_path):
    ss = tmp_path / "ssrepo"
    (ss / "moon_sync_inbox").mkdir(parents=True)
    main = _main_tree(tmp_path, [{"code": "SS", "root": str(ss)},
                                 {"code": "XY", "inbox": str(tmp_path / "xy-in")}])
    root, _, _ = _inbox_root(tmp_path, local_extra={
        "dest_inboxes": {"MAIN": str(main / "moon_sync_inbox")}})
    t = ew_loop.Tick(deps(root, spawn=FakeSpawn()))
    assert t.dest_inbox("MAIN") == main / "moon_sync_inbox"
    assert t.dest_inbox("ss") == ss / "moon_sync_inbox"
    assert t.dest_inbox("XY") == tmp_path / "xy-in"
    assert t.dest_inbox("NOPE") is None


def test_no_main_row_and_no_roster_stays_unknown(tmp_path):
    root, _, _ = _inbox_root(tmp_path)
    assert ew_loop.Tick(deps(root)).dest_inbox("SS") is None


def test_configured_roster_still_wins_over_mains(tmp_path):
    mine = tmp_path / "mine-in"
    roster = tmp_path / "mine.json"
    roster.write_text(json.dumps({"repos": [{"code": "SS", "inbox": str(mine)}]}))
    main = _main_tree(tmp_path, [{"code": "SS", "inbox": str(tmp_path / "other")}])
    root, _, _ = _inbox_root(tmp_path, local_extra={
        "roster": str(roster), "dest_inboxes": {"MAIN": str(main / "moon_sync_inbox")}})
    assert ew_loop.Tick(deps(root)).dest_inbox("SS") == mine


def test_redelivery_reaches_ss_two_of_two_and_rehashes(tmp_path):
    """The ACCEPT shape: two notes whose latest ledger line reads no inbox known."""
    ss = tmp_path / "ssrepo"
    (ss / "moon_sync_inbox").mkdir(parents=True)
    main = _main_tree(tmp_path, [{"code": "SS", "root": str(ss)}])
    root, _, outbox = _inbox_root(tmp_path, local_extra={
        "dest_inboxes": {"MAIN": str(main / "moon_sync_inbox")}})
    names = ["2026-10-18-1234-from-EW-ANSWER-to-SS-batched-1-answers.md",
             "2026-11-01-0934-from-EW-ANSWER-re-a-note.md"]
    for n in names:
        (outbox / n).write_bytes(f"note {n}\n".encode("ascii"))
    ledger = root / ew_loop.DELIVERY_REL
    write_rows(ledger, [{"note": n, "to": "SS", "reached": False, "count": "0/1",
                         "detail": "no inbox known for SS"} for n in names])
    t = ew_loop.Tick(deps(root))
    t.redeliver(outbox)
    assert any("redelivered 2/2 reached" in s for s in t.log)
    last = {r["note"]: r for r in map(json.loads, ledger.read_text().splitlines())}
    assert all(last[n]["reached"] and last[n]["count"] == "1/1" for n in names)
    for n in names:
        assert (ss / "moon_sync_inbox" / n).read_bytes() == (outbox / n).read_bytes()
    assert "no inbox known" not in json.dumps([last[n] for n in names])


# ---------------------------------------------------------------- item 2

def _reset(control, ts, count=17):
    control.mkdir(parents=True, exist_ok=True)
    (control / "headless_budget.reset-2026-11-01.json").write_text(
        json.dumps({"resets": [{"ts": iso(ts), "tree": "EW", "count": count, "starts": []}]}),
        encoding="ascii")


class Inner:
    def __init__(self, used=0, cap=500):
        self.n, self.cap, self.window, self.clock = used, cap, 86400, lambda: NOW

    def used(self):
        return self.n

    def readable(self):
        return True

    def frees_at(self):
        return None


def test_rows_before_a_recorded_reset_do_not_count(tmp_path):
    control = tmp_path / "ops" / "loop" / "control"
    usage = control / "headless_usage.jsonl"
    write_rows(usage, [usage_row(NOW - 2 * HOUR - i) for i in range(17)]
               + [usage_row(NOW - 10)])
    b = usage_ledger.UsageBudget(Inner(used=0), usage)
    assert b.used() == 18  # no record yet: the larger ledger, as plan 100 has it
    _reset(control, NOW - HOUR)
    assert b.used() == 1  # only the run started after the reset
    b.inner.n = 3
    assert b.used() == 3  # the budget file still counts its own starts
    assert b.frees_at() is None or b.frees_at() > NOW - HOUR


def test_a_run_started_before_the_reset_and_ended_after_it_does_not_count(tmp_path):
    control = tmp_path / "control"
    usage = control / "headless_usage.jsonl"
    write_rows(usage, [usage_row(NOW - 100, dur=HOUR * 2)])
    _reset(control, NOW - HOUR)
    assert usage_ledger.UsageBudget(Inner(), usage).used() == 0


def test_a_torn_archive_or_a_future_stamp_is_no_reset(tmp_path):
    control = tmp_path / "control"
    usage = control / "headless_usage.jsonl"
    write_rows(usage, [usage_row(NOW - 10)])
    (control / "headless_budget.reset-2026-01-01.json").write_text("{torn", encoding="ascii")
    b = usage_ledger.UsageBudget(Inner(), usage)
    assert b.used() == 1
    _reset(control, NOW + HOUR)
    assert b.used() == 1


def test_loop_gate_reads_the_kit_tree_budget_cap(tmp_path):
    root, _, _ = _inbox_root(tmp_path)
    d = deps(root)
    k = ew_lane.kit()
    assert isinstance(d.budget, usage_ledger.UsageBudget)
    assert d.budget.cap == k.tree_budget(root, "EW").cap
    assert "cap " + str(d.budget.cap) in usage_ledger.gate_line(d.budget)


def test_spawn_block_opens_after_a_recorded_reset(tmp_path):
    root, _, _ = _inbox_root(tmp_path)
    d = deps(root)
    d.budget.clock = d.clock
    now = d.clock()
    control = root / "ops" / "loop" / "control"
    write_rows(control / "headless_usage.jsonl",
               [usage_row(now - 2 * HOUR - i, dur=1) for i in range(d.budget.cap)])
    assert ew_loop.spawn_block(root, d.budget, now) == "runs cap"
    _reset(control, now - HOUR)
    assert ew_loop.spawn_block(root, d.budget, now) is None


# ---------------------------------------------------------------- item 3

ROUTED = "2026-10-30-0900-from-MAIN-ORDER-to-EW-edit-rules.md"
ROUTED_TEXT = "1. Edit CLAUDE.md: add the rule.\n"


def _park(root, inbox, queued_ts, oid="Nabc123"):
    (inbox / ROUTED).write_text(ROUTED_TEXT, encoding="ascii")
    path = root / ew_loop.ORDERS_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"orders": [{"id": oid, "note": ROUTED, "text": ROUTED_TEXT,
                                            "queued_ts": queued_ts}]}))


def test_parked_order_and_its_age_under_48h_no_warning(tmp_path):
    root, inbox, _ = _inbox_root(tmp_path)
    _park(root, inbox, NOW - 30 * HOUR)
    rows = loop_inbox.parked_items(root, inbox, NOW)
    assert rows == [{"id": "Nabc123", "why": "CLAUDE.md", "age_h": 30.0}]
    doc = loop_inbox.parked_status(rows)
    assert doc["parked"] == rows and doc["parked_oldest_age_h"] == 30.0
    assert "parked_warning" not in doc


def test_warning_from_48h_names_the_item(tmp_path):
    root, inbox, _ = _inbox_root(tmp_path)
    _park(root, inbox, NOW - 48 * HOUR)
    doc = loop_inbox.parked_status(loop_inbox.parked_items(root, inbox, NOW))
    assert doc["parked_warning"] == "stale session: Nabc123 parked 48 h, needs CLAUDE.md"


def test_session_done_order_and_nothing_parked_show_nothing(tmp_path):
    root, inbox, _ = _inbox_root(tmp_path)
    assert loop_inbox.parked_status(loop_inbox.parked_items(root, inbox, NOW)) == {}
    _park(root, inbox, NOW - 90 * HOUR)
    assert loop_inbox.session_done(root, "Nabc123", "abc") is not None
    assert loop_inbox.parked_items(root, inbox, NOW) == []


def test_adjudicate_item_is_parked_oldest_first(tmp_path):
    root, inbox, _ = _inbox_root(tmp_path)
    _park(root, inbox, NOW - 5 * HOUR)
    ew_loop.Items(root).put({"id": "164", "state": "adjudicate", "finished": iso(NOW - 60 * HOUR)})
    ew_loop.Items(root).put({"id": "165", "state": "merged", "finished": iso(NOW - 80 * HOUR)})
    rows = loop_inbox.parked_items(root, inbox, NOW)
    assert [r["id"] for r in rows] == ["164", "Nabc123"]
    assert loop_inbox.parked_status(rows)["parked_warning"].startswith("stale session: 164 ")


def test_tick_write_puts_the_fields_in_inbox_status(tmp_path):
    root, inbox, _ = _inbox_root(tmp_path)
    d = deps(root, clock=lambda: NOW)
    d.budget.clock = d.clock
    _park(root, inbox, NOW - 50 * HOUR)
    t = ew_loop.Tick(d)
    doc = t.write("idle", "Idle", [], NOW)
    status = json.loads((root / d.kit.STATUS_REL).read_text())
    assert status["code"] == "EW" and status["schema"] == 1  # the kit's fields stay
    assert status["parked"][0]["id"] == "Nabc123"
    assert status["parked_oldest_age_h"] == 50.0
    assert status["parked_warning"].startswith("stale session: Nabc123 parked 50 h")
    assert any("stale session" in s for s in doc["log"])


def test_tick_write_leaves_the_kit_doc_alone_when_nothing_is_parked(tmp_path):
    root, _, _ = _inbox_root(tmp_path)
    d = deps(root, clock=lambda: NOW)
    d.budget.clock = d.clock
    ew_loop.Tick(d).write("idle", "Idle", [], NOW)
    status = json.loads((root / d.kit.STATUS_REL).read_text())
    assert not [k for k in status if k.startswith("parked")]


# ---------------------------------------------------------------- item 5

def test_spend_line_per_line_with_this_weeks_figures():
    rows = [usage_row(NOW - 10, cost_usd=1.5),
            usage_row(NOW - 20, note="lane-build-164", cost_usd=0.25),
            usage_row(NOW - 30, note="lane-data", cost_usd=2.0),
            usage_row(NOW - 40, note="lane-review-164", cost_usd=0.5),
            usage_row(NOW - 50, kind="inbox", note="n.md", cost_usd=0.1),
            usage_row(NOW - 60, kind="triage", note="n.md", cost_usd=0.05),
            usage_row(NOW - 70, note="lane-build", cost_usd=None),
            usage_row(NOW - 80, note="by-hand", cost_usd=3.0),
            usage_row(NOW - 8 * 86400, cost_usd=99.0)]
    line = usage_ledger.spend_text(rows, NOW)
    assert line.startswith("Spend 7d to ") and line.isascii() and "\n" not in line
    assert "$7.40 total" in line
    for part in ("build $1.75", "data $2.00", "review $0.50", "inbox $0.10", "triage $0.05",
                 "other $3.00", "1 unpriced"):
        assert part in line


# ---------------------------------------------------------------- item 6

def _transcript(config, sid, body=b"{}\n"):
    p = config / "projects" / "E--ew-worktrees-lane-0" / f"{sid}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    return p


def test_one_lane_in_twenty_first_sampled_retry_always(tmp_path):
    side, tree = tmp_path / "side", tmp_path / "tree"
    got = [lane_samples.begin(tree, sidecar=side) for _ in range(41)]
    assert [i for i, sid in enumerate(got) if sid] == [0, 20, 40]
    lanes = json.loads((side / lane_samples.SUB / "state.json").read_text())["lanes"]
    assert lane_samples.begin(tree, retry=True, sidecar=side)
    assert json.loads((side / lane_samples.SUB / "state.json").read_text())["lanes"] == lanes


def test_no_sidecar_or_a_sidecar_in_the_tree_means_no_sample(tmp_path):
    # conftest pins FLEET_SIDECAR_ROOT off, so the suite's default is no sidecar
    assert lane_samples.sample_dir() is None
    assert lane_samples.begin(tmp_path) is None
    assert lane_samples.finish(tmp_path, "sid", "x") is None
    inside = tmp_path / "tree" / "ops"
    assert lane_samples.begin(tmp_path / "tree", sidecar=inside) is None
    assert lane_samples.finish(tmp_path / "tree", "sid", "x", roots=[], sidecar=inside) is None
    assert not (inside / lane_samples.SUB).exists()


def test_finish_copies_the_transcript_to_the_sidecar_only(tmp_path):
    side, tree, cfg = tmp_path / "side", tmp_path / "tree", tmp_path / "cfg"
    tree.mkdir()
    src = _transcript(cfg, "sid-1", b'{"a": 1}\n')
    dest = lane_samples.finish(tree, "sid-1", "Nd11/eb1", roots=[cfg], sidecar=side,
                               clock=lambda: NOW)
    assert dest.parent == side / lane_samples.SUB / "samples"
    assert dest.name.endswith("-Nd11-eb1-sid-1.jsonl")
    assert dest.read_bytes() == src.read_bytes() and src.exists()
    assert list(tree.iterdir()) == []
    row = json.loads((side / lane_samples.SUB / "ledger.jsonl").read_text())
    assert row["event"] == "sample" and row["bytes"] == src.stat().st_size


def test_a_missing_transcript_is_a_ledger_line_not_a_failure(tmp_path):
    side = tmp_path / "side"
    (side / lane_samples.SUB).mkdir(parents=True)
    assert lane_samples.finish(tmp_path / "t", "gone", "x", roots=[tmp_path / "c"], sidecar=side,
                               clock=lambda: NOW) is None
    assert "no-transcript" in (side / lane_samples.SUB / "ledger.jsonl").read_text()


def _sampled(tree, side, cfg, n, start=0, size=100, recycle_fn=None):
    for i in range(start, start + n):
        _transcript(cfg, f"s{i}", b"x" * size)
        lane_samples.finish(tree, f"s{i}", "lane", roots=[cfg], sidecar=side,
                            clock=lambda i=i: NOW + i,
                            recycle_fn=recycle_fn or (lambda p: False))


def test_cap_set_once_after_the_first_twenty_then_oldest_recycled(tmp_path):
    side, tree, cfg = tmp_path / "side", tmp_path / "tree", tmp_path / "cfg"
    d = side / lane_samples.SUB
    _sampled(tree, side, cfg, 19, recycle_fn=lambda p: 1 / 0)
    assert not (d / "cap.json").exists()
    _sampled(tree, side, cfg, 1, start=19, recycle_fn=lambda p: 1 / 0)
    doc = json.loads((d / "cap.json").read_text())
    assert doc["cap_bytes"] == 4000 and doc["measured_n"] == 20 and doc["median_bytes"] == 100
    sent = []

    def fake_recycle(p):
        sent.append(p.name)
        os.remove(p)  # stands in for the Recycle Bin; finish never unlinks itself
        return True

    _sampled(tree, side, cfg, 25, start=20, recycle_fn=fake_recycle)
    held = lane_samples._samples(d)
    assert sum(p.stat().st_size for p in held) <= 4000 and len(sent) == 5
    assert all("-s" + str(i) + ".jsonl" in sent[i] for i in range(5))  # oldest first
    assert json.loads((d / "cap.json").read_text())["cap_bytes"] == 4000  # set once
    assert "recycled" in (d / "ledger.jsonl").read_text()


def test_a_recycle_that_fails_keeps_the_file(tmp_path):
    side, tree, cfg = tmp_path / "side", tmp_path / "tree", tmp_path / "cfg"
    d = side / lane_samples.SUB
    _sampled(tree, side, cfg, 45)  # the default fake leaves every file in place
    assert len(lane_samples._samples(d)) == 45
    assert "recycle-failed" in (d / "ledger.jsonl").read_text()


def test_config_roots_reads_route_accounts_and_env(tmp_path):
    route = tmp_path / "route.json"
    route.write_text(json.dumps({"version": 2, "accounts": [
        {"mode": "single", "config_dir": str(tmp_path / "acct")}, {"mode": "proxy"}]}))
    roots = lane_samples.config_roots({"CLAUDE_CONFIG_DIR": str(tmp_path / "env")}, route)
    assert roots[:2] == [tmp_path / "acct", tmp_path / "env"]
    assert roots[2].name == ".claude"


def _lane_fixture(tmp_path, monkeypatch, sample):
    """run_lane with fakes; the sampler's calls recorded."""
    calls = {"begin": [], "finish": [], "spawn": []}
    monkeypatch.setattr(lane_samples, "begin",
                        lambda root, retry=False, **k: calls["begin"].append(retry) or sample)
    monkeypatch.setattr(lane_samples, "finish",
                        lambda root, sid, label, **k: calls["finish"].append((sid, label)))
    wt = tmp_path / "wt"
    wt.mkdir()

    class Ctx:
        def __enter__(self):
            return {"index": 0, "worktree": str(wt)}

        def __exit__(self, *a):
            return False

    def spawn(root, code, prompt, **kw):
        calls["spawn"].append(kw)
        return {"rc": 0, "error": None}

    kw = dict(root=tmp_path, spawn=spawn, lane_ctx=lambda *a, **k: Ctx(),
              progress=lambda *a, **k: None, record=lambda *a, **k: None)
    return calls, kw


def test_sampled_lane_runs_with_a_session_id_and_is_copied_at_its_end(tmp_path, monkeypatch):
    calls, kw = _lane_fixture(tmp_path, monkeypatch, "sid-9")
    ew_lane.run_lane("build", "x", sample_retry=True, sample_label="164", **kw)
    assert calls["begin"] == [True]
    assert calls["spawn"][0]["session_id"] == "sid-9"
    assert calls["finish"] == [("sid-9", "164")]


def test_unsampled_lane_keeps_persistence_off(tmp_path, monkeypatch):
    calls, kw = _lane_fixture(tmp_path, monkeypatch, None)
    ew_lane.run_lane("build", "x", **kw)
    assert calls["begin"] == [False]
    assert "session_id" not in calls["spawn"][0] and "persist" not in calls["spawn"][0]
    assert calls["finish"] == [(None, "lane-build")]


def test_sample_retry_reaches_the_lane_from_the_worker(tmp_path):
    seen = {}

    def run_lane(lane, prompt, **kw):
        seen.update(kw)
        return {"rc": 0, "error": None, "worktree": str(tmp_path)}

    root, _, _ = _inbox_root(tmp_path)
    items = ew_loop.Items(root)
    items.put({"id": "012", "state": "dispatched", "attempts": 2, "lane": "build",
               "prompt": "x", "kind": "plan"})
    assert ew_loop.lane_worker("012", deps=deps(root), run_lane=run_lane) == 0
    assert seen["sample_retry"] is True and seen["sample_label"] == "012"
    items.put({"id": "013", "state": "dispatched", "attempts": 1, "lane": "build",
               "prompt": "x", "kind": "plan"})
    assert ew_loop.lane_worker("013", deps=deps(root), run_lane=run_lane) == 0
    assert seen["sample_retry"] is False


# ---------------------------------------------------------------- item 7

TIMED = re.compile(r"\b(?:monotonic|perf_counter|time)\(\)\s*-\s*\w+")


def test_every_timing_assert_goes_through_the_guard_budget():
    """FLEET-9: a wall-clock bound under load flakes; fleet_test_guard.budget scales it."""
    raw = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("assert ") and TIMED.search(line) \
                    and re.search(r"[<>]", line) and "budget(" not in line:
                raw.append(f"{path.name}:{n}")
    assert raw == []
