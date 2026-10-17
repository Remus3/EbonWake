"""Plan 140: weekly silver goal - earned this week, goal, pace and projection."""

import datetime as dt
import http.client
import itertools
import json
import threading

import pytest

from server.ew import app as ewapp
from server.ew import market, overrides, silvergoal, today, whatnow

UTC = dt.timezone.utc
# Saturday 2026-10-17 12:00 UTC; the NA weekly reset is Thursday 00:00 UTC.
NOW = dt.datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
WEEK_START = dt.datetime(2026, 10, 15, 0, 0, tzinfo=UTC)
WEEK_END = dt.datetime(2026, 10, 22, 0, 0, tzinfo=UTC)


def iso(t):
    return t.isoformat()


_IDS = itertools.count(1)


def ses(label, started, silver, minutes=60, **extra):
    """A grind session row (plan 005 shape); `label` only names it in the test."""
    return dict({"id": f"s{next(_IDS)}", "spot": "s1", "started": iso(started), "minutes": minutes,
                 "silver": silver, "trash": 0}, **extra)


def sale(sid, at, price, vp=False, fame=0):
    return {"id": sid, "at": iso(at), "price": price, "vp": vp, "fame_pct": fame}


def ocr_ses(sid, started, silver, first, last):
    return ses(sid, started, silver, auto=True, silver_src="ocr_delta",
               silver_from={"first_at": iso(first), "last_at": iso(last), "n": 3, "conf": 0.95})


def history(weekly):
    """One typed session per past full week (oldest first), Friday noon."""
    out = []
    for i, amount in enumerate(weekly):
        back = len(weekly) - i
        out.append(ses(f"h{i}", WEEK_START - dt.timedelta(days=7 * back) + dt.timedelta(days=1),
                       amount))
    return out


# -- week window ---------------------------------------------------------------------

def test_week_is_the_plan_021_na_weekly_reset_window():
    start, end = silvergoal.week_window(NOW)
    assert start == today.last_weekly_reset(NOW) == WEEK_START
    assert end == today.next_weekly_reset(NOW) == WEEK_END


def test_week_window_at_the_reset_instant_starts_a_new_week():
    start, end = silvergoal.week_window(WEEK_END)
    assert start == WEEK_END and end == WEEK_END + dt.timedelta(days=7)


# -- earned --------------------------------------------------------------------------

def test_earned_sums_typed_and_auto_sessions_plus_sales_net_in_the_week():
    sessions = [ses("a", WEEK_START + dt.timedelta(hours=1), 1000),
                ses("b", NOW - dt.timedelta(hours=2), 500, auto=True),
                ses("old", WEEK_START - dt.timedelta(hours=1), 9999)]
    sales = [sale("s1", NOW - dt.timedelta(hours=1), 1_000_000, vp=True, fame=0),
             sale("s0", WEEK_START - dt.timedelta(days=1), 5_000_000)]
    src = {"sessions": sessions, "sales": sales}
    net = market.net_proceeds(1_000_000, True, 0)
    assert silvergoal.earned_week(src, (WEEK_START, WEEK_END)) == 1500 + net


def test_a_sale_also_seen_as_an_ocr_silver_delta_is_counted_once():
    first, last = NOW - dt.timedelta(hours=3), NOW - dt.timedelta(hours=1)
    net = market.net_proceeds(2_000_000, False, 0)
    sessions = [ocr_ses("a", first, 5_000_000 + net, first, last)]
    sales = [sale("s1", NOW - dt.timedelta(hours=2), 2_000_000)]
    src = {"sessions": sessions, "sales": sales}
    assert silvergoal.earned_week(src, (WEEK_START, WEEK_END)) == 5_000_000 + net


def test_the_ocr_delta_never_goes_negative_and_typed_rows_are_not_trimmed():
    first, last = NOW - dt.timedelta(hours=3), NOW - dt.timedelta(hours=1)
    net = market.net_proceeds(2_000_000, False, 0)
    sessions = [ocr_ses("a", first, 100, first, last),
                ses("t", first, 700)]  # typed: the operator's own number stands
    sales = [sale("s1", NOW - dt.timedelta(hours=2), 2_000_000)]
    src = {"sessions": sessions, "sales": sales}
    assert silvergoal.earned_week(src, (WEEK_START, WEEK_END)) == net + 700


def test_a_sale_outside_the_ocr_window_does_not_trim_it():
    first, last = NOW - dt.timedelta(hours=3), NOW - dt.timedelta(hours=2)
    net = market.net_proceeds(1_000_000, False, 0)
    sessions = [ocr_ses("a", first, 3_000_000, first, last)]
    sales = [sale("s1", NOW - dt.timedelta(hours=1), 1_000_000)]
    src = {"sessions": sessions, "sales": sales}
    assert silvergoal.earned_week(src, (WEEK_START, WEEK_END)) == 3_000_000 + net


def test_malformed_rows_are_skipped():
    src = {"sessions": [{"id": "x"}, None, ses("a", NOW - dt.timedelta(hours=1), 10)],
           "sales": [{"at": "nope", "price": 5}, sale("s", NOW, -1), "junk",
                     sale("s2", NOW - dt.timedelta(hours=1), 100, fame=999)]}
    assert silvergoal.earned_week(src, (WEEK_START, WEEK_END)) == 10
    assert silvergoal.earned_week({}, (WEEK_START, WEEK_END)) == 0
    assert silvergoal.earned_week(None, (WEEK_START, WEEK_END)) == 0


# -- goal ----------------------------------------------------------------------------

def test_goal_is_the_median_of_the_last_four_full_weeks_plus_ten_percent():
    src = {"sessions": history([10_000_000, 40_000_000, 20_000_000, 30_000_000]), "sales": []}
    g = silvergoal.goal(src, NOW, override=None)
    assert g == {"value": 27_500_000, "source": "history", "weeks": [
        10_000_000, 40_000_000, 20_000_000, 30_000_000]}


def test_only_the_last_four_full_weeks_count():
    src = {"sessions": history([999_000_000, 10, 10, 10, 10]), "sales": []}
    assert silvergoal.goal(src, NOW, None)["value"] == 11


def test_weeks_before_the_first_ledger_entry_do_not_count():
    src = {"sessions": history([10_000_000, 20_000_000]), "sales": []}
    g = silvergoal.goal(src, NOW, None)
    assert g["weeks"] == [10_000_000, 20_000_000]
    assert g["value"] == 16_500_000


def test_a_quiet_week_after_history_began_counts_as_zero():
    sessions = history([10_000_000, 20_000_000, 30_000_000, 40_000_000])
    del sessions[2]
    g = silvergoal.goal({"sessions": sessions, "sales": []}, NOW, None)
    assert g["weeks"] == [10_000_000, 20_000_000, 0, 40_000_000]
    assert g["value"] == 16_500_000


def test_no_history_means_no_goal():
    assert silvergoal.goal({"sessions": [], "sales": []}, NOW, None) == {
        "value": None, "source": None, "weeks": []}
    only_this_week = {"sessions": [ses("a", NOW - dt.timedelta(hours=1), 50)], "sales": []}
    assert silvergoal.goal(only_this_week, NOW, None)["value"] is None


def test_an_override_wins_over_history():
    src = {"sessions": history([10, 20, 30, 40]), "sales": []}
    g = silvergoal.goal(src, NOW, override=500_000_000)
    assert g["value"] == 500_000_000 and g["source"] == "override"


@pytest.mark.parametrize("bad", [0, -5, None, True, 1.5, "100"])
def test_a_non_positive_or_non_int_override_is_ignored(bad):
    src = {"sessions": history([10, 20, 30, 40]), "sales": []}
    assert silvergoal.goal(src, NOW, override=bad)["source"] == "history"


# -- pace ----------------------------------------------------------------------------

def test_pace_needed_per_day_projection_and_on_track():
    # 4.5 days left (Sat 12:00 -> Thu 00:00) -> 5 whole days for "per day".
    src = {"sessions": [ses("a", NOW - dt.timedelta(days=1), 70_000_000)], "sales": []}
    p = silvergoal.pace(src, NOW, earned=70_000_000, goal_value=100_000_000)
    assert p["days_left"] == 5
    assert p["needed_per_day"] == 6_000_000
    assert p["rate_per_day"] == 10_000_000
    assert p["projection"] == 70_000_000 + 45_000_000
    assert p["on_track"] is True
    assert all(isinstance(p[k], int) and not isinstance(p[k], bool)
               for k in ("days_left", "needed_per_day", "rate_per_day", "projection"))


def test_pace_off_track_and_goal_met():
    src = {"sessions": [ses("a", NOW - dt.timedelta(days=1), 7_000_000)], "sales": []}
    p = silvergoal.pace(src, NOW, earned=7_000_000, goal_value=100_000_000)
    assert p["on_track"] is False and p["needed_per_day"] == 18_600_000
    met = silvergoal.pace(src, NOW, earned=200, goal_value=100)
    assert met["needed_per_day"] == 0 and met["on_track"] is True


def test_trailing_rate_spans_the_reset():
    # Last week's Wednesday still counts in the trailing 7 days.
    src = {"sessions": [ses("a", WEEK_START - dt.timedelta(hours=12), 14_000_000)], "sales": []}
    p = silvergoal.pace(src, NOW, earned=0, goal_value=1)
    assert p["rate_per_day"] == 2_000_000


# -- view ----------------------------------------------------------------------------

def test_view_hidden_without_a_goal():
    v = silvergoal.view({"sessions": [], "sales": []}, NOW)
    assert v["hidden"] is True and v["goal"] is None and v["pace"] is None
    assert v["week"] == {"start": iso(WEEK_START), "end": iso(WEEK_END)}


def test_view_with_history_and_override():
    src = {"sessions": history([10_000_000] * 4) + [ses("a", NOW - dt.timedelta(hours=1),
                                                       1_000_000)], "sales": []}
    v = silvergoal.view(src, NOW)
    assert v["hidden"] is False and v["goal"] == 11_000_000 and v["goal_source"] == "history"
    assert v["earned"] == 1_000_000 and v["pace"]["on_track"] is False
    v2 = silvergoal.view(src, NOW, override=1_000_000)
    assert v2["goal"] == 1_000_000 and v2["goal_source"] == "override"
    assert v2["pace"]["on_track"] is True


def test_view_carries_the_game_running_flag():
    assert silvergoal.view({}, NOW, running=True)["running"] is True
    assert silvergoal.view({}, NOW)["running"] is False


# -- override expiry with the week ---------------------------------------------------

def test_week_goal_override_key_expires_at_the_weekly_reset():
    policy = overrides.load_policy()
    assert policy["grind.week_goal"]["expiry"] == "until:week_reset"
    assert "grind" in policy["grind.week_goal"]["cards"]
    set_at = NOW.timestamp()
    assert overrides.expiry_at("until:week_reset", set_at) == WEEK_END.timestamp()
    # set at the reset instant: the next week's reset
    assert overrides.expiry_at("until:week_reset", WEEK_END.timestamp()) == (
        WEEK_END + dt.timedelta(days=7)).timestamp()


def test_override_ledger_drops_the_goal_after_the_reset():
    class Store:
        def __init__(self):
            self.d = {}

        def get(self, k):
            return self.d.get(k, {})

        def put(self, k, v):
            self.d[k] = v

    led = overrides.OverrideLedger(Store(), clock=lambda: NOW.timestamp())
    led.set("grind.week_goal", 300_000_000)
    before = led.effective("grind.week_goal", None, 0, now=WEEK_END.timestamp() - 1)
    after = led.effective("grind.week_goal", None, 0, now=WEEK_END.timestamp())
    assert before["value"] == 300_000_000
    assert after["value"] == 0


# -- what now ------------------------------------------------------------------------

def _wn_view(on_track, running, needed=5_000_000):
    return {"hidden": False, "goal": 100, "earned": 1, "running": running,
            "week": {"start": iso(WEEK_START), "end": iso(WEEK_END)},
            "pace": {"on_track": on_track, "needed_per_day": needed, "days_left": 5,
                     "rate_per_day": 1, "projection": 2}}


def test_whatnow_suggests_only_when_off_track_and_the_game_runs():
    c = whatnow.silver_goal(_wn_view(False, True), NOW)
    assert len(c) == 1 and c[0]["source"] == "silver" and c[0]["due"] is None
    assert "5.0M" in c[0]["text"] and len(c[0]["text"]) <= whatnow.TEXT_MAX
    assert whatnow.silver_goal(_wn_view(True, True), NOW) == []
    assert whatnow.silver_goal(_wn_view(False, False), NOW) == []
    assert whatnow.silver_goal({"hidden": True, "running": True}, NOW) == []
    assert whatnow.silver_goal(None, NOW) == []


def test_whatnow_silver_source_is_weighted_and_ranks():
    w = whatnow.load_weights()
    assert "silver" in w and "silver" in whatnow.SOURCES
    out = whatnow.collect({"silver": lambda: _wn_view(False, True)}, NOW, w)
    assert out["top"]["source"] == "silver"


# -- routes --------------------------------------------------------------------------

def _no_network(url, timeout=None):
    raise AssertionError(f"no network in tests: {url}")


@pytest.fixture()
def srv(tmp_path):
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", commit="a" * 40,
                          sse_interval=0.05, market_seed=[],
                          market_client=market.ArshaClient(fetch=_no_network,
                                                           cache_dir=tmp_path / "cache"),
                          profile_cfg={}, config_path=tmp_path / "local.json")
    t = threading.Thread(target=s.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()
    yield s
    s.shutdown()
    s.server_close()


def _call(s, method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", s.server_address[1], timeout=5)
    data = json.dumps(body).encode() if body is not None else None
    c.request(method, path, body=data,
              headers={"Content-Type": "application/json"} if data else {})
    r = c.getresponse()
    out = r.read()
    c.close()
    return r.status, json.loads(out) if out else None


@pytest.mark.server
def test_routes_get_view_and_typed_goal_through_the_grind_route(srv):
    st, v = _call(srv, "GET", "/api/silvergoal")
    assert st == 200 and v["hidden"] is True and v["earned"] == 0 and v["running"] is False
    st, v = _call(srv, "POST", "/api/grind", {"week_goal": 250_000_000})
    assert st == 200 and v["goal"] == 250_000_000 and v["goal_source"] == "override"
    assert v["pace"]["on_track"] is False
    assert _call(srv, "GET", "/api/silvergoal")[1]["goal"] == 250_000_000
    led = srv.overrides.doc()["live"]["grind.week_goal"]
    assert led["source"] == "typed" and led["expires_at"] is not None
    assert _call(srv, "POST", "/api/grind", {"week_goal": -1})[0] == 400
    assert _call(srv, "POST", "/api/grind", {"week_goal": True})[0] == 400
    # game not running: no What-now suggestion even off pace
    top = _call(srv, "GET", "/api/whatnow")[1]["top"]
    assert top is None or top["source"] != "silver"
    st, v = _call(srv, "POST", "/api/grind", {"week_goal": None})
    assert st == 200 and v["hidden"] is True
