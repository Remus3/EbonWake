"""Plan 109: the Value Pack state comes from the buff timer the auto-OCR arms.

An armed timer is VP on (with its end), a timer that ran out is VP off for
VP_GRACE_S, after that the fallback chain (typed / config / default) decides.
A "Value Pack" read at the 30-day cap is a normal read; a renewal read commits,
a read ending earlier than the armed timer is held for review.

AutoOcr runs over a fake ScreenShot folder with an injected OCR runner; the app
tests call the resolver directly (make_server binds 127.0.0.1:0, nothing is
served, nothing reads the game or the network).
"""

import datetime as dt
import json
import os

import pytest

from server.ew import app as ewapp
from server.ew import grind, market, ocr, ocrauto

pytestmark = pytest.mark.server

T0 = 1_800_000_000.0
HOUR = 3600.0
DAY = 86400.0


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).replace(microsecond=0).isoformat()


def _doc(*lines):
    return {"text": "\n".join(lines),
            "lines": [{"text": t, "words": [], "confidence": 95} for t in lines]}


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


class FakeGame:
    def __init__(self, shot_dir):
        self.shot_dir = shot_dir
        self.shots = []

    def add(self, name, ts, size=10):
        (self.shot_dir / name).write_bytes(b"x" * size)
        self.shots.insert(0, {"name": name, "size": size, "mtime": _iso(ts)})

    def view(self):
        return {"screenshots": [dict(s) for s in self.shots]}


def _no_network(url, timeout):
    raise AssertionError(f"network: {url}")


@pytest.fixture()
def srv(tmp_path):
    clock = Clock(T0)
    cfg = tmp_path / "local.json"
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", commit="a" * 40,
                          sse_interval=0.05, market_seed=[],
                          market_client=market.ArshaClient(fetch=_no_network,
                                                           cache_dir=tmp_path / "cache"),
                          config_path=cfg, profile_cfg={},
                          today_clock=clock, grind_clock=clock, deadeye_clock=clock,
                          leveling_clock=clock)
    s.overrides.clock = clock
    s.market.settings = {"vp": False, "fame_pct": 0}
    yield s, clock, cfg
    s.server_close()


def _auto(tmp_path, clock, store, g):
    shot_dir = tmp_path / "ScreenShot"
    shot_dir.mkdir(exist_ok=True)
    game = FakeGame(shot_dir)
    docs = {}
    reader = ocr.OcrService(game, tmp_path / "ocr", runner=lambda p: docs[p.name])
    auto = ocrauto.AutoOcr(store, game, reader, g, settings=lambda: {}, clock=clock)
    auto.on_game(None, "logged_in", T0 - 7 * DAY)
    return auto, game, docs


def _shoot(auto, game, docs, clock, name, ts, text):
    game.add(name, ts)
    docs[name] = _doc(text)
    clock.t = ts + 60
    auto.scan()
    auto.drain()


def _arm(s, minutes):
    s.grind.buff({"name": "Value Pack", "minutes": minutes})


def _vp_ends(s):
    b = next(b for b in s.store.get("grind")["buffs"] if b["name"].lower() == "value pack")
    return dt.datetime.fromisoformat(b["ends"]).timestamp()


# -- slice 1: tri-state live signal ----------------------------------------------------

def test_armed_timer_is_vp_on_with_its_end(srv):
    s, clock, _ = srv
    _arm(s, 600)
    live = s._vp_live()
    assert live == {"value": True, "signal": "vp_timer", "ends": _iso(T0 + 600 * 60)}
    assert s.tax()["vp"] is True
    row = s.settings_out(s.settings.view())["derived"]["market.vp"]
    assert row["value"] is True and row["source"] == "timer"
    assert row["ends"] == _iso(T0 + 600 * 60)


def test_ran_out_an_hour_ago_is_vp_off_and_retires_a_typed_override(srv):
    s, clock, _ = srv
    s.overrides.set("market.vp", True, source="typed")
    _arm(s, 60)
    clock.t = T0 + 2 * HOUR  # ran out 1 h ago
    assert s._vp_live() == {"value": False, "signal": "vp_expired", "ends": _iso(T0 + HOUR)}
    assert s.tax()["vp"] is False
    assert any(h["key"] == "market.vp" and h["retired_by"] == "vp_expired"
               for h in s.overrides.history())
    row = s.settings_out(s.settings.view())["derived"]["market.vp"]
    assert row["value"] is False and row["source"] == "expired"
    assert row["ends"] == _iso(T0 + HOUR)


def test_expired_timer_beats_a_config_value(srv):
    s, clock, cfg = srv
    _arm(s, 60)
    cfg.write_text(json.dumps({"market": {"vp": True}}) + "\n", encoding="ascii")
    os.utime(cfg, (T0 + 90 * 60, T0 + 90 * 60))  # written after the timer ran out
    s.market.settings = {"vp": True, "fame_pct": 0}
    clock.t = T0 + 2 * HOUR
    assert s.tax()["vp"] is False


def test_typed_after_the_timer_ran_out_wins(srv):
    s, clock, _ = srv
    _arm(s, 60)
    clock.t = T0 + 2 * HOUR
    s.overrides.set("market.vp", True, source="typed")  # bought VP, no screenshot yet
    assert s._vp_live() is None
    assert s.tax()["vp"] is True
    assert s.settings_out(s.settings.view())["derived"]["market.vp"]["source"] == "typed"


def test_after_the_grace_the_fallback_decides(srv):
    s, clock, cfg = srv
    _arm(s, 60)
    clock.t = T0 + HOUR + 8 * DAY
    assert s._vp_live() is None
    assert s.tax()["vp"] is False
    assert s.settings_out(s.settings.view())["derived"]["market.vp"]["source"] == "default"
    cfg.write_text(json.dumps({"market": {"vp": True}}) + "\n", encoding="ascii")
    os.utime(cfg, (clock.t, clock.t))
    s.market.settings = {"vp": True, "fame_pct": 0}
    assert s.tax()["vp"] is True
    assert s.settings_out(s.settings.view())["derived"]["market.vp"]["source"] == "config"


def test_grace_constant():
    assert ewapp.VP_GRACE_S == 7 * DAY


# -- slice 3: expiry surfaces --------------------------------------------------------

def test_digest_value_pack_row_from_t_minus_24h(srv):
    s, clock, _ = srv
    _arm(s, 3 * 24 * 60)
    assert s.maintdigest.view()["value_pack"] is None  # 3 days out: no row yet
    clock.t = T0 + 2 * DAY + 600
    vp = s.maintdigest.view()["value_pack"]
    assert vp == {"ends": _iso(T0 + 3 * DAY), "in_s": int(DAY - 600)}
    clock.t = T0 + 3 * DAY + 1
    assert s.maintdigest.view()["value_pack"] is None  # ran out: nothing to warn about


# -- slice 2: read confidence ----------------------------------------------------------

def test_value_pack_at_the_cap_is_a_normal_read():
    f = ocrauto.buff_fields(_doc("Value Pack 30 d"))
    assert f[0]["name"] == "Value Pack" and f[0]["value"] == grind.MAX_BUFF_MINUTES
    assert f[0]["conf"] == 1.0
    other = ocrauto.buff_fields(_doc("XP scroll 30 d"))
    assert other[0]["conf"] == ocrauto.TIME_AT_CAP  # the cap still lowers any other buff


def test_29d_23h_read_commits_at_the_gate_and_arms_vp(srv, tmp_path):
    s, clock, _ = srv
    auto, game, docs = _auto(tmp_path, clock, s.store, s.grind)
    _shoot(auto, game, docs, clock, "vp.jpg", T0, "Value Pack 29 d 23 h")
    assert [c["name"] for c in auto.view()["commits"]] == ["Value Pack"]
    assert not auto.view()["review"]
    assert s.tax()["vp"] is True  # acceptance: market net proceeds use the VP rate
    assert s.market.tax()["vp"] is True
    row = s.settings_out(s.settings.view())["derived"]["market.vp"]
    assert row["source"] == "timer"
    end = _vp_ends(s)
    clock.t = end + 1  # acceptance: the clock passing the end flips tax to no-VP
    assert s.tax()["vp"] is False
    assert s.market.tax()["vp"] is False


def test_renewal_read_extends_the_timer(srv, tmp_path):
    s, clock, _ = srv
    auto, game, docs = _auto(tmp_path, clock, s.store, s.grind)
    _arm(s, 10 * 24 * 60)
    before = _vp_ends(s)
    _shoot(auto, game, docs, clock, "renew.jpg", T0 + 600, "Value Pack 30 d")
    assert not auto.view()["review"]
    assert _vp_ends(s) > before


def test_shorter_read_is_queued(srv, tmp_path):
    s, clock, _ = srv
    auto, game, docs = _auto(tmp_path, clock, s.store, s.grind)
    _arm(s, 29 * 24 * 60)
    before = _vp_ends(s)
    _shoot(auto, game, docs, clock, "short.jpg", T0 + 600, "Value Pack 5 d")
    assert _vp_ends(s) == before
    item = next(r for r in auto.view()["review"] if r["name"] == "Value Pack")
    assert "earlier than the armed" in item["why"]
    auto.review({"id": item["id"], "action": "accept"})  # the operator's call
    assert _vp_ends(s) < before


def test_same_timer_read_again_commits(srv, tmp_path):
    s, clock, _ = srv
    auto, game, docs = _auto(tmp_path, clock, s.store, s.grind)
    _arm(s, 10 * 24 * 60)
    # 2 h later the tooltip shows 9 d 22 h (hour granularity): the same end
    _shoot(auto, game, docs, clock, "same.jpg", T0 + 2 * HOUR, "Value Pack 9 d 22 h")
    assert not auto.view()["review"]
