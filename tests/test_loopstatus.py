"""Plan 136: the loop status summary (server/ew/loopstatus.py) and GET /api/loop.
Fixture control trees live under tmp_path only; nothing reads the real
ops/loop/control/."""

import datetime as dt
import http.client
import json
import threading

import pytest

from server.ew import app as ewapp
from server.ew import loopstatus as ls
from ew_testkit import offline_market

NOW = 1_790_000_000.0


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).replace(microsecond=0).isoformat()


def _ctl(root):
    p = root / "ops" / "loop" / "control"
    (p / "progress").mkdir(parents=True, exist_ok=True)
    (p / "loop_items").mkdir(parents=True, exist_ok=True)
    return p


def _loop(root, age_s=60, state="running", eta_s=900, checklist=None, fire=7, tick_s=12.5):
    doc = {"task": "loop", "pct": 100, "step": "x", "eta_s": eta_s, "status": "done",
           "updated": _iso(NOW - age_s), "state": state, "fire": fire, "tick_s": tick_s,
           "log": [], "checklist": checklist or []}
    (_ctl(root) / "progress" / "loop.json").write_text(json.dumps(doc), encoding="utf-8")


def _item(root, iid, state, **kw):
    rec = dict({"id": iid, "state": state, "title": f"title {iid}",
                "updated": _iso(NOW - 300)}, **kw)
    (_ctl(root) / "loop_items" / f"{iid}.json").write_text(json.dumps(rec), encoding="utf-8")


def test_missing_tree_is_unknown_never_raises(tmp_path):
    s = ls.summary(tmp_path, NOW)
    assert s["state"] == "unknown"
    assert s["halted"] is False and s["stale"] is False and s["backoff_until"] is None
    assert s["in_flight"] == [] and s["stuck"] == [] and s["counts"] == {}
    assert s["last_tick_utc"] is None and s["tick_age_s"] is None


def test_torn_loop_json_is_unknown(tmp_path):
    (_ctl(tmp_path) / "progress" / "loop.json").write_text("{\"state\": ", encoding="utf-8")
    assert ls.summary(tmp_path, NOW)["state"] == "unknown"
    (_ctl(tmp_path) / "progress" / "loop.json").write_text("[1, 2]", encoding="utf-8")
    assert ls.summary(tmp_path, NOW)["state"] == "unknown"


def test_fresh_tick_fields(tmp_path):
    _loop(tmp_path, age_s=120, state="idle", fire=41, tick_s=8.0)
    s = ls.summary(tmp_path, NOW)
    assert s["state"] == "idle" and s["fire"] == 41 and s["tick_s"] == 8.0
    assert s["tick_age_s"] == 120 and s["last_tick_utc"] == _iso(NOW - 120)
    assert s["stale"] is False and s["eta_s"] == 900


def test_stale_when_older_than_twice_eta(tmp_path):
    _loop(tmp_path, age_s=1800, state="running")
    assert ls.summary(tmp_path, NOW)["stale"] is False  # exactly 2x is not stale
    _loop(tmp_path, age_s=1801, state="running")
    s = ls.summary(tmp_path, NOW)
    assert s["stale"] is True and s["state"] == "stale"
    _loop(tmp_path, age_s=700, eta_s=300)
    assert ls.summary(tmp_path, NOW)["stale"] is True


def test_bad_updated_or_eta_falls_back(tmp_path):
    _loop(tmp_path, age_s=10, eta_s="soon")
    assert ls.summary(tmp_path, NOW)["eta_s"] == ls.TICK_S
    doc = json.loads((_ctl(tmp_path) / "progress" / "loop.json").read_text())
    doc["updated"] = "yesterday"
    (_ctl(tmp_path) / "progress" / "loop.json").write_text(json.dumps(doc))
    s = ls.summary(tmp_path, NOW)
    assert s["tick_age_s"] is None and s["stale"] is True and s["state"] == "stale"


def test_halt_file_wins(tmp_path):
    _loop(tmp_path, age_s=5000, state="running")
    (_ctl(tmp_path) / "HALT").write_text("", encoding="utf-8")
    s = ls.summary(tmp_path, NOW)
    assert s["halted"] is True and s["state"] == "halted" and s["stale"] is True


def test_halt_without_loop_json(tmp_path):
    (_ctl(tmp_path) / "HALT").write_text("", encoding="utf-8")
    s = ls.summary(tmp_path, NOW)
    assert s["halted"] is True and s["state"] == "halted"


def test_backoff_active_and_expired(tmp_path):
    _loop(tmp_path)
    bp = _ctl(tmp_path) / "backoff.json"
    bp.write_text(json.dumps({"delay_s": 1800, "until": NOW + 600, "reason": "usage limit"}))
    s = ls.summary(tmp_path, NOW)
    assert s["backoff_until"] == _iso(NOW + 600) and s["state"] == "backoff"
    assert s["backoff_reason"] == "usage limit"
    bp.write_text(json.dumps({"delay_s": 0, "until": 0}))
    s = ls.summary(tmp_path, NOW)
    assert s["backoff_until"] is None and s["state"] == "running"
    bp.write_text("{torn")
    assert ls.summary(tmp_path, NOW)["backoff_until"] is None


def test_stuck_in_flight_and_counts(tmp_path):
    _loop(tmp_path, checklist=[
        {"id": "P136", "task": "Loop status card", "state": "builder running", "eta_s": 240},
        {"id": "P137", "task": "Other", "state": "reviewing", "eta_s": 0}])
    _item(tmp_path, "P130", "adjudicate")
    _item(tmp_path, "P131", "gave-up", error="out of attempts")
    _item(tmp_path, "P132", "merge-conflict")
    _item(tmp_path, "P133", "blocked", needs=["120", "121"])
    _item(tmp_path, "P134", "merged")
    _item(tmp_path, "P135", "merged")
    _item(tmp_path, "P136", "dispatched", lane=1, dispatched=_iso(NOW - 200))
    _item(tmp_path, "P137", "ran", lane=2)
    s = ls.summary(tmp_path, NOW)
    assert [x["id"] for x in s["stuck"]] == ["P130", "P131", "P132", "P133"]
    assert s["stuck"][0] == {"id": "P130", "state": "adjudicate", "since": _iso(NOW - 300),
                             "title": "title P130"}
    assert s["stuck"][3]["needs"] == ["120", "121"]
    assert s["stuck"][1]["error"] == "out of attempts"
    assert [x["id"] for x in s["in_flight"]] == ["P136", "P137"]
    f = s["in_flight"][0]
    assert f["lane"] == 1 and f["state"] == "dispatched"
    assert f["line"] == "builder running, ~4m"
    assert s["in_flight"][1]["line"] == "reviewing"
    assert s["counts"] == {"adjudicate": 1, "gave-up": 1, "merge-conflict": 1, "blocked": 1,
                           "merged": 2, "dispatched": 1, "ran": 1}


def test_torn_item_files_are_skipped(tmp_path):
    _loop(tmp_path)
    _item(tmp_path, "P130", "adjudicate")
    (_ctl(tmp_path) / "loop_items" / "P999.json").write_text("{torn")
    (_ctl(tmp_path) / "loop_items" / "P998.json").write_text("[]")
    s = ls.summary(tmp_path, NOW)
    assert [x["id"] for x in s["stuck"]] == ["P130"] and s["counts"] == {"adjudicate": 1}


def test_summary_never_writes(tmp_path):
    _loop(tmp_path)
    _item(tmp_path, "P130", "adjudicate")
    before = sorted((p.relative_to(tmp_path), p.stat().st_mtime_ns)
                    for p in tmp_path.rglob("*"))
    ls.summary(tmp_path, NOW)
    after = sorted((p.relative_to(tmp_path), p.stat().st_mtime_ns)
                   for p in tmp_path.rglob("*"))
    assert before == after


def test_main_root_follows_worktree_gitdir_file(tmp_path):
    main = tmp_path / "main"
    (main / ".git" / "worktrees" / "lane-1").mkdir(parents=True)
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text("gitdir: " + str(main / ".git" / "worktrees" / "lane-1") + "\n")
    assert ls.main_root(wt) == main
    assert ls.main_root(main) == main
    assert ls.main_root(tmp_path / "plain") == tmp_path / "plain"


def test_main_root_other_gitdir_shapes_are_their_own_root(tmp_path):
    # plan 150 coverage: a gitdir that is not <x>/.git/worktrees/<n> (a submodule)
    # and a .git file without the gitdir: prefix both keep the root
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text("gitdir: " + str(tmp_path / "m" / ".git" / "modules" / "x") + "\n")
    assert ls.main_root(wt) == wt
    (wt / ".git").write_text("junk\n")
    assert ls.main_root(wt) == wt


def test_cache_holds_for_ttl():
    calls = []
    clock = [NOW]
    c = ls.LoopStatus("unused", clock=lambda: clock[0],
                      summarize=lambda root, now: calls.append(now) or {"n": len(calls)})
    assert c.view() == {"n": 1}
    clock[0] += 9
    assert c.view() == {"n": 1}
    clock[0] += 2
    assert c.view() == {"n": 2}


# ---------------------------------------------------------------- GET /api/loop

@pytest.fixture
def srv(tmp_path):
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", commit="a" * 40,
                          market_seed=[], profile_cfg={}, config_path=tmp_path / "local.json",
                          market_client=offline_market(tmp_path))
    t = threading.Thread(target=s.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()
    yield s
    s.shutdown()
    s.server_close()


def _req(s, method, path):
    c = http.client.HTTPConnection("127.0.0.1", s.server_address[1], timeout=5)
    c.request(method, path)
    r = c.getresponse()
    out = json.loads(r.read().decode("utf-8"))
    c.close()
    return r.status, out


@pytest.mark.server
def test_route_loop_unknown_then_halted(srv, tmp_path):
    code, body = _req(srv, "GET", "/api/loop")
    assert code == 200 and body["state"] == "unknown"
    _loop(tmp_path, age_s=10)
    _item(tmp_path, "P130", "adjudicate")
    (_ctl(tmp_path) / "HALT").write_text("")
    srv.loopstatus.clear()
    code, body = _req(srv, "GET", "/api/loop")
    assert code == 200 and body["state"] == "halted" and body["halted"] is True
    assert [x["id"] for x in body["stuck"]] == ["P130"]


@pytest.mark.server
def test_route_loop_has_no_post(srv):
    code, _ = _req(srv, "POST", "/api/loop")
    assert code in (403, 404, 405)
