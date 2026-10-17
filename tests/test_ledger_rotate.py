"""Plan 138: tools/ledger_rotate.py moves old control-ledger rows and finished
progress files to archives. Fixtures live under tmp_path; nothing is deleted."""

import datetime as _dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import eta  # noqa: E402
import ledger_rotate  # noqa: E402
import usage_ledger  # noqa: E402

NOW = 1_790_000_000.0
DAY = 86400.0
CONTROL = Path("ops/loop/control")


def iso(epoch):
    return _dt.datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="seconds")


def local(epoch):
    return _dt.datetime.fromtimestamp(epoch).strftime("%Y-%m-%dT%H:%M:%S")


def month(epoch):
    return _dt.datetime.fromtimestamp(epoch).strftime("%Y%m")


def write_lines(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(ln.encode("ascii") + b"\n" for ln in lines))


def jl(rows):
    return [r if isinstance(r, str) else json.dumps(r, sort_keys=True) for r in rows]


def read_rows(path):
    if not path.exists():
        return []
    return [ln for ln in path.read_text(encoding="ascii").split("\n") if ln]


def control(root):
    return root / CONTROL


# ---------------------------------------------------------------- usage

def usage_rows():
    return jl([
        {"ts": iso(NOW - 60 * DAY), "duration_s": 10, "kind": "build"},
        {"ts": iso(NOW - 36 * DAY), "duration_s": 10, "kind": "inbox"},
        "{torn line",
        {"ts": iso(NOW - 20 * DAY), "duration_s": 10, "kind": "build"},
        {"ts": iso(NOW - 3600), "duration_s": 30, "kind": "build"},
        {"ts": iso(NOW - 600), "duration_s": 5, "kind": "triage"},
        {"note": "no timestamp"},
    ])


def test_usage_rows_older_than_35_days_move_to_a_monthly_archive(tmp_path):
    live = control(tmp_path) / "headless_usage.jsonl"
    rows = usage_rows()
    write_lines(live, rows)
    before = usage_ledger.run_starts(live, NOW)
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    assert res["headless_usage"] == 2
    assert read_rows(live) == rows[2:]  # torn and ts-less lines kept, order kept
    arch = control(tmp_path) / "archive"
    moved = [ln for f in sorted(arch.glob("headless_usage-*.jsonl")) for ln in read_rows(f)]
    assert moved == rows[:2]
    assert (arch / f"headless_usage-{month(NOW - 60 * DAY)}.jsonl").exists()
    assert usage_ledger.run_starts(live, NOW) == before  # 24 h governor unchanged


def test_usage_keeps_at_least_8_days_whatever_the_setting(tmp_path):
    live = control(tmp_path) / "headless_usage.jsonl"
    rows = jl([{"ts": iso(NOW - 7 * DAY), "kind": "build"},
               {"ts": iso(NOW - 9 * DAY), "kind": "build"}])
    write_lines(live, rows)
    plan = ledger_rotate.plan_jsonl(live, ledger_rotate.age_rule(1), NOW,
                                    min_keep_s=ledger_rotate.USAGE_MIN_KEEP_S)
    assert plan["keep"] == [rows[0].encode()]


def test_archive_appends_and_a_second_run_moves_nothing(tmp_path):
    live = control(tmp_path) / "headless_usage.jsonl"
    arch = control(tmp_path) / "archive" / f"headless_usage-{month(NOW - 60 * DAY)}.jsonl"
    write_lines(arch, ['{"old": "archived earlier"}'])
    write_lines(live, usage_rows())
    ledger_rotate.rotate(tmp_path, now=NOW)
    assert read_rows(arch)[0] == '{"old": "archived earlier"}'
    snap = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    assert ledger_rotate.total(res) == 0
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == snap


def test_a_concurrent_append_skips_the_file_and_loses_nothing(tmp_path):
    live = control(tmp_path) / "headless_usage.jsonl"
    rows = usage_rows()
    write_lines(live, rows)
    extra = json.dumps({"ts": iso(NOW), "kind": "build"})

    def grow():
        with live.open("ab") as fh:
            fh.write(extra.encode() + b"\n")

    n = ledger_rotate.rotate_jsonl(live, ledger_rotate.age_rule(35), NOW,
                                   control(tmp_path) / "archive", _before_replace=grow)
    assert n is None  # skipped: retried next run
    assert read_rows(live) == rows + [extra]
    assert not list((control(tmp_path) / "archive").glob("*.jsonl"))
    assert not list(live.parent.glob("*.tmp"))


def test_missing_files_are_nothing_to_do(tmp_path):
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    assert ledger_rotate.total(res) == 0 and res["skipped"] == []
    assert not (control(tmp_path) / "archive").exists()


# ---------------------------------------------------------------- timings

def test_timings_keep_newest_200_ok_per_kind_plus_the_last_30_days(tmp_path):
    live = control(tmp_path) / "timings.jsonl"
    rows = []
    for i in range(205):  # 205 old ok rows of kind a: the 5 oldest go
        rows.append({"kind": "a", "seconds": float(i), "ok": True, "ts": NOW - 90 * DAY + i})
    rows.append({"kind": "a", "seconds": 1.0, "ok": False, "ts": NOW - 40 * DAY})  # old fail goes
    rows.append({"kind": "a", "seconds": 2.0, "ok": False, "ts": NOW - 2 * DAY})  # young fail stays
    rows.append({"kind": "b", "seconds": 3.0, "ok": True, "ts": NOW - 400 * DAY})  # few b: stays
    rows = jl(rows) + ["torn{"]
    write_lines(live, rows)
    est = {k: eta.estimate(k, log=live) for k in ("a", "b", "c")}
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    assert res["timings"] == 6
    kept = read_rows(live)
    assert kept == rows[5:205] + rows[206:]
    assert {k: eta.estimate(k, log=live) for k in ("a", "b", "c")} == est
    moved = [ln for f in (control(tmp_path) / "archive").glob("timings-*.jsonl")
             for ln in read_rows(f)]
    assert sorted(moved) == sorted(rows[:5] + [rows[205]])


# ---------------------------------------------------------------- kit logs

def test_claims_gitlock_identity_keep_30_days(tmp_path):
    for name in ("claims", "gitlock", "identity"):
        rows = jl([{"at": local(NOW - 31 * DAY), "event": "old"},
                   {"at": local(NOW - 29 * DAY), "event": "young"}, "torn"])
        write_lines(control(tmp_path) / f"{name}.jsonl", rows)
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    for name in ("claims", "gitlock", "identity"):
        assert res[name] == 1
        assert [json.loads(r)["event"] for r in read_rows(control(tmp_path) / f"{name}.jsonl")
                if r != "torn"] == ["young"]


# ---------------------------------------------------------------- progress

def put(root, name, doc):
    p = control(root) / "progress" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="ascii")
    return p


def test_finished_progress_files_older_than_7_days_move_to_the_archive(tmp_path):
    old, young = iso(NOW - 8 * DAY), iso(NOW - 6 * DAY)
    put(tmp_path, "a.json", {"status": "done", "updated": old})
    put(tmp_path, "b.json", {"status": "failed", "updated": NOW - 8 * DAY})  # epoch form
    put(tmp_path, "c.json", {"status": "done", "updated": young})
    put(tmp_path, "d.json", {"status": "running", "updated": old})
    put(tmp_path, "e.json", {"status": "blocked", "updated": old})
    put(tmp_path, "loop.json", {"status": "done", "updated": old})
    put(tmp_path, "f.json", "{torn")
    put(tmp_path, "g.json", {"status": "done"})
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    assert res["progress"] == 2
    prog = control(tmp_path) / "progress"
    assert sorted(p.name for p in (prog / "archive").iterdir()) == ["a.json", "b.json"]
    assert sorted(p.name for p in prog.glob("*.json")) == [
        "c.json", "d.json", "e.json", "f.json", "g.json", "loop.json"]
    assert ledger_rotate.rotate(tmp_path, now=NOW)["progress"] == 0


def test_a_progress_name_already_archived_is_never_overwritten(tmp_path):
    put(tmp_path, "archive/a.json", {"first": 1})
    put(tmp_path, "a.json", {"status": "done", "updated": iso(NOW - 9 * DAY)})
    ledger_rotate.rotate(tmp_path, now=NOW)
    arch = control(tmp_path) / "progress" / "archive"
    assert json.loads((arch / "a.json").read_text()) == {"first": 1}
    assert len(list(arch.glob("a*.json"))) == 2


# ---------------------------------------------------------------- dry run, daily

def test_dry_run_writes_nothing(tmp_path):
    write_lines(control(tmp_path) / "headless_usage.jsonl", usage_rows())
    put(tmp_path, "a.json", {"status": "done", "updated": iso(NOW - 9 * DAY)})
    snap = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    res = ledger_rotate.rotate(tmp_path, now=NOW, dry_run=True)
    assert res["headless_usage"] == 2 and res["progress"] == 1
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == snap


def test_rotate_daily_runs_once_per_local_day(tmp_path):
    write_lines(control(tmp_path) / "headless_usage.jsonl", usage_rows())
    first = ledger_rotate.rotate_daily(tmp_path, now=NOW)
    assert first["headless_usage"] == 2
    write_lines(control(tmp_path) / "headless_usage.jsonl", usage_rows())
    assert ledger_rotate.rotate_daily(tmp_path, now=NOW + 60) is None
    assert ledger_rotate.rotate_daily(tmp_path, now=NOW + DAY)["headless_usage"] == 2


def test_rotate_daily_retries_the_same_day_after_a_skip(tmp_path, monkeypatch):
    write_lines(control(tmp_path) / "headless_usage.jsonl", usage_rows())
    real = ledger_rotate.rotate_jsonl
    monkeypatch.setattr(ledger_rotate, "rotate_jsonl", lambda *a, **k: None)
    res = ledger_rotate.rotate_daily(tmp_path, now=NOW)
    assert "headless_usage" in res["skipped"]
    monkeypatch.setattr(ledger_rotate, "rotate_jsonl", real)
    assert ledger_rotate.rotate_daily(tmp_path, now=NOW + 60)["headless_usage"] == 2


def test_summary_line_and_cli_dry_run(tmp_path, capsys):
    write_lines(control(tmp_path) / "headless_usage.jsonl", usage_rows())
    assert ledger_rotate.main(["--dry-run", "--root", str(tmp_path), "--now", str(NOW)]) == 0
    out = capsys.readouterr().out
    assert "headless_usage: 2" in out and "would move" in out
    assert len(read_rows(control(tmp_path) / "headless_usage.jsonl")) == 7
    assert ledger_rotate.summary({"headless_usage": 2, "timings": 0, "progress": 1,
                                  "skipped": ["claims"]}) == (
        "ledgers rotated: 2 row(s), 1 progress file(s) archived, skipped claims")
