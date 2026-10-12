import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import eta  # noqa: E402


def test_fmt_units():
    assert eta.fmt(42) == "[~42s]"
    assert eta.fmt(600) == "[~10m]"
    assert eta.fmt(3 * 3600) == "[~3h]"


def test_estimate_median_of_last_five_ok(tmp_path):
    log = tmp_path / "t.jsonl"
    assert eta.estimate("pytest", default=33, log=log) == 33
    for s in (100, 1, 2, 3, 4, 5):
        eta.record("pytest", s, log=log)
    eta.record("pytest", 999, ok=False, log=log)
    eta.record("other", 7, log=log)
    assert eta.estimate("pytest", log=log) == 3


def test_torn_line_is_skipped(tmp_path):
    log = tmp_path / "t.jsonl"
    eta.record("x", 10, log=log)
    with log.open("a") as fh:
        fh.write('{"kind": "x", "sec')
    assert eta.estimate("x", log=log) == 10


def test_resolve_cmd_uses_which_for_shims(monkeypatch):
    # Windows: npm is npm.cmd; subprocess without a shell cannot find it.
    monkeypatch.setattr(eta.shutil, "which", lambda name: "/bin/" + name + ".cmd")
    assert eta.resolve_cmd(["npm", "test"]) == ["/bin/npm.cmd", "test"]


def test_resolve_cmd_leaves_unknown_alone(monkeypatch):
    monkeypatch.setattr(eta.shutil, "which", lambda name: None)
    assert eta.resolve_cmd(["nope", "-x"]) == ["nope", "-x"]


def test_lane_aliases_read_the_lane_run_kind(tmp_path):
    # hand-off session 28: `eta.py estimate build` read the 60 s default while
    # the lanes record lane-<lane>-code; the short lane name is an alias.
    log = tmp_path / "t.jsonl"
    for s in (400, 500, 600):
        eta.record("lane-review-code", s, log=log)
    assert eta.canonical("review") == "lane-review-code"
    assert eta.estimate("review", log=log) == 500
    assert eta.canonical("pytest") == "pytest"


def test_measured_defaults_replace_flat_sixty(tmp_path):
    # measured medians (session 29) of real lane runs and loop items; a kind
    # with no history starts from its own measured default, never 60 s.
    log = tmp_path / "empty.jsonl"
    for kind in ("build", "data", "review", "lane-build-code", "item-plan"):
        assert eta.estimate(kind, log=log) >= 200
    assert eta.estimate("item-plan", log=log) > eta.estimate("item-resolve", log=log)
    assert eta.estimate("unknown-kind", log=log) == eta.DEFAULT_S
    assert eta.estimate("item-plan", default=7, log=log) == 7


def test_cli_estimate_uses_alias(tmp_path, monkeypatch, capsys):
    log = tmp_path / "t.jsonl"
    monkeypatch.setattr(eta, "LOG", log)
    eta.record("lane-data-code", 900, log=log)
    assert eta.main(["estimate", "data"]) == 0
    assert capsys.readouterr().out.strip() == "[~15m]"
