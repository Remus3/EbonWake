"""Plan 130: curated official known-issue windows (data/known_issues.json),
GET /api/known-issues?area=, and suspect XP samples kept out of the rate.

Read-only data; nothing is fetched (plan 064 owns notice import). Every clock
is injected; all times are UTC.
"""

import datetime as dt
import http.client
import json
import threading

import pytest

from server.ew import app as ewapp
from server.ew import knownissues, leveling
from server.ew.store import Store

UTC = dt.timezone.utc
FROM = "2026-10-08T00:00:00+00:00"
UNTIL = "2026-10-15T00:00:00+00:00"


def _row(**kw):
    r = {"id": "x-issue", "title": "Trading EXP under-granted", "affects": ["leveling"],
         "from": FROM, "until": UNTIL, "source": "NA Known Issues notice 184, read 2026-10-14",
         "verified": True}
    r.update(kw)
    return r


def _at(s):
    return dt.datetime.fromisoformat(s)


# --- data file ---------------------------------------------------------------

def test_tracked_file_loads_and_is_ascii():
    raw = knownissues.FILE.read_bytes()
    assert all(b < 128 for b in raw) and b"\r" not in raw
    rows = knownissues.load()
    ids = {r["id"] for r in rows}
    assert {"trading-exp-shortfall", "lv59-quest-exp-stall", "season-fishing-exp-over",
            "agris-fever-cost-change"} <= ids
    for r in rows:
        assert set(r["affects"]) <= set(knownissues.AREAS) and r["affects"]
        assert "184" in r["source"] and "2026-10-14" in r["source"]
        assert r["kind"] in knownissues.KINDS


def test_tracked_seed_shapes():
    rows = {r["id"]: r for r in knownissues.load()}
    agris = rows["agris-fever-cost-change"]
    assert agris["kind"] == "change" and "enhance" in agris["affects"]
    assert agris["from"] == "2026-10-15T00:00:00+00:00"
    lv59 = rows["lv59-quest-exp-stall"]
    assert lv59["level_min"] == lv59["level_max"] == 59 and lv59["until"] is None
    # Trading EXP is life-skill EXP: it never touches combat level samples.
    assert "leveling" not in rows["trading-exp-shortfall"]["affects"]
    assert rows["season-fishing-exp-over"]["exclude_samples"] is False


@pytest.mark.parametrize("bad", [
    {"id": "Bad Id"}, {"title": ""}, {"title": "caf" + chr(233)}, {"affects": []},
    {"affects": ["pvp"]}, {"affects": ["market", "market"]}, {"from": "2026-10-08"},
    {"until": "2026-10-01T00:00:00+00:00"}, {"until": FROM}, {"verified": "yes"},
    {"kind": "rumour"}, {"source": ""}, {"exclude_samples": 1}, {"level_min": 0},
    {"level_min": 60, "level_max": 59}, {"bogus": 1},
])
def test_validate_rejects(bad):
    with pytest.raises(ValueError):
        knownissues.validate(_row(**bad))


def test_validate_defaults_and_normalizes_utc():
    r = knownissues.validate(_row(**{"from": "2026-10-07T17:00:00-07:00", "until": None}))
    assert r["from"] == FROM and r["until"] is None
    assert r["kind"] == "defect" and r["exclude_samples"] is True
    assert r["level_min"] is None and r["level_max"] is None


def test_load_rejects_duplicate_ids(tmp_path):
    p = tmp_path / "k.json"
    p.write_text(json.dumps([_row(), _row()]), encoding="ascii")
    with pytest.raises(ValueError):
        knownissues.load(p)


# --- active(now, area) ---------------------------------------------------------

def test_window_edges_inclusive_from_exclusive_until():
    rows = [knownissues.validate(_row())]
    before = _at(FROM) - dt.timedelta(seconds=1)
    assert knownissues.active(before, rows=rows) == []
    assert [r["state"] for r in knownissues.active(_at(FROM), rows=rows)] == ["active"]
    last = _at(UNTIL) - dt.timedelta(seconds=1)
    assert len(knownissues.active(last, rows=rows)) == 1
    assert knownissues.active(_at(UNTIL), rows=rows) == []


def test_open_ended_row_stays_active():
    rows = [knownissues.validate(_row(until=None))]
    assert len(knownissues.active(_at(FROM) + dt.timedelta(days=400), rows=rows)) == 1


def test_area_filter():
    rows = [knownissues.validate(_row(id="a", affects=["leveling", "trading"])),
            knownissues.validate(_row(id="b", affects=["market"]))]
    now = _at(FROM)
    assert [r["id"] for r in knownissues.active(now, "leveling", rows)] == ["a"]
    assert [r["id"] for r in knownissues.active(now, "trading", rows)] == ["a"]
    assert [r["id"] for r in knownissues.active(now, "market", rows)] == ["b"]
    assert knownissues.active(now, "books", rows) == []
    assert [r["id"] for r in knownissues.active(now, None, rows)] == ["a", "b"]
    with pytest.raises(ValueError):
        knownissues.active(now, "pvp", rows)


def test_change_row_pending_then_applied():
    rows = [knownissues.validate(_row(id="agris", kind="change", affects=["enhance"],
                                      **{"from": UNTIL, "until": "2026-10-29T00:00:00+00:00"}))]
    pend = knownissues.active(_at(FROM), "enhance", rows)
    assert [r["state"] for r in pend] == ["pending"]
    assert [r["state"] for r in knownissues.active(_at(UNTIL), "enhance", rows)] == ["applied"]
    assert knownissues.active(_at("2026-10-29T00:00:00+00:00"), "enhance", rows) == []


# --- suspect samples -------------------------------------------------------------

def test_suspect_only_inside_a_leveling_window_and_level_range():
    rows = [knownissues.validate(_row(id="lv59", until=None, level_min=59, level_max=59)),
            knownissues.validate(_row(id="trade", affects=["trading"])),
            knownissues.validate(_row(id="fish", exclude_samples=False)),
            knownissues.validate(_row(id="agris", kind="change"))]
    inside = _at(FROM) + dt.timedelta(hours=1)
    assert knownissues.suspect(rows, inside, 59) == "lv59"
    assert knownissues.suspect(rows, inside, 60) is None
    assert knownissues.suspect(rows, _at(FROM) - dt.timedelta(seconds=1), 59) is None


def _sample(when, level, pct):
    return {"ts": when.isoformat(), "level": level, "pct": pct}


def test_suspect_sample_excluded_from_rate_and_shown(tmp_path):
    t0 = _at(FROM) - dt.timedelta(hours=3)
    now = t0 + dt.timedelta(hours=4)
    rows = [knownissues.validate(_row(id="stall", until=None, level_min=59, level_max=59))]
    svc = leveling.LevelingService(Store(tmp_path / "s"), clock=lambda: now.timestamp(),
                                   epochs=[], deadlines=[], issues=rows)
    svc.store.put("leveling", {"samples": [
        _sample(t0, 58, 10.0), _sample(t0 + dt.timedelta(hours=1), 58, 14.0),
        _sample(_at(FROM) + dt.timedelta(minutes=30), 59, 99.99),
        _sample(_at(FROM) + dt.timedelta(minutes=50), 59, 99.99)]})
    v = svc.view()
    # only the two Lv 58 samples count: 4 %/h, not dragged down by the stall
    assert v["rate_pct_h"] == pytest.approx(4.0)
    tags = [s["suspect"] for s in v["samples"]]
    assert tags == ["stall", "stall", None, None]  # newest first


def test_no_issue_rows_leaves_rate_unchanged(tmp_path):
    t0 = _at(FROM)
    svc = leveling.LevelingService(Store(tmp_path / "s"),
                                   clock=lambda: (t0 + dt.timedelta(hours=2)).timestamp(),
                                   epochs=[], deadlines=[], issues=[])
    svc.store.put("leveling", {"samples": [_sample(t0, 59, 10.0),
                                           _sample(t0 + dt.timedelta(hours=1), 59, 12.0)]})
    v = svc.view()
    assert v["rate_pct_h"] == pytest.approx(2.0)
    assert [s["suspect"] for s in v["samples"]] == [None, None]


# --- route ---------------------------------------------------------------------

@pytest.fixture()
def ksrv(tmp_path):
    when = _at("2026-10-16T00:00:00+00:00").timestamp()
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", commit="a" * 40,
                          sse_interval=0.05, market_seed=[], leveling_clock=lambda: when,
                          profile_cfg={})
    t = threading.Thread(target=s.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()
    yield s
    s.shutdown()
    s.server_close()


def _get(s, path):
    c = http.client.HTTPConnection("127.0.0.1", s.server_address[1], timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    out = r.read()
    c.close()
    return r.status, json.loads(out)


@pytest.mark.server
def test_route_known_issues(ksrv):
    st, doc = _get(ksrv, "/api/known-issues?area=enhance")
    assert st == 200 and doc["area"] == "enhance" and doc["error"] is None
    agris = [r for r in doc["issues"] if r["id"] == "agris-fever-cost-change"]
    assert agris and agris[0]["state"] == "applied"
    assert all("enhance" in r["affects"] for r in doc["issues"])
    st, doc = _get(ksrv, "/api/known-issues")
    assert st == 200 and doc["area"] is None
    assert "trading-exp-shortfall" in {r["id"] for r in doc["issues"]}
    st, doc = _get(ksrv, "/api/known-issues?area=pvp")
    assert st == 400
