"""Plan 131: night drop-chance clock - the pure clock (window edges, wrap past
midnight), the game-time tooltip parser, calibration drift (refit inside /
outside the sanity band, held read), the typed-toggle override precedence, the
auto-OCR pipeline, the drop calculator and GET /api/daynight. No network, no
Tesseract, no PowerShell."""

import datetime as dt
import http.client
import json
import threading

import pytest

from server.ew import app as ewapp
from server.ew import daynight as dn
from server.ew import grind, ocr, ocrauto, overrides
from ew_testkit import offline_market
from server.ew.store import Store

T0 = 1_790_000_000.0
TABLE = dn.load_table()
P = TABLE["period_min"] * 60   # seconds per game day (seed 240 min)
N = TABLE["night_min"] * 60    # seconds of night (seed 40 min)


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).replace(microsecond=0).isoformat()


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


# -- data file ---------------------------------------------------------------------

def test_data_file_ascii_unverified_and_valid():
    raw = dn.DATA_FILE.read_bytes()
    raw.decode("ascii")
    assert b"\r\n" not in raw
    doc = json.loads(raw)
    assert set(doc) >= {"period_min", "night_from", "night_to", "source", "verified"}
    assert doc["verified"] is False  # community seed until a calibration confirms it
    assert TABLE["span_min"] == 540 and 0 < TABLE["night_min"] < TABLE["period_min"]


@pytest.mark.parametrize("bad", [
    {"period_min": 10}, {"night_min": 240}, {"night_from": "25:00"},
    {"night_to": "22:00"}, {"titles": []}])
def test_bad_table_rejected(bad):
    doc = dict(json.loads(dn.DATA_FILE.read_text(encoding="ascii")), **bad)
    with pytest.raises(ValueError):
        dn.clean_table(doc)


def test_bad_table_file_degrades(tmp_path):
    p = tmp_path / "d.json"
    p.write_text("{", encoding="ascii")
    s = dn.DayNightService(Store(tmp_path / "s"), clock=Clock(), path=p)
    v = s.view()
    assert v["error"] and v["calibrated"] is False and v["night"] is False
    with pytest.raises(ValueError):
        s.commit({"game": "22:00"}, "a.jpg", T0, "u1")


# -- pure clock --------------------------------------------------------------------

def test_phase_round_trip_and_mapping():
    assert dn.phase_of(dn.to_min("22:00"), TABLE) == 0
    assert dn.phase_of(dn.to_min("07:00"), TABLE) == pytest.approx(N / P)
    for hhmm in ("00:00", "03:30", "06:59", "07:00", "12:00", "21:59", "22:00", "23:59"):
        m = dn.to_min(hhmm)
        assert dn.game_at(dn.phase_of(m, TABLE) + 1e-9, TABLE) == m


@pytest.mark.parametrize("game,night,left_s", [
    ("22:00", True, N),                      # night starts: 40 min of it left
    ("07:00", False, P - N),                 # day starts: 200 min to the next night
    ("21:59", False, (P - N) / 900),         # last day minute
    ("06:59", True, N / 540),                # last night minute
    ("00:30", True, N * (540 - 150) / 540),  # wrap past game midnight
    ("02:00", True, N * (540 - 240) / 540),
])
def test_window_edges_and_wrap(game, night, left_s):
    st = dn.clock_at(T0, T0, game, TABLE["period_min"], TABLE)
    assert st["night"] is night and st["game_now"] == game
    assert st["next_change"] - T0 == pytest.approx(left_s, abs=0.01)


def test_clock_runs_from_the_anchor():
    st = dn.clock_at(T0 + N, T0, "22:00", TABLE["period_min"], TABLE)
    assert st["night"] is False and st["game_now"] == "07:00"
    st = dn.clock_at(T0 + P - 1, T0, "22:00", TABLE["period_min"], TABLE)
    assert st["night"] is False and st["next_change"] == pytest.approx(T0 + P)
    st = dn.clock_at(T0 + 3 * P + 60, T0, "22:00", TABLE["period_min"], TABLE)
    assert st["night"] is True  # three whole cycles later
    st = dn.clock_at(T0 - 60, T0, "07:00", TABLE["period_min"], TABLE)
    assert st["night"] is True  # before the anchor works too


def test_check_value():
    assert dn.check_value({"game": "22:15"}) == {"game": "22:15"}
    for bad in ({"game": "24:00"}, {"game": "7:00"}, {"game": "22:15", "x": 1}, "22:15", None):
        with pytest.raises(ValueError):
            dn.check_value(bad)


# -- drift / calibration -----------------------------------------------------------

def _svc(tmp_path, ledger=False):
    clock = Clock()
    store = Store(tmp_path / "store")
    led = None
    if ledger:
        led = overrides.OverrideLedger(store, clock=clock)
    return dn.DayNightService(store, clock=clock, ledger=led), clock


def test_first_read_calibrates(tmp_path):
    s, clock = _svc(tmp_path)
    assert s.state() is None and s.view()["calibrated"] is False
    s.commit({"game": "22:00"}, "a.jpg", T0, "u1")
    clock.t = T0 + 600
    v = s.view()
    assert v["calibrated"] and v["night"] is True and v["via"] == "clock"
    assert v["ends_in_s"] == N - 600 and v["next_change_utc"] == _iso(T0 + N)
    assert v["verified"] is False and v["reads"] == 1


def test_drift_inside_tolerance_confirms(tmp_path):
    s, clock = _svc(tmp_path)
    s.commit({"game": "22:00"}, "a.jpg", T0, "u1")
    # one cycle + 2 min later the clock says 22:00 + 2 real min = 22:27 game
    later = T0 + P + 120
    game = dn.fmt(dn.game_at(120 / P, TABLE))
    assert s.ocr_check({"game": game}, later) == ("ok", None)
    s.commit({"game": game}, "b.jpg", later, "u2")
    clock.t = later
    v = s.view()
    assert v["verified"] is True and v["refit"] is False and v["period_min"] == 240


def test_drift_refit_inside_band(tmp_path):
    s, clock = _svc(tmp_path)
    s.commit({"game": "07:00"}, "a.jpg", T0, "u1")
    # the real period is 241 min: ten cycles later the clock is 10 min off
    real = 241 * 60
    later = T0 + 10 * real
    act, why = s.ocr_check({"game": "07:00"}, later)
    assert act == "ok" and why.startswith("period refit to 241.0")
    s.commit({"game": "07:00"}, "b.jpg", later, "u2")
    clock.t = later
    v = s.view()
    assert v["refit"] is True and v["period_min"] == pytest.approx(241, abs=0.01)
    assert v["verified"] is True
    # the refit period predicts the next change
    assert v["next_change_utc"] == _iso(later + real - N * 241 / 240)


def test_drift_outside_band_is_held(tmp_path):
    s, _ = _svc(tmp_path)
    s.commit({"game": "07:00"}, "a.jpg", T0, "u1")
    later = T0 + 1800  # 30 min later the clock reads 07:00 + 30 min of day
    act, why = s.ocr_check({"game": "13:00"}, later)  # 13:00 is 6 game h = 60 real min
    assert act == "hold" and "off the clock" in why
    with pytest.raises(ValueError):
        s.commit({"game": "13:00"}, "b.jpg", later, "u2")
    assert s.view(later)["reads"] == 1
    # an operator accept (force) starts a new chain from the held read
    prev = s.commit({"game": "13:00"}, "b.jpg", later, "u2", force=True)
    v = s.view(later)
    assert v["reads"] == 1 and v["anchor"]["game"] == "13:00" and v["verified"] is False
    s.restore("u2", prev)
    assert s.view(later)["anchor"]["game"] == "07:00"


def test_older_read_is_skipped_and_undo_needs_the_newest(tmp_path):
    s, _ = _svc(tmp_path)
    s.commit({"game": "07:00"}, "a.jpg", T0, "u1")
    assert s.ocr_check({"game": "07:00"}, T0 - 60)[0] == "skip"
    prev = s.commit({"game": dn.fmt(dn.game_at(N / P + 60 / P, TABLE))}, "b.jpg",
                    T0 + 60, "u2")
    with pytest.raises(ValueError):
        s.restore("u1", {})
    s.restore("u2", prev)
    assert s.view(T0)["reads"] == 1


def test_corrupt_store_degrades(tmp_path):
    s, _ = _svc(tmp_path)
    s.store.put(dn.DOMAIN, {"reads": [{"id": "u1", "at": "x", "game": "25:00"}, 5],
                            "period_min": 999})
    v = s.view()
    assert v["calibrated"] is False and v["period_min"] == 240


# -- override precedence -----------------------------------------------------------

def test_typed_toggle_overrides_until_the_next_change(tmp_path):
    s, clock = _svc(tmp_path, ledger=True)
    s.commit({"game": "07:00"}, "a.jpg", T0, "u1")  # day for 200 min
    clock.t = T0 + 600
    assert s.effective()["night"] is False and s.effective()["via"] == "clock"
    s.set_override(True)
    e = s.effective()
    assert e["night"] is True and e["via"] == "override"
    assert e["until_utc"] == _iso(T0 + P - N)  # ends at the next day / night change
    clock.t = T0 + P - N + 1  # night now; the override retired by the clock
    e = s.effective()
    assert e["via"] == "clock" and e["night"] is True
    assert s.ledger.history()[0]["retired_by"] == "clock"


def test_typed_toggle_uncalibrated_expires_by_the_ledger(tmp_path):
    s, clock = _svc(tmp_path, ledger=True)
    assert s.effective()["via"] is None
    s.set_override(True)
    assert s.effective()["night"] is True and s.effective()["via"] == "override"
    clock.t = T0 + 86400 + 1
    assert s.effective()["via"] is None and s.effective()["night"] is False


def test_override_off_beats_a_night_clock(tmp_path):
    s, clock = _svc(tmp_path, ledger=True)
    s.commit({"game": "22:00"}, "a.jpg", T0, "u1")
    s.set_override(False)
    e = s.effective()
    assert e["night"] is False and e["via"] == "override"
    with pytest.raises(ValueError):
        s.set_override("yes")


# -- OCR parser --------------------------------------------------------------------

def _tip(time_text="Game Time 22:15", extra=None, scale=1.0):
    h = round(18 * scale)

    def ln(text, x, y):
        return {"text": text, "x": round(x * scale), "y": round(y * scale),
                "w": round(200 * scale), "h": h}

    lines = [ln("Kamasylvia", 1700, 40), ln(time_text, 1650, 300),
             ln("Item drop chance increases at night.", 1650, 322)]
    lines += [ln(t, x, y) for t, x, y in (extra or [])]
    return {"text": "\n".join(x["text"] for x in lines), "lines": lines}


@pytest.mark.parametrize("scale", [1.0, 1.5])
def test_parse_tooltip(scale):
    [f] = dn.parse(_tip(scale=scale), TABLE["titles"])
    assert f["kind"] == "gametime" and f["value"] == {"game": "22:15"}
    assert f["conf"] == dn.CONF_SAME


@pytest.mark.parametrize("text,game", [
    ("Game Time: PM 10:15", "22:15"), ("In-game time 7:05 AM", "07:05"),
    ("Game Time 12:00 am", "00:00"), ("Game Time 00:40", "00:40")])
def test_parse_time_formats(text, game):
    assert dn.parse(_tip(text), TABLE["titles"])[0]["value"] == {"game": game}


def test_parse_time_beside_and_dotted_and_ambiguous():
    doc = _tip("Game Time", extra=[("21:40", 1650, 318)])
    [f] = dn.parse(doc, TABLE["titles"])
    assert f["value"] == {"game": "21:40"} and f["conf"] == dn.CONF_NEAR
    [f] = dn.parse(_tip("Game Time 21.40"), TABLE["titles"])
    assert f["conf"] < 0.9 and "dot" in f["why"]
    doc = _tip("Game Time 21:40", extra=[("03:10", 1650, 330)])
    assert dn.parse(doc, TABLE["titles"])[0]["conf"] == dn.CONF_AMBIG


def test_no_tooltip_no_read_and_far_clock_ignored():
    doc = {"text": "Silver 1,234\n22:15", "lines": [
        {"text": "Silver 1,234", "x": 0, "y": 0, "w": 100, "h": 18},
        {"text": "22:15", "x": 0, "y": 40, "w": 50, "h": 18}]}
    assert dn.parse(doc, TABLE["titles"]) == []
    doc = _tip("Game Time 22:15", extra=[("PM 03:10", 1800, 1000)])  # the real-time clock
    [f] = dn.parse(doc, TABLE["titles"])
    assert f["value"] == {"game": "22:15"} and f["conf"] == dn.CONF_SAME
    assert dn.parse(_tip("Game Time 25:61"), TABLE["titles"]) == []


# -- auto-OCR pipeline -------------------------------------------------------------

class FakeGame:
    def __init__(self, shot_dir):
        self.shot_dir = shot_dir
        self.shots = []

    def add(self, name, ts, size=10):
        (self.shot_dir / name).write_bytes(b"x" * size)
        self.shots.insert(0, {"name": name, "size": size, "mtime": _iso(ts)})

    def view(self):
        return {"screenshots": [dict(s) for s in self.shots]}


@pytest.fixture
def env(tmp_path):
    shot_dir = tmp_path / "ScreenShot"
    shot_dir.mkdir()
    game = FakeGame(shot_dir)
    docs = {}
    clock = Clock()
    store = Store(tmp_path / "store")
    g = grind.GrindService(store, clock=clock, presets=[])
    led = overrides.OverrideLedger(store, clock=clock)
    day = dn.DayNightService(store, clock=clock, ledger=led)
    g.night, g.night_set = day.effective, day.set_override
    reader = ocr.OcrService(game, tmp_path / "ocr", runner=lambda p: docs[p.name])
    auto = ocrauto.AutoOcr(store, game, reader, g, settings=lambda: {}, clock=clock,
                           daynight=day)

    class Env:
        pass

    e = Env()
    e.__dict__.update(game=game, docs=docs, clock=clock, grind=g, day=day, auto=auto)
    return e


def _run(e, shots, start=T0 - 7200):
    e.auto.on_game(None, "logged_in", start)
    for name, ts, doc in shots:
        e.game.add(name, ts)
        e.docs[name] = doc
    e.clock.t = max(ts for _, ts, _ in shots) + 60
    e.auto.scan()
    e.auto.drain()


def _drops(e):
    d = e.grind.view()["drops"]
    row = next(r for r in d["buffs"] if r["id"] == "night")
    via = next((a["via"] for a in d["active"] if a["id"] == "night"), None)
    return row["on"], via, d


def test_shot_calibrates_and_drives_the_calculator(env):
    assert _drops(env)[:2] == (False, None)
    _run(env, [("t1.jpg", T0, _tip("Game Time 22:00"))])
    on, via, d = _drops(env)
    assert on is True and via == "clock" and d["rate_total"] == 10
    assert d["night"]["calibrated"] is True
    [c] = [c for c in env.auto.view()["commits"] if c["kind"] == "gametime"]
    env.clock.t = T0 + N + 5
    assert _drops(env)[:2] == (False, None)  # night ended by the clock
    env.auto.undo(c["id"])
    assert env.day.state() is None


def test_held_read_goes_to_review_and_accept_recalibrates(env):
    _run(env, [("t1.jpg", T0, _tip("Game Time 07:00"))])
    _run(env, [("t2.jpg", T0 + 1800, _tip("Game Time 13:00"))])
    [r] = [r for r in env.auto.view()["review"] if r["kind"] == "gametime"]
    assert "off the clock" in r["why"]
    assert env.day.view()["anchor"]["game"] == "07:00"
    with pytest.raises(ValueError):  # accept / discard only
        env.auto.review({"id": r["id"], "action": "fix", "value": {"game": "13:00"}})
    env.auto.review({"id": r["id"], "action": "accept"})
    assert env.day.view()["anchor"]["game"] == "13:00"


def test_low_confidence_read_is_reviewed(env):
    _run(env, [("t1.jpg", T0, _tip("Game Time 21:40", extra=[("03:10", 1650, 330)]))])
    assert env.day.state() is None
    assert [r for r in env.auto.view()["review"] if r["kind"] == "gametime"]


def test_typed_toggle_in_the_calculator_is_an_override(env):
    _run(env, [("t1.jpg", T0, _tip("Game Time 07:00"))])
    assert _drops(env)[:2] == (False, None)
    env.grind.drop_toggle({"id": "night", "on": True})
    assert _drops(env)[:2] == (True, "override")
    assert "night" not in env.grind.store.get("grind").get("drop_on", [])
    env.clock.t = T0 + P - N + 1
    assert _drops(env)[:2] == (True, "clock")  # the override ended at the change


def test_unwired_grind_keeps_the_plain_toggle(tmp_path):
    g = grind.GrindService(Store(tmp_path / "s"), clock=Clock(), presets=[])
    g.drop_toggle({"id": "night", "on": True})
    d = g.view()["drops"]
    assert d["night"] is None and d["rate_total"] == 10
    assert next(a for a in d["active"] if a["id"] == "night")["via"] == "toggle"


# -- route -------------------------------------------------------------------------

@pytest.fixture()
def srv(tmp_path):
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", commit="a" * 40,
                          market_seed=[], profile_cfg={}, grind_clock=Clock(),
                          config_path=tmp_path / "local.json",
                          market_client=offline_market(tmp_path))
    t = threading.Thread(target=s.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()
    yield s
    s.shutdown()
    s.server_close()


def _req(s, method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", s.server_address[1], timeout=5)
    c.request(method, path, body=json.dumps(body) if body is not None else None,
              headers={"Content-Type": "application/json"} if body is not None else {})
    r = c.getresponse()
    out = json.loads(r.read().decode("utf-8"))
    c.close()
    return r.status, out


@pytest.mark.server
def test_route_daynight(srv):
    code, body = _req(srv, "GET", "/api/daynight")
    assert code == 200 and body["calibrated"] is False and body["error"] is None
    assert body["period_min"] == 240 and body["verified"] is False
    srv.daynight.commit({"game": "22:00"}, "t.jpg", T0, "u1")
    code, body = _req(srv, "GET", "/api/daynight")
    assert code == 200 and body["night"] is True and body["via"] == "clock"
    assert srv.live_signals()["grind.night"]() == {"value": True, "signal": "game_clock"}
    code, g = _req(srv, "GET", "/api/grind")
    assert code == 200 and g["drops"]["night"]["via"] == "clock"
