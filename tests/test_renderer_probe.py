"""Plan 175: DX12 renderer compatibility probe.

Screenshot format-change flag over the watcher's own history (extension and
pixel size of the newest ScreenShot file), the signal-digest "renderer" row,
and the operator's overlay test-pattern result as a plan 079 override that
expires at the next client patch (plan 174 signal). No client file, memory,
packet or window access: only the watcher's file metadata and image header.
"""

import struct
import zlib

import pytest

from server.ew import overrides as ov
from server.ew import renderer, signals

NOW = 1_800_000_000.0


def _png(w, h):
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    return (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(ihdr)) + chunk
            + struct.pack(">I", zlib.crc32(chunk)))


def _jpg(w, h):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + sof + b"\xff\xd9"


def _bmp(w, h):
    return b"BM" + b"\x00" * 12 + struct.pack("<IiiHH", 40, w, -h, 1, 24)


def _shot(name, w=2560, h=1440, at=NOW - 30):
    return {"name": name, "ext": renderer.ext_of(name), "w": w, "h": h, "at": at}


# -- image header ------------------------------------------------------------------

@pytest.mark.parametrize("make,name", [(_png, "a.png"), (_jpg, "a.jpg"), (_bmp, "a.bmp")])
def test_image_size_reads_the_header(tmp_path, make, name):
    p = tmp_path / name
    p.write_bytes(make(1920, 1080))
    assert renderer.image_size(p) == (1920, 1080)


def test_image_size_unknown_or_missing_is_none(tmp_path):
    p = tmp_path / "x.webp"
    p.write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ")
    assert renderer.image_size(p) is None
    assert renderer.image_size(tmp_path / "gone.png") is None
    (tmp_path / "short.png").write_bytes(b"\x89PNG")
    assert renderer.image_size(tmp_path / "short.png") is None


def test_ext_of_is_lowercase_with_dot():
    assert renderer.ext_of("2026_11_14 Shot.PNG") == ".png"
    assert renderer.ext_of("noext") == ""


# -- format-change flag (the plan's failing-first cases) ---------------------------

def test_empty_history_is_quiet_and_records():
    hist, res = renderer.check(renderer.empty(), _shot("a.png"))
    assert res["new_ext"] is False and res["new_size"] is False
    assert [(f["ext"], f["w"], f["h"]) for f in hist["formats"]] == [(".png", 2560, 1440)]


def test_same_format_is_quiet():
    hist, _ = renderer.check(renderer.empty(), _shot("a.png"))
    hist2, res = renderer.check(hist, _shot("b.png"))
    assert res["new_ext"] is False and res["new_size"] is False
    assert hist2 == hist


def test_png_then_new_extension_flags():
    hist, _ = renderer.check(renderer.empty(), _shot("a.png"))
    hist, res = renderer.check(hist, _shot("b.webp", w=None, h=None))
    assert res["new_ext"] is True and res["new_size"] is False
    assert res["was_ext"] == [".png"]


def test_new_pixel_size_flags():
    hist, _ = renderer.check(renderer.empty(), _shot("a.png"))
    _, res = renderer.check(hist, _shot("b.png", w=1920, h=1080))
    assert res["new_size"] is True and res["new_ext"] is False


def test_flag_is_idempotent_until_a_later_shot():
    hist, _ = renderer.check(renderer.empty(), _shot("a.png"))
    hist, first = renderer.check(hist, _shot("b.jpg"))
    hist2, again = renderer.check(hist, _shot("b.jpg"))
    assert first["new_ext"] and again["new_ext"] and hist2 == hist
    _, later = renderer.check(hist, _shot("c.jpg"))
    assert later["new_ext"] is False


def test_no_shot_is_quiet_and_keeps_history():
    hist, _ = renderer.check(renderer.empty(), _shot("a.png"))
    hist2, res = renderer.check(hist, None)
    assert res["latest"] is None and not res["new_ext"] and hist2 == hist


def test_history_is_capped_and_junk_cleaned():
    hist = renderer.clean({"formats": [{"ext": 3}, "junk", {"ext": ".png", "w": 1, "h": 1,
                                                           "first_name": "a.png"}]})
    assert len(hist["formats"]) == 1
    for i in range(renderer.HISTORY_MAX + 5):
        hist, _ = renderer.check(hist, _shot(f"s{i}.png", w=100 + i, h=100))
    assert len(hist["formats"]) == renderer.HISTORY_MAX


# -- digest row --------------------------------------------------------------------

def _row(inp):
    doc = signals.digest({"renderer": inp}, NOW)
    return next(r for r in doc["rows"] if r["id"] == "renderer")


def test_digest_has_a_renderer_row_with_hints():
    assert "renderer" in signals.REASONS and signals.NAMES["renderer"] == "Renderer check"
    hints = signals.load_hints()
    for reason in signals.REASONS["renderer"]:
        assert signals.hint(hints, "renderer", reason) != signals.GENERIC_HINT, reason


def test_row_no_shot_is_off():
    r = _row({"latest": None})
    assert r["level"] == "off" and r["reason"] == "no_shot"


def test_row_same_format_is_ok_with_ext_size_age():
    r = _row({"latest": _shot("a.png"), "new_ext": False, "new_size": False})
    assert r["level"] == "ok" and r["reason"] is None and r["age_s"] == 30
    assert ".png" in r["detail"] and "2560x1440" in r["detail"]


def test_row_new_extension_warns():
    r = _row({"latest": _shot("b.webp", w=None, h=None), "new_ext": True, "new_size": False,
              "was_ext": [".png"]})
    assert r["level"] == "warn" and r["reason"] == "new_format"
    assert ".webp" in r["detail"] and ".png" in r["detail"]


def test_row_new_size_warns():
    r = _row({"latest": _shot("b.png", w=1920, h=1080), "new_ext": False, "new_size": True})
    assert r["level"] == "warn" and r["reason"] == "new_size"


def test_row_overlay_hidden_warns_and_seen_is_shown():
    hidden = {"renderer": "dx12", "seen": False, "set_at": "2026-11-14T00:00:00+00:00"}
    r = _row({"latest": _shot("a.png"), "new_ext": False, "new_size": False, "test": hidden})
    assert r["level"] == "warn" and r["reason"] == "overlay_hidden"
    seen = dict(hidden, seen=True)
    r = _row({"latest": _shot("a.png"), "new_ext": False, "new_size": False, "test": seen})
    assert r["level"] == "ok" and "overlay test: seen (dx12" in r["detail"]


def test_row_junk_input_is_warn_not_500():
    r = _row({"latest": "junk"})
    assert r["level"] in ("warn", "off")


# -- service: watcher metadata, persisted history, override with patch expiry -----

class FakeStore:
    def __init__(self):
        self.d = {}

    def get(self, k, default=None):
        return self.d.get(k, {} if default is None else default)

    def put(self, k, v):
        self.d[k] = v


class FakeGame:
    def __init__(self, docs, shots=(), other=None):
        self.documents_dir = docs
        self.shots = list(shots)
        self.other = other

    def view(self):
        return {"screenshots": list(self.shots)}

    def health(self):
        return {"other_shot": self.other}


def _iso(t):
    return ov._iso(t)


POLICY = {renderer.KEY: {"label": "Overlay test pattern", "expiry": "days:30",
                         "cards": ["system"]}}


def _svc(tmp_path, game, listed=(), clock=lambda: NOW):
    store = FakeStore()
    led = ov.OverrideLedger(store, clock=clock, policy=ov.clean_policy({"keys": POLICY}))
    svc = renderer.RendererProbe(game, store, led, listed=lambda: list(listed), clock=clock)
    return svc, store, led


def test_service_reads_newest_shot_size_and_flags_new_format(tmp_path):
    shots = tmp_path / "ScreenShot"
    shots.mkdir()
    (shots / "a.png").write_bytes(_png(2560, 1440))
    game = FakeGame(tmp_path, [{"name": "a.png", "size": 10, "mtime": _iso(NOW - 60)}])
    svc, store, _ = _svc(tmp_path, game)
    s = svc.signal()
    assert s["latest"]["ext"] == ".png" and (s["latest"]["w"], s["latest"]["h"]) == (2560, 1440)
    assert s["new_ext"] is False and store.d["renderer"]["formats"]
    (shots / "b.jpg").write_bytes(_jpg(2560, 1440))
    game.shots.insert(0, {"name": "b.jpg", "size": 10, "mtime": _iso(NOW - 10)})
    s = svc.signal()
    assert s["latest"]["name"] == "b.jpg" and s["new_ext"] is True


def test_service_sees_an_unlisted_extension_from_the_watcher(tmp_path):
    game = FakeGame(tmp_path, [{"name": "a.png", "size": 1, "mtime": _iso(NOW - 600)}])
    svc, _, _ = _svc(tmp_path, game)
    svc.signal()
    game.other = {"name": "c.webp", "size": 5, "mtime": _iso(NOW - 5)}
    s = svc.signal()
    assert s["latest"]["ext"] == ".webp" and s["new_ext"] is True


def test_service_never_reads_outside_the_screenshot_folder(tmp_path):
    game = FakeGame(tmp_path, [{"name": "..\\evil.png", "size": 1, "mtime": _iso(NOW - 5)}])
    svc, _, _ = _svc(tmp_path, game)
    s = svc.signal()
    assert s["latest"] is None


def test_record_stores_a_typed_override_with_set_at(tmp_path):
    svc, _, led = _svc(tmp_path, FakeGame(None))
    out = svc.record({"renderer": "dx12", "seen": True})
    e = led.doc()["live"][renderer.KEY]
    assert e["value"] == {"renderer": "dx12", "seen": True} and e["source"] == "typed"
    assert e["set_at"] == _iso(NOW) and out["test"]["seen"] is True
    assert svc.signal()["test"]["renderer"] == "dx12"


@pytest.mark.parametrize("body", [{}, {"renderer": "dx9", "seen": True},
                                  {"renderer": "dx12", "seen": "yes"},
                                  {"renderer": "dx12", "seen": True, "x": 1}, None])
def test_record_rejects_bad_bodies(tmp_path, body):
    svc, _, _ = _svc(tmp_path, FakeGame(None))
    with pytest.raises(ValueError):
        svc.record(body)


def _patch(when, no=1):
    return {"title": f"[Updates] Patch Notes - {when}", "group_no": no, "stamp": None, "url": ""}


def test_result_expires_at_the_next_client_patch(tmp_path):
    listed = [_patch("November 12, 2026"), _patch("January 15, 2027", 2)]
    svc, _, led = _svc(tmp_path, FakeGame(None), listed=listed)
    svc.record({"renderer": "dx11", "seen": True})  # set 2027-01-15 (NOW): same-day patch keeps
    assert svc.signal()["test"] is not None
    listed.append(_patch("January 20, 2027", 3))
    svc.listed = lambda: list(listed)
    assert svc.signal()["test"] is None
    assert led.history()[0]["retired_by"] == "patch"


def test_policy_file_covers_the_key():
    row = ov.load_policy()[renderer.KEY]
    assert row["expiry"].startswith("days:") and "system" in row["cards"]


# -- watcher: the newest file of an extension it does not list --------------------

def test_gamewatch_reports_the_newest_unlisted_file(tmp_path):
    import os

    from server.ew import gamewatch
    shots = tmp_path / "ScreenShot"
    shots.mkdir()
    gw = gamewatch.GameWatch(None, str(tmp_path), clock=lambda: NOW - 100, tasklist=lambda: False)
    for name, t in (("a.png", NOW - 50), ("b.webp", NOW - 40), ("c.jxr", NOW - 20),
                    ("old.dds", NOW - 1000)):
        (shots / name).write_bytes(b"x")
        os.utime(shots / name, (t, t))
    gw.poll()
    assert [s["name"] for s in gw.view()["screenshots"]] == ["a.png"]
    other = gw.health()["other_shot"]
    assert other["name"] == "c.jxr" and other["size"] == 1


# -- server wiring ---------------------------------------------------------------

def _no_network(url, timeout):
    raise AssertionError("test touched the network")


@pytest.fixture()
def srv(tmp_path):
    from server.ew import app as ewapp
    from server.ew import market
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", commit="a" * 40,
                          market_seed=[],
                          market_client=market.ArshaClient(fetch=_no_network,
                                                           cache_dir=tmp_path / "cache"),
                          profile_cfg={}, config_path=tmp_path / "local.json")
    yield s
    s.server_close()


@pytest.mark.server
def test_server_digest_has_renderer_row(srv):
    rows = {r["id"]: r for r in srv.signals.view()["rows"]}
    assert rows["renderer"]["level"] == "off" and rows["renderer"]["reason"] == "no_shot"


@pytest.mark.server
def test_settings_route_records_and_clears_the_test_result(srv):
    from server.ew import app as ewapp

    class H:
        server = srv
    out = ewapp.Handler._post_settings(H(), {"overlay_test": {"renderer": "dx12", "seen": False}})
    assert out["overlay_test"]["seen"] is False and out["overlay_test"]["renderer"] == "dx12"
    assert srv.settings_out(srv.settings.view())["overlay_test"]["renderer"] == "dx12"
    rows = {r["id"]: r for r in srv.signals.view()["rows"]}
    assert rows["renderer"]["reason"] == "overlay_hidden"  # a hidden overlay wins over no shot
    keys = [i["key"] for i in srv.overrides_view()["items"]]
    assert renderer.KEY in keys
    ewapp.Handler._post_settings(H(), {"clear": renderer.KEY})
    assert srv.settings_out(srv.settings.view())["overlay_test"] is None
    with pytest.raises(ValueError):
        ewapp.Handler._post_settings(H(), {"overlay_test": {"renderer": "dx12"}})
