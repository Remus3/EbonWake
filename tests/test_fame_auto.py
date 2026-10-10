"""Plan 108: the family fame bonus is derived - a persisted OCR read (store
domain `fame`) or a profile fame tier estimate; a config value never beats a
read, a typed override only while it is newer than the newest read.

AutoOcr runs over a fake ScreenShot folder with an injected OCR runner; the
app tests call the resolver directly (make_server binds 127.0.0.1:0, nothing
is served, nothing reads the game or the network).
"""

import datetime as dt
import json
import os

import pytest

from server.ew import app as ewapp
from server.ew import fameauto, grind, market, ocr, ocrauto, progress
from server.ew.store import Store

pytestmark = pytest.mark.server

T0 = 1_800_000_000.0
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
        self.listeners = []

    def add(self, name, ts, size=10):
        (self.shot_dir / name).write_bytes(b"x" * size)
        self.shots.insert(0, {"name": name, "size": size, "mtime": _iso(ts)})

    def view(self):
        return {"screenshots": [dict(s) for s in self.shots]}


def _auto(tmp_path, clock, store=None):
    shot_dir = tmp_path / "ScreenShot"
    shot_dir.mkdir(exist_ok=True)
    game = FakeGame(shot_dir)
    docs = {}
    store = store or Store(tmp_path / "store")
    g = grind.GrindService(store, clock=clock, presets=[])
    reader = ocr.OcrService(game, tmp_path / "ocr", runner=lambda p: docs[p.name])
    auto = ocrauto.AutoOcr(store, game, reader, g, settings=lambda: {}, clock=clock)
    auto.on_game(None, "logged_in", T0 - 7 * DAY)
    return auto, game, docs, store


def _shoot(auto, game, docs, clock, name, ts, pct):
    game.add(name, ts)
    docs[name] = _doc(f"Family Fame bonus +{pct:.3f}%")
    clock.t = ts + 60
    auto.scan()
    auto.drain()


# -- slice 1 / 4: persisted read, monotonic guard (AutoOcr) ------------------------

def test_committed_read_is_persisted_in_the_fame_domain(tmp_path):
    clock = Clock()
    auto, game, docs, store = _auto(tmp_path, clock)
    _shoot(auto, game, docs, clock, "sell.jpg", T0, 1.25)
    assert auto.fame_read() == {"value": 1.25, "at": _iso(T0), "source": "ocr",
                                "file": "sell.jpg"}
    assert store.get("fame")["value"] == 1.25


def test_read_survives_commit_rotation_and_a_restart(tmp_path):
    clock = Clock()
    auto, game, docs, store = _auto(tmp_path, clock)
    _shoot(auto, game, docs, clock, "sell.jpg", T0, 1.25)
    for i in range(ocrauto.MAX_COMMITS + 1):
        auto._commit("s.jpg", "silver", "silver", 1000 + i, T0 + 120 + i)
    store.put("ocr_reads", {})  # the bounded read list rotated out too
    assert not [c for c in auto.view()["commits"] if c["kind"] == "fame"]
    again, *_ = _auto(tmp_path, clock, store=Store(tmp_path / "store"))  # restart
    assert again.fame_read()["value"] == 1.25


def test_lower_read_is_queued_two_agreeing_lower_reads_commit(tmp_path):
    clock = Clock()
    auto, game, docs, store = _auto(tmp_path, clock)
    _shoot(auto, game, docs, clock, "a.jpg", T0, 1.25)
    _shoot(auto, game, docs, clock, "b.jpg", T0 + 600, 0.25)  # a misread
    assert auto.fame_read()["value"] == 1.25
    item = next(r for r in auto.view()["review"] if r["kind"] == "fame")
    assert "fame went down" in item["why"] and item["value"] == 0.25
    _shoot(auto, game, docs, clock, "c.jpg", T0 + 1200, 0.5)    # disagrees: queued too
    assert auto.fame_read()["value"] == 1.25
    _shoot(auto, game, docs, clock, "d.jpg", T0 + 1800, 0.25)   # agrees with b.jpg
    assert auto.fame_read() == {"value": 0.25, "at": _iso(T0 + 1800), "source": "ocr",
                                "file": "d.jpg"}
    assert [r["file"] for r in auto.view()["review"] if r["kind"] == "fame"] == ["c.jpg"]


def test_same_screenshot_twice_never_agrees_with_itself(tmp_path):
    clock = Clock()
    auto, game, docs, store = _auto(tmp_path, clock)
    _shoot(auto, game, docs, clock, "a.jpg", T0, 1.25)
    _shoot(auto, game, docs, clock, "b.jpg", T0 + 600, 0.25)
    auto._enqueue_review("b.jpg", {"kind": "fame", "name": "fame", "value": 0.25, "conf": 0.9,
                                   "why": "fame % with decimals"}, T0 + 600)
    _shoot(auto, game, docs, clock, "b.jpg", T0 + 700, 0.25)  # a new key, same file name
    assert auto.fame_read()["value"] == 1.25


def test_higher_or_equal_read_commits_and_review_accept_wins(tmp_path):
    clock = Clock()
    auto, game, docs, store = _auto(tmp_path, clock)
    _shoot(auto, game, docs, clock, "a.jpg", T0, 1.0)
    _shoot(auto, game, docs, clock, "b.jpg", T0 + 600, 1.0)
    _shoot(auto, game, docs, clock, "c.jpg", T0 + 1200, 1.25)
    assert auto.fame_read()["file"] == "c.jpg"
    _shoot(auto, game, docs, clock, "d.jpg", T0 + 1800, 0.75)
    item = next(r for r in auto.view()["review"] if r["kind"] == "fame")
    auto.review({"id": item["id"], "action": "accept"})  # the operator's call
    assert auto.fame_read()["value"] == 0.75


def test_older_shot_never_replaces_the_newest_read_and_undo_falls_back(tmp_path):
    clock = Clock()
    auto, game, docs, store = _auto(tmp_path, clock)
    _shoot(auto, game, docs, clock, "a.jpg", T0, 1.0)
    _shoot(auto, game, docs, clock, "b.jpg", T0 + 600, 1.25)
    _shoot(auto, game, docs, clock, "old.jpg", T0 - 600, 0.5)  # was lower back then
    assert auto.fame_read()["file"] == "b.jpg"
    assert not [r for r in auto.view()["review"] if r["kind"] == "fame"]
    uid = next(c["id"] for c in auto.view()["commits"] if c.get("file") == "b.jpg")
    auto.undo(uid)
    assert auto.fame_read()["file"] == "a.jpg"


# -- slice 3: the tier table ---------------------------------------------------------

def test_tier_table_shipped_unverified_and_estimate():
    doc = json.loads(fameauto.TIERS_FILE.read_text(encoding="ascii"))
    assert doc["verified"] is False and "source" in doc and "read" in doc
    t = fameauto.clean_tiers({"verified": False, "tiers": [
        {"min_fame": 4000, "pct": 1.0}, {"min_fame": 1000, "pct": 0.5}, {"min_fame": "x"},
        {"min_fame": 7000, "pct": 9}]})
    assert t["tiers"] == [(1000, 0.5), (4000, 1.0)]
    assert fameauto.estimate(t, 999) is None
    assert fameauto.estimate(t, 4000) == 1.0
    assert fameauto.estimate(fameauto.clean_tiers({}), 99999) is None
    assert fameauto.profile_fame({"combat_fame": 3000, "life_fame": 1500}) == 4500
    assert fameauto.profile_fame({"life_fame": 20}) == 20
    assert fameauto.profile_fame({"name": "x"}) is None


# -- slice 2 / 3: precedence in the app resolver -------------------------------------

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
    s.fame_tiers = fameauto.clean_tiers({})
    yield s, clock, cfg
    s.server_close()


def _no_network(url, timeout):
    raise AssertionError(f"network: {url}")


def _config(s, cfg, pct, mtime):
    cfg.write_text(json.dumps({"market": {"fame_pct": pct}}) + "\n", encoding="ascii")
    os.utime(cfg, (mtime, mtime))
    s.market.settings = {"vp": False, "fame_pct": pct}


def _read(s, pct, at, file="sell.jpg"):
    s.store.put("fame", {"value": pct, "at": _iso(at), "source": "ocr", "file": file})


def test_acceptance_config_newer_than_the_read_never_wins(srv):
    s, clock, cfg = srv
    _read(s, 1.25, T0 - 2 * DAY)
    _config(s, cfg, 0.5, T0)
    assert s.tax()["fame_pct"] == 1.25
    row = s._fame_row()
    assert row["value"] == 1.25 and row["source"] == "ocr"
    assert row["age_s"] == 2 * DAY


def test_config_is_the_fallback_without_a_read(srv):
    s, clock, cfg = srv
    _config(s, cfg, 0.5, T0 - DAY)
    assert s.tax()["fame_pct"] == 0.5
    assert s._fame_row()["source"] == "config"


def test_typed_newer_than_the_read_wins_then_a_newer_read_retires_it(srv):
    s, clock, cfg = srv
    _read(s, 1.25, T0 - 600)
    s.overrides.set("market.fame_pct", 0.75, source="typed")
    assert s.tax()["fame_pct"] == 0.75
    assert s._fame_row()["source"] == "typed"
    clock.t = T0 + 600
    _read(s, 1.5, T0 + 300)
    assert s.tax()["fame_pct"] == 1.5
    assert any(h["key"] == "market.fame_pct" and h["retired_by"] == "ocr_fame"
               for h in s.overrides.history())


def test_legacy_ocr_reads_list_still_counts(srv):
    s, clock, cfg = srv
    s.store.put("ocr_reads", {"fame": [{"id": "u9", "at": _iso(T0 - 60), "value": 1.0,
                                        "source": "ocr:sell.jpg"}]})
    assert s.tax()["fame_pct"] == 1.0
    assert s._fame_row()["source"] == "ocr"


def _profile(s, tmp_path, clock, combat, life):
    h = progress.ProfileHistory(tmp_path / "hist.jsonl", clock=clock)
    h.append([{"name": "Main", "main": True, "combat_fame": combat, "life_fame": life}])
    s.progress.history = h


def test_profile_tier_fallback_only_without_a_read(srv, tmp_path):
    s, clock, cfg = srv
    s.fame_tiers = fameauto.clean_tiers({"verified": False, "tiers": [
        {"min_fame": 1000, "pct": 0.5}, {"min_fame": 4000, "pct": 1.0}]})
    _profile(s, tmp_path, clock, 3000, 1500)
    assert s.tax()["fame_pct"] == 1.0
    row = s._fame_row()
    assert row["source"] == "profile" and row["note"] == "estimated from profile fame"
    _read(s, 1.25, T0 - 3 * DAY)  # any OCR read beats the estimate
    assert s.tax()["fame_pct"] == 1.25 and s._fame_row()["source"] == "ocr"


def test_empty_tier_table_means_no_profile_fallback(srv, tmp_path):
    s, clock, cfg = srv
    _profile(s, tmp_path, clock, 3000, 1500)
    assert s.tax()["fame_pct"] == 0
    assert s._fame_row()["source"] == "default"


def test_settings_view_carries_the_derived_fame_row(srv):
    s, clock, cfg = srv
    _read(s, 1.25, T0 - 600)
    out = s.settings_out(s.settings.view())
    assert out["derived"]["market.fame_pct"]["value"] == 1.25
    assert out["derived"]["market.fame_pct"]["source"] == "ocr"
