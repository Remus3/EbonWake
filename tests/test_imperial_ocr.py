"""Plan 117: Imperial CP + Imperial mastery from OCR - Energy / CP bar and
life-skill mastery window shots fill the Imperial delivery planner (053)
inputs; a typed value is an override that expires after TYPED_TTL_S.
Stub OCR engine only; nothing runs Tesseract or touches the game."""

import datetime as dt
import http.client
import json
import threading

import pytest

from server.ew import app as ewapp
from server.ew import grind, imperial, market, ocr, ocrauto, ocrinfer
from server.ew.store import Store

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 10, 5, 22, 30, tzinfo=UTC).timestamp()
DAY = 86400.0


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, UTC).replace(microsecond=0).isoformat()


def _ln(text, y=0, x=0, w=300, h=20):
    return {"text": text, "x": x, "y": y, "w": w, "h": h}


def _doc(*lines):
    lines = [ln if isinstance(ln, dict) else _ln(ln, y=40 * i) for i, ln in enumerate(lines)]
    return {"text": "\n".join(ln["text"] for ln in lines), "lines": lines}


CP_BAR = _doc("Energy 210/300", "Contribution 45/312")
MASTERY_WINDOW = _doc("Cooking Mastery 1,250", "Imperial Cooking Delivery Bonus +40.5%")


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


# -- slice 1: CP bar shapes ------------------------------------------------------------

@pytest.mark.parametrize("text", ["Contribution 45/312", "Contrib. 45 / 312",
                                  "Energy 210/300  CP 45/312",
                                  "Contribution Points 45 / 312"])
def test_cp_bar_shapes(text):
    f = ocrinfer.cp_field(_doc(text))
    assert f["kind"] == "cp" and f["value"] == 312
    assert f["conf"] >= ocrauto.AUTO_COMMIT_MIN


def test_energy_pair_is_never_cp():
    assert ocrinfer.cp_field(_doc("Energy 210/300")) is None
    assert ocrinfer.cp_field(CP_BAR)["value"] == 312
    assert [f["kind"] for f in ocrinfer.planner_fields(CP_BAR)] == ["cp"]


# -- slice 2: mastery parser -----------------------------------------------------------

def _m(doc):
    return [(f["kind"], f["name"], f["value"]) for f in ocrinfer.mastery_fields(doc)]


def test_mastery_type_on_the_line():
    out = ocrinfer.mastery_fields(_doc("Imperial Alchemy Delivery +12.25%"))
    assert [(f["name"], f["value"]) for f in out] == [("alchemy", 12.25)]
    assert out[0]["conf"] == ocrinfer.CONF_MASTERY_LINE and out[0]["why"]


def test_mastery_type_from_the_window_header():
    doc = _doc("Cooking Mastery 1,250", "Imperial Delivery Bonus +40.5%")
    out = ocrinfer.mastery_fields(doc)
    assert [(f["name"], f["value"]) for f in out] == [("cooking", 40.5)]
    assert out[0]["conf"] == ocrinfer.CONF_MASTERY_HEADER
    assert out[0]["conf"] >= ocrauto.AUTO_COMMIT_MIN


def test_mastery_two_headers_without_type_is_no_read():
    doc = _doc("Cooking Mastery 1,250", "Alchemy Mastery 800", "Imperial Delivery +40.5%")
    assert _m(doc) == []


def test_mastery_both_types_on_lines_and_whole_and_comma():
    doc = _doc("Imperial Cooking Delivery +40%", "Imperial Alchemy Delivery +12,5%")
    out = {f["name"]: f for f in ocrinfer.mastery_fields(doc)}
    assert out["cooking"]["value"] == 40 and out["alchemy"]["value"] == 12.5
    assert out["alchemy"]["conf"] == ocrinfer.CONF_MASTERY_COMMA < ocrauto.AUTO_COMMIT_MIN


def test_mastery_none_shapes():
    assert _m(_doc("Cooking Mastery 1,250")) == []          # points only: no bonus read
    assert _m(_doc("Imperial Cooking Delivery +900%")) == []  # over the planner bound
    assert _m(_doc("Cooking +40.5%")) == []
    assert any(k == "mastery" for k, _, _ in
               [(f["kind"], f["name"], f["value"])
                for f in ocrinfer.planner_fields(MASTERY_WINDOW)])


# -- slice 3: kind wiring --------------------------------------------------------------

def test_kind_registered():
    assert "mastery" in ocrauto.PLANNER_KINDS
    assert "mastery" in ocrauto.KINDS and "mastery" in ocrauto.FIX_KINDS


class FakeGame:
    def __init__(self, shot_dir):
        self.shot_dir = shot_dir
        self.shots = []

    def add(self, name, when, size=10):
        (self.shot_dir / name).write_bytes(b"x" * size)
        self.shots.insert(0, {"name": name, "size": size, "mtime": _iso(when)})

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
    reader = ocr.OcrService(game, tmp_path / "ocr", runner=lambda p: docs[p.name])
    auto = ocrauto.AutoOcr(store, game, reader, g, settings=lambda: {}, clock=clock)
    auto.on_game(None, "logged_in", T0 - DAY)
    imp = imperial.ImperialService(store, clock=clock, reads=auto.latest)

    class Env:
        pass

    e = Env()
    e.__dict__.update(game=game, docs=docs, clock=clock, store=store, auto=auto, imp=imp)
    return e


def _shot(e, name, when, doc):
    e.game.add(name, when)
    e.docs[name] = doc
    e.auto.scan()
    e.auto.drain()


def _type(v, t):
    return next(r for r in v["types"] if r["type"] == t)


def test_worker_commits_mastery_and_cp_and_imperial_reads_them(env):
    _shot(env, "cp.png", T0 - 600, CP_BAR)
    _shot(env, "m.png", T0 - 300, MASTERY_WINDOW)
    assert env.auto.view()["review"] == []
    assert env.auto.latest("mastery:cooking")["value"] == 40.5
    assert env.auto.latest("mastery:alchemy") is None
    v = env.imp.view()
    assert v["cp"]["value"] == 312 and v["cp"]["source"] == "ocr"
    cook = _type(v, "cooking")
    assert cook["cap"] == 156 and cook["mastery_pct"] == 40.5
    assert cook["mastery_source"] == "ocr" and cook["mastery_age_s"] == 300
    assert _type(v, "alchemy")["mastery_pct"] == 0
    assert _type(v, "alchemy")["mastery_source"] == "default"


def test_latest_mastery_needs_a_type(env):
    with pytest.raises(ValueError):
        env.auto.latest("mastery:fishing")
    with pytest.raises(ValueError):
        env.auto.latest("mastery")


def test_undo_removes_the_mastery_read(env):
    _shot(env, "m.png", T0 - 300, MASTERY_WINDOW)
    uid = env.auto.view()["commits"][0]["id"]
    env.auto.undo(uid)
    assert env.auto.latest("mastery:cooking") is None
    assert _type(env.imp.view(), "cooking")["mastery_pct"] == 0


def test_review_fix_of_a_low_conf_mastery_read(env):
    _shot(env, "m.png", T0 - 300, _doc("Imperial Alchemy Delivery +12,5%"))
    rv = env.auto.view()["review"]
    assert [(r["kind"], r["name"], r["value"]) for r in rv] == [("mastery", "alchemy", 12.5)]
    env.auto.review({"id": rv[0]["id"], "action": "fix", "value": 12.75})
    assert env.auto.latest("mastery:alchemy")["value"] == 12.75
    with pytest.raises(ValueError):
        env.auto._commit("m.png", "mastery", "fishing", 5, T0)
    with pytest.raises(ValueError):
        env.auto._commit("m.png", "mastery", "cooking", 900, T0)


# -- slice 4: precedence + expiry -------------------------------------------------------

def _svc(tmp_path, clock, reads):
    return imperial.ImperialService(Store(tmp_path / "store"), clock=clock,
                                    reads=lambda k: reads.get(k))


def test_read_beats_older_typed_and_newer_typed_beats_read(tmp_path):
    clock, reads = Clock(), {}
    s = _svc(tmp_path, clock, reads)
    s.set_mastery({"type": "cooking", "pct": 20})
    clock.t = T0 + 600
    reads["mastery:cooking"] = {"value": 40.5, "at": _iso(T0 + 300), "source": "ocr:m.png"}
    cook = _type(s.view(), "cooking")
    assert cook["mastery_pct"] == 40.5 and cook["mastery_typed"] == 20
    s.set_mastery({"type": "cooking", "pct": 30})
    cook = _type(s.view(), "cooking")
    assert cook["mastery_pct"] == 30 and cook["mastery_source"] == "operator"
    assert cook["mastery_expires_at"] == _iso(T0 + 600 + imperial.TYPED_TTL_S)
    assert cook["mastery_expired"] is False


def test_typed_past_ttl_loses_to_an_older_read(tmp_path):
    clock, reads = Clock(), {}
    reads["cp"] = {"value": 312, "at": _iso(T0 - 600), "source": "ocr:cp.png"}
    reads["mastery:cooking"] = {"value": 40.5, "at": _iso(T0 - 600), "source": "ocr:m.png"}
    s = _svc(tmp_path, clock, reads)
    s.set_cp(80)
    s.set_mastery({"type": "cooking", "pct": 20})
    v = s.view()
    assert v["cp"]["value"] == 80 and _type(v, "cooking")["mastery_pct"] == 20
    clock.t = T0 + imperial.TYPED_TTL_S
    v = s.view()
    assert v["cp"]["value"] == 312 and v["cp"]["source"] == "ocr" and v["cp"]["typed"] == 80
    assert _type(v, "cooking")["mastery_pct"] == 40.5
    assert s.typed_overrides() == []


def test_typed_past_ttl_without_a_read_stays_and_is_flagged(tmp_path):
    clock = Clock()
    s = _svc(tmp_path, clock, {})
    s.set_cp(80)
    s.set_mastery({"type": "alchemy", "pct": 15})
    clock.t = T0 + imperial.TYPED_TTL_S + 60
    v = s.view()
    assert v["cp"]["value"] == 80 and v["cp"]["expired"] is True
    alc = _type(v, "alchemy")
    assert alc["mastery_pct"] == 15 and alc["mastery_expired"] is True
    assert [t["cap"] for t in v["types"]] == [40, 40]


def test_pre_117_mastery_without_a_set_time_loses_to_any_read(tmp_path):
    clock, reads = Clock(), {}
    store = Store(tmp_path / "store")
    store.put("imperial", {"day": "2026-10-05", "mastery": {"cooking": 20, "alchemy": 0}})
    s = imperial.ImperialService(store, clock=clock, reads=lambda k: reads.get(k))
    assert _type(s.view(), "cooking")["mastery_pct"] == 20
    assert _type(s.view(), "cooking")["mastery_source"] == "operator"
    reads["mastery:cooking"] = {"value": 40.5, "at": _iso(T0 - 30 * DAY), "source": "ocr:m"}
    assert _type(s.view(), "cooking")["mastery_pct"] == 40.5


def test_mastery_null_clears_the_typed_value(tmp_path):
    s = _svc(tmp_path, Clock(), {})
    s.set_mastery({"type": "cooking", "pct": 20})
    v = s.set_mastery({"type": "cooking", "pct": None})
    assert _type(v, "cooking")["mastery_pct"] == 0
    assert _type(v, "cooking")["mastery_source"] == "default"
    assert s.typed_overrides() == []


# -- slice 5: overrides carry the expiry -------------------------------------------------

def test_typed_overrides_carry_expires_at(tmp_path):
    clock = Clock()
    s = _svc(tmp_path, clock, {})
    s.set_cp(80)
    s.set_mastery({"type": "cooking", "pct": 20})
    rows = {r["key"]: r for r in s.typed_overrides()}
    assert sorted(rows) == ["imperial.cp", "imperial.mastery.cooking"]
    exp = _iso(T0 + imperial.TYPED_TTL_S)
    assert rows["imperial.cp"]["expires_at"] == exp
    assert rows["imperial.mastery.cooking"]["expires_at"] == exp
    assert rows["imperial.mastery.cooking"]["value"] == 20


# -- acceptance over the served app ------------------------------------------------------

def _no_network(url, timeout):
    raise AssertionError(f"network: {url}")


@pytest.fixture()
def served(tmp_path):
    clock = Clock()
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", commit="a" * 40,
                          sse_interval=0.05, market_seed=[],
                          market_client=market.ArshaClient(fetch=_no_network,
                                                           cache_dir=tmp_path / "cache"),
                          config_path=tmp_path / "local.json", profile_cfg={},
                          today_clock=clock, grind_clock=clock, deadeye_clock=clock,
                          leveling_clock=clock)
    s.market.settings = {"vp": False, "fame_pct": 0}
    t = threading.Thread(target=s.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()
    yield s, clock
    s.shutdown()
    s.server_close()


def _req(s, method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", s.server_address[1], timeout=5)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    c.request(method, path, body=None if body is None else json.dumps(body).encode(),
              headers=headers)
    r = c.getresponse()
    out = r.read()
    c.close()
    return r.status, (json.loads(out) if out else None)


@pytest.mark.server
def test_acceptance_reads_fill_the_card_and_typed_expires(served):
    s, clock = served
    st, _ = _req(s, "POST", "/api/imperial", {"cp": 80})
    assert st == 200
    _, ov = _req(s, "GET", "/api/overrides")
    row = next(i for i in ov["items"] if i["key"] == "imperial.cp")
    assert row["expires_at"] == _iso(T0 + imperial.TYPED_TTL_S)
    assert row["expires_in_s"] == int(imperial.TYPED_TTL_S)
    s.store.put("ocr_reads", {
        "cp": [{"id": "u900", "at": _iso(T0 - 600), "value": 312, "source": "ocr:cp.png"}],
        "mastery": [{"id": "u901", "at": _iso(T0 - 300), "name": "cooking", "value": 40.5,
                     "source": "ocr:m.png"}]})
    _, imp = _req(s, "GET", "/api/imperial")
    assert imp["cp"]["value"] == 80  # typed after the CP read: still in force
    assert _type(imp, "cooking")["mastery_pct"] == 40.5
    clock.t = T0 + imperial.TYPED_TTL_S
    _, imp = _req(s, "GET", "/api/imperial")
    assert imp["cp"]["value"] == 312 and imp["cp"]["source"] == "ocr"
    assert [t["cap"] for t in imp["types"]] == [156, 156]
    _, ov = _req(s, "GET", "/api/overrides")
    assert not any(i["key"].startswith("imperial.") for i in ov["items"])
