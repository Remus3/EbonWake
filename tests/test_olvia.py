"""Plan 170: Olvia Academy semester epoch - semester table, per-semester
enrolment check (plan 024), boundary stale-mark of typed lecture progress
(plan 079 ledger) and the before-maintenance digest line (plan 074).

Pure functions plus store-backed services over tmp_path; nothing reads the
game, the network or a real config file.
"""

import datetime as dt
import http.client
import json
import threading

import pytest

from server.ew import leveling, levels, maintdigest, olvia
from server.ew import overrides as ov
from server.ew.store import Store

UTC = dt.timezone.utc
S4 = {"number": 4, "start_utc": "2026-11-12T07:00:00+00:00",
      "end_utc": "2027-02-25T07:00:00+00:00",
      "weekly_quests_end_utc": "2027-02-24T23:59:00+00:00", "needs_level": 60,
      "graduation_reset": True, "source": "Global Lab 2026-11-06", "verified": False}
S5 = dict(S4, number=5, start_utc="2027-02-25T07:00:00+00:00",
          end_utc="2027-06-03T07:00:00+00:00",
          weekly_quests_end_utc="2027-06-02T23:59:00+00:00")
BEFORE = dt.datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
AFTER = dt.datetime(2026, 11, 12, 10, 0, tzinfo=UTC)
POLICY = ov.clean_policy({"keys": {
    olvia.LECTURE_KEY: {"label": "Olvia lectures", "expiry": "days:120", "cards": ["leveling"]}}})


class Clock:
    def __init__(self, when):
        self.t = when.timestamp()

    def __call__(self):
        return self.t

    def to(self, when):
        self.t = when.timestamp()


def _svc(tmp_path, when, rows=None):
    clock = Clock(when)
    led = ov.OverrideLedger(Store(tmp_path / "store"), clock=clock, policy=POLICY)
    return olvia.OlviaService(led, rows=[S4] if rows is None else rows, clock=clock), clock, led


# --- semester table ---------------------------------------------------------------

def test_tracked_table_is_ascii_valid_and_holds_semester_4():
    raw = olvia.DATA_FILE.read_bytes()
    assert raw.isascii() and b"\r" not in raw
    rows = olvia.load()
    s4 = next(r for r in rows if r["number"] == 4)
    assert s4["start_utc"].startswith("2026-11-12")
    assert s4["end_utc"].startswith("2027-02-25")
    assert s4["weekly_quests_end_utc"] == "2027-02-24T23:59:00+00:00"
    assert s4["graduation_reset"] is True and s4["needs_level"] == 60
    assert s4["verified"] is False and s4["source"]


@pytest.mark.parametrize("bad", [
    dict(S4, weekly_quests_end_utc="2027-03-01T00:00:00+00:00"),  # after the end
    dict(S4, weekly_quests_end_utc=S4["start_utc"]),
    dict(S4, needs_level=99), dict(S4, number=0), dict(S4, verified="no"),
    dict(S4, source=""), dict(S4, start_utc="2026-11-12"), dict(S4, extra=1),
])
def test_bad_rows_are_refused(bad):
    with pytest.raises(ValueError):
        olvia.check([bad])


def test_overlapping_or_duplicate_semesters_are_refused():
    with pytest.raises(ValueError):
        olvia.check([S4, dict(S5, start_utc="2027-01-01T00:00:00+00:00")])
    with pytest.raises(ValueError):
        olvia.check([S4, dict(S5, number=4)])
    assert [r["number"] for r in olvia.check([S5, S4])] == [4, 5]


def test_brief_is_upcoming_then_running():
    rows = olvia.check([S4])
    up = olvia.brief(rows, BEFORE)
    assert up["state"] == "upcoming" and up["number"] == 4 and up["starts_in_s"] > 0
    run = olvia.brief(rows, AFTER)
    assert run["state"] == "running" and run["starts_in_s"] < 0 < run["quests_end_in_s"]
    assert olvia.brief(rows, dt.datetime(2027, 3, 1, tzinfo=UTC)) is None


# --- plan 024 enrolment check per semester ------------------------------------------

def test_each_semester_is_a_plan_024_deadline_row():
    rows = olvia.deadline_rows(olvia.check([S4, S5]))
    assert [r["id"] for r in rows] == ["olvia-semester-4", "olvia-semester-5"]
    for r in rows:
        assert levels.validate_deadline(r)["needs_level"] == 60
    assert rows[0]["enrol_by_utc"] == S4["weekly_quests_end_utc"]


def test_leveling_runs_the_enrolment_check_per_semester(tmp_path):
    clock = Clock(AFTER)
    svc = leveling.LevelingService(Store(tmp_path / "store"), clock=clock, epochs=[],
                                   deadlines=[], issues=[], semesters=[S4, S5])
    svc.sample({"level": 58, "pct": 0})
    clock.to(AFTER + dt.timedelta(hours=10))
    v = svc.sample({"level": 58, "pct": 10})  # 1 %/h: Lv 60 in 190 h, well before 02-24
    by = {d["id"]: d for d in v["deadlines"]}
    assert set(by) == {"olvia-semester-4", "olvia-semester-5"}
    assert by["olvia-semester-4"]["state"] == "on_track"
    assert by["olvia-semester-4"]["tracked"] is True
    assert v["semester"]["number"] == 4 and v["semester"]["state"] == "running"
    assert v["lecture"] is None  # no ledger bound outside the app


def test_injected_deadlines_without_semesters_add_none(tmp_path):
    svc = leveling.LevelingService(Store(tmp_path / "store"), clock=Clock(AFTER), epochs=[],
                                   deadlines=[], issues=[])
    assert svc.view()["deadlines"] == [] and svc.view()["semester"] is None


def test_operator_row_with_the_semester_id_replaces_it(tmp_path):
    svc = leveling.LevelingService(Store(tmp_path / "store"), clock=Clock(AFTER), epochs=[],
                                   deadlines=[], issues=[], semesters=[S4])
    row = dict(olvia.deadline_rows(olvia.check([S4]))[0], needs_level=61, verified=True)
    v = svc.deadline_set(row)
    rows = [d for d in v["deadlines"] if d["id"] == "olvia-semester-4"]
    assert len(rows) == 1 and rows[0]["needs_level"] == 61 and rows[0]["by"] == "typed"


# --- plan 079 stale-mark at the boundary -----------------------------------------

def test_progress_typed_before_the_boundary_is_stale_marked(tmp_path):
    svc, clock, led = _svc(tmp_path, BEFORE)
    assert svc.set_lecture(7)["value"] == 7
    clock.to(AFTER)
    out = svc.lecture()
    assert out["value"] is None  # not carried over
    assert out["stale"]["value"] == 7 and out["stale"]["set_at"].startswith("2026-11-10")
    assert olvia.LECTURE_KEY not in led.doc()["live"]
    hist = led.history()[0]
    assert hist["key"] == olvia.LECTURE_KEY and hist["retired_by"] == olvia.RESET_BY


def test_progress_typed_after_the_boundary_stays(tmp_path):
    svc, clock, led = _svc(tmp_path, AFTER)
    svc.set_lecture(2)
    clock.to(AFTER + dt.timedelta(days=3))
    out = svc.lecture()
    assert out["value"] == 2 and out["stale"] is None
    assert led.history() == []


def test_new_progress_after_the_reset_hides_the_stale_row(tmp_path):
    svc, clock, _ = _svc(tmp_path, BEFORE)
    svc.set_lecture(7)
    clock.to(AFTER)
    assert svc.lecture()["stale"]["value"] == 7
    out = svc.set_lecture(1)
    assert out["value"] == 1 and out["stale"] is None


def test_no_reset_boundary_keeps_progress(tmp_path):
    svc, clock, _ = _svc(tmp_path, BEFORE, rows=[dict(S4, graduation_reset=False)])
    svc.set_lecture(7)
    clock.to(AFTER)
    assert svc.lecture()["value"] == 7


def test_set_lecture_validates_and_clears(tmp_path):
    svc, _, led = _svc(tmp_path, AFTER)
    for bad in (-1, olvia.LECTURE_MAX + 1, True, 1.5, "3"):
        with pytest.raises(ValueError):
            svc.set_lecture(bad)
    svc.set_lecture(3)
    assert svc.set_lecture(None)["value"] is None
    assert led.history()[0]["retired_by"] == "operator"


def test_tracked_policy_covers_the_lecture_key():
    row = ov.load_policy()[olvia.LECTURE_KEY]
    assert row["expiry"].startswith("days:") and "leveling" in row["cards"]


# --- plan 074 digest line ---------------------------------------------------------

def test_digest_row_at_the_reset_maintenance():
    rows = olvia.check([S4])
    start = dt.datetime(2026, 11, 12, 7, 0, tzinfo=UTC)
    out = olvia.digest_rows(rows, BEFORE, start)
    assert len(out) == 1 and out[0]["kind"] == "olvia"
    t = out[0]["title"]
    assert "lectures reset" in t and "2027-02-24 23:59" in t and len(t) <= olvia.TITLE_MAX
    assert olvia.digest_rows(rows, BEFORE, start + dt.timedelta(days=7)) == []


def test_digest_row_at_the_semester_end():
    rows = olvia.check([dict(S4, graduation_reset=False)])
    start = dt.datetime(2027, 2, 25, 7, 0, tzinfo=UTC)
    out = olvia.digest_rows(rows, start - dt.timedelta(hours=5), start)
    assert len(out) == 1 and "S4 ends" in out[0]["title"]
    assert len(out[0]["title"]) <= olvia.TITLE_MAX


def test_digest_service_lists_the_olvia_line(tmp_path):
    clock = Clock(dt.datetime(2026, 11, 11, 12, 0, tzinfo=UTC))
    d = maintdigest.DigestService(
        Store(tmp_path / "store"), loss_rows=lambda: [], items=lambda: [], hot=lambda: [],
        maint_inputs=lambda: {"slot": None, "notices": {}}, clock=clock,
        semesters=lambda: olvia.check([S4]))
    v = d.view()
    assert v["maint"]["start_utc"].startswith("2026-11-12T07:00")
    assert [r["kind"] for r in v["ending"]] == ["olvia"]


def test_digest_survives_a_bad_semester_source(tmp_path):
    d = maintdigest.DigestService(
        Store(tmp_path / "store"), loss_rows=lambda: [], items=lambda: [], hot=lambda: [],
        maint_inputs=lambda: {"slot": None, "notices": {}},
        clock=Clock(dt.datetime(2026, 11, 11, 12, 0, tzinfo=UTC)),
        semesters=lambda: [{"number": "x"}])
    assert d.view()["ending"] == []


def _no_network(url, timeout):
    raise AssertionError(f"network: {url}")


@pytest.mark.server
def test_post_lecture_through_the_leveling_route(tmp_path):
    from server.ew import app as ewapp
    from server.ew import market
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", commit="a" * 40,
                          sse_interval=0.05, market_seed=[],
                          market_client=market.ArshaClient(fetch=_no_network,
                                                           cache_dir=tmp_path / "cache"),
                          profile_cfg={}, config_path=tmp_path / "local.json")
    t = threading.Thread(target=s.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()
    try:
        def call(body):
            c = http.client.HTTPConnection("127.0.0.1", s.server_address[1], timeout=5)
            c.request("POST", "/api/leveling", body=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"})
            r = c.getresponse()
            out = json.loads(r.read())
            c.close()
            return r.status, out
        st, v = call({"lecture": 4})
        assert st == 200 and v["lecture"]["value"] == 4
        assert s.overrides.doc()["live"][olvia.LECTURE_KEY]["source"] == "typed"
        assert call({"lecture": -1})[0] == 400
        st, v = call({"lecture": None})
        assert st == 200 and v["lecture"]["value"] is None
    finally:
        s.shutdown()
        s.server_close()


def test_semester_table_round_trips_as_json():
    assert json.loads(json.dumps(olvia.check([S4]))) == olvia.check([S4])
