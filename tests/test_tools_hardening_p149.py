"""Plan 149 hardening audit of tools/*.py: one regression test per FIXED
finding (docs/audit/20261017-tools.md). Synthetic data only."""

import io
import json
import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import eta  # noqa: E402
import ew_facts  # noqa: E402
import ew_lane  # noqa: E402
import ew_loop  # noqa: E402
import leak_sweep as ls  # noqa: E402
import ledger_rotate  # noqa: E402
import loop_base  # noqa: E402
import loop_inbox  # noqa: E402
import usage_ledger  # noqa: E402


# ---- TOOLS-01: eta.py - a non-finite or malformed row poisons every estimate

def test_tools01_record_refuses_non_finite_clamps_negative(tmp_path):
    log = tmp_path / "t.jsonl"
    for bad in (float("nan"), float("inf")):
        try:
            eta.record("k", bad, log=log)
        except ValueError:
            continue
        raise AssertionError(f"record accepted {bad!r}")
    assert not log.exists()
    assert eta.record("k", -1.0, log=log)["seconds"] == 0.0  # clock stepped back


def test_tools01_history_skips_bad_rows(tmp_path):
    log = tmp_path / "t.jsonl"
    log.write_text("\n".join([
        "5",
        '["k"]',
        '{"kind": "k", "ok": true, "seconds": "abc"}',
        '{"kind": "k", "ok": true, "seconds": NaN}',
        '{"kind": "k", "ok": true, "seconds": Infinity}',
        '{"kind": "k", "ok": true}',
        '{"kind": "k", "ok": true, "seconds": 10}',
    ]) + "\n", encoding="utf-8")
    est = eta.estimate("k", log=log)
    assert est == 10 and math.isfinite(est)
    assert eta.fmt(est) == "[~10s]"


def test_tools01_estimate_default_flag_without_value_is_usage():
    assert eta.main(["estimate", "k", "--default"]) == 64


# ---- TOOLS-02: loop_base.load_config - a config typo crashed every tick

def _cfg(tmp_path, doc):
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "local.json").write_text(json.dumps(doc), encoding="utf-8")
    return loop_base.load_config(tmp_path)


def test_tools02_non_object_config_falls_back_to_defaults(tmp_path):
    cfg = _cfg(tmp_path, [1, 2])
    assert cfg["tick_s"] == loop_base.TICK_S
    assert cfg["lane_timeout_s"] == loop_base.LANE_TIMEOUT_S


def test_tools02_bad_numbers_fall_back_per_key(tmp_path):
    cfg = _cfg(tmp_path, {"loop": {"tick_s": "15m", "lane_timeout_s": None,
                                   "max_notes_per_day": "six", "max_new_plans_per_day": -1}})
    assert cfg["tick_s"] == loop_base.TICK_S
    assert cfg["lane_timeout_s"] == loop_base.LANE_TIMEOUT_S
    assert cfg["max_notes_per_day"] == loop_base.DEFAULT_MAX_NOTES
    assert cfg["max_new_plans_per_day"] == loop_base.DEFAULT_MAX_PLANS


def test_tools02_valid_numbers_still_apply(tmp_path):
    cfg = _cfg(tmp_path, {"loop": {"tick_s": 600, "lane_timeout_s": 3600,
                                   "max_notes_per_day": 9, "max_new_plans_per_day": 0}})
    assert (cfg["tick_s"], cfg["lane_timeout_s"]) == (600, 3600)
    assert cfg["max_notes_per_day"] == loop_base.DEFAULT_MAX_NOTES  # never raised
    assert cfg["max_new_plans_per_day"] == 0


# ---- TOOLS-03: non-object roster / orders JSON crashed the inbox pass

def _dest(roster_doc, tmp_path):
    p = tmp_path / "roster.json"
    p.write_text(json.dumps(roster_doc), encoding="utf-8")
    fake = SimpleNamespace(cfg={"dest_inboxes": {}, "roster": str(p)},
                           d=SimpleNamespace(roster_path=None))
    return loop_inbox.InboxMixin.dest_inbox(fake, "MAIN")


def test_tools03_malformed_roster_is_no_destination(tmp_path):
    assert _dest([1, 2], tmp_path) is None
    assert _dest({"repos": 5}, tmp_path) is None
    assert _dest({"repos": [{"code": "MAIN", "inbox": "inbox-dir"}]}, tmp_path) == \
        Path("inbox-dir")


def test_tools03_malformed_orders_file_is_no_order(tmp_path):
    p = tmp_path / loop_base.ORDERS_REL
    p.parent.mkdir(parents=True)
    for doc in ([{"id": "N1"}], {"orders": 5}):
        p.write_text(json.dumps(doc), encoding="utf-8")
        assert loop_inbox.queued_orders(tmp_path) == []


# ---- TOOLS-04: leak_sweep - a C-quoted diff path skipped its added lines

def test_tools04_quoted_diff_path_lines_are_scanned():
    mail = "ping someone" + "@" + "mail.test.org"
    diff = ('+++ "b/docs/caf\\303\\251.md"\n@@\n+' + mail + "\n")
    added = ls._added_lines(diff)
    assert list(added) == ["docs/caf\u00e9.md"]
    kinds = [k for _, _, k in ls.scan_diff(diff, [])]
    assert kinds == ["email"]


def test_tools04_plain_and_dev_null_headers_unchanged():
    diff = "+++ b/a.md\n@@\n+x\n+++ /dev/null\n@@\n+y\n"
    assert ls._added_lines(diff) == {"a.md": "x"}


# ---- TOOLS-05: leak_sweep - a non-object needle config was a traceback, not FAULT

def test_tools05_non_object_needle_config_is_fault(tmp_path):
    cfg = tmp_path / "c.json"
    for doc in ('["abc"]', '{"needles": "abc"}'):
        cfg.write_text(doc, encoding="utf-8")
        try:
            ls.load_needles(cfg, environ={})
        except ValueError:
            continue
        raise AssertionError(f"{doc} must FAULT")


# ---- TOOLS-06: out-of-range timestamps raised instead of reading as unknown

def test_tools06_epoch_of_out_of_range_is_none():
    for text in ("0001-01-01T00:00:00", "9999-12-31T23:59:59"):
        v = loop_base.epoch_of(text)
        assert v is None or math.isfinite(v)


def test_tools06_profile_age_out_of_range_is_none():
    import profile_selfhost  # noqa: PLC0415 - imports server.ew
    v = profile_selfhost._age_s("0001-01-01T00:00:00", lambda: 1.7e9)
    assert v is None or math.isfinite(v)


def test_tools06_usage_epoch_out_of_range_is_none(tmp_path):
    p = tmp_path / "u.jsonl"
    p.write_text('{"ts": "0001-01-01T00:00:00", "duration_s": 1}\n', encoding="utf-8")
    assert usage_ledger.run_starts(p, 1.7e9) == []


def test_tools06_rotate_keeps_garbage_numeric_ts(tmp_path):
    ctl = tmp_path / ledger_rotate.CONTROL_REL
    ctl.mkdir(parents=True)
    rows = ['{"kind": "x", "ok": false, "ts": -1e300}',
            '{"kind": "x", "ok": false, "ts": 1e300}']
    (ctl / "timings.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    res = ledger_rotate.rotate(tmp_path, now=1.7e9)
    assert res["skipped"] == [] and res["timings"] == 0
    assert (ctl / "timings.jsonl").read_text(encoding="utf-8").splitlines() == rows


# ---- TOOLS-07: ew_lane main exited 0 on a run its own record counts failed

def test_tools07_main_fails_on_error_with_rc_zero(tmp_path, monkeypatch):
    pf = tmp_path / "p.txt"
    pf.write_text("x", encoding="utf-8")
    monkeypatch.setattr(ew_lane, "run_lane",
                        lambda *a, **k: {"rc": 0, "error": "boom", "worktree": "w"})
    assert ew_lane.main(["run", "build", "--prompt-file", str(pf)]) == 1
    monkeypatch.setattr(ew_lane, "run_lane",
                        lambda *a, **k: {"rc": 0, "error": None, "worktree": "w"})
    assert ew_lane.main(["run", "build", "--prompt-file", str(pf)]) == 0


# ---- TOOLS-08: a malformed loop.json crashed the checklist / tick write

def test_tools08_fire_count_tolerates_bad_docs():
    assert ew_loop.fire_count({"fire": 4}) == 5
    for prev in ({"fire": "x"}, {"fire": None}, [3], None, {"fire": [1]}):
        assert ew_loop.fire_count(prev) == 1


def test_tools08_render_checklist_tolerates_bad_docs():
    for doc in ([1], {"fire": "x", "checklist": 5}, None):
        out = ew_loop.render_checklist(doc)
        assert "/done" in out


# ---- TOOLS-09: a note removed mid-listing crashed the inbox pass

def test_tools09_inbox_names_skip_vanished(tmp_path, monkeypatch):
    for n in ("a.md", "b.md", ".hidden.md"):
        (tmp_path / n).write_text(n, encoding="utf-8")
    real = Path.stat

    def gone(self, *a, **k):  # b.md vanishes after is_file() saw it
        if self.name == "b.md":
            raise FileNotFoundError(str(self))
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "is_file", lambda self: os.path.isfile(self))
    monkeypatch.setattr(Path, "stat", gone)
    assert loop_inbox.inbox_names(tmp_path) == ["a.md"]


# ---- TOOLS-10: ew_facts edit guard crashed on a non-string file_path

def test_tools10_edit_guard_non_string_path(monkeypatch):
    for payload in ({"tool_input": {"file_path": 5}}, {"tool_input": [1]}, [1]):
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        assert ew_facts.edit_guard() == 0


# ---- TOOLS-11: an empty ci run command was an IndexError, not fail closed

def test_tools11_empty_gate_command_fails_closed(tmp_path):
    wf = tmp_path / ew_loop.CI_WORKFLOW_REL
    wf.parent.mkdir(parents=True)
    wf.write_text("jobs:\n  t:\n    steps:\n      - run: \"\"\n", encoding="utf-8")
    ran = []
    ok, detail = ew_loop._gates(tmp_path, run=lambda argv, cwd: ran.append(argv) or (0, ""))
    assert not ok and "fail closed" in detail and ran == []
