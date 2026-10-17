"""Plan 141 hardening audit, slice server-a: one test per FIXED finding
(docs/audit/20261017-server-a.md). Each failed before its fix."""

import datetime as dt
import json
from pathlib import Path

from server.ew import (autotick, bossdrift, bosses, coupons, dataverdicts, detect, eventcurrency,
                       eventnotices, gamewatch, patchverify, today)
from server.ew.store import Store

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC).timestamp()
FIX = Path(__file__).parent / "fixtures" / "notices"


# -- SERVER-A-01: autotick forgets arbitrary seen shots when it trims -----------------

class _Game:
    def __init__(self):
        self.shots = []

    def view(self):
        return {"state": "running", "screenshots": [dict(s) for s in self.shots]}


def _shots(prefix, n):
    return [{"name": f"{prefix}{i}.jpg", "size": 1, "mtime": "2026-10-17T12:00:00+00:00"}
            for i in range(n)]


def test_a01_listed_shots_stay_seen_after_the_trim(tmp_path):
    store = Store(tmp_path / "store")
    clk = lambda: T0  # noqa: E731
    rule, grants, verified = today.dice_preset()
    dice = gamewatch.DiceClock(store, rule, grants, verified=verified, clock=clk)
    reads = []

    def settings():
        reads.append(1)
        return {"checklist.auto": True}

    game = _Game()
    at = autotick.AutoTick(store, today.TodayService(store, clock=clk), dice, game,
                           table=bosses.load_table(), settings=settings, clock=clk)
    game.shots = _shots("old", 1000)
    at.scan_shots()
    game.shots = _shots("new", 50)
    at.scan_shots()  # 1050 keys seen -> trimmed to MAX_SEEN
    n = len(reads)
    at.scan_shots()  # the same 50 listed shots: nothing is fresh
    assert len(reads) == n, "a still-listed shot was forgotten by the trim and re-scanned"
    assert len(at._seen) <= autotick.MAX_SEEN


def test_a01_seen_keys_stay_bounded_while_auto_is_off(tmp_path):
    store = Store(tmp_path / "store")
    clk = lambda: T0  # noqa: E731
    rule, grants, verified = today.dice_preset()
    dice = gamewatch.DiceClock(store, rule, grants, verified=verified, clock=clk)
    game = _Game()
    at = autotick.AutoTick(store, today.TodayService(store, clock=clk), dice, game,
                           table=bosses.load_table(),
                           settings=lambda: {"checklist.auto": False}, clock=clk)
    for i in range(30):
        game.shots = _shots(f"b{i}-", 50)
        at.scan_shots()
    assert len(at._seen) <= autotick.MAX_SEEN, "the trim was skipped while auto was off"


# -- SERVER-A-02: an attempt stamp in the future blocks the check until then -------

class _Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def test_a02_future_attempt_stamp_does_not_block_the_drift_check(tmp_path):
    cfg = bossdrift.config(bosses.load_table())
    client = bossdrift.DriftClient(cfg, fetch=lambda u, t: b"", clock=_Clock(T0),
                                   cache_dir=tmp_path / "drift")
    client._record(T0 + 400 * 86400, "allow")  # clock set back / corrupt stamp
    assert client.due() is True
    client._record(T0 - 60, "allow")
    assert client.due() is False, "a real recent attempt still holds the floor"


def test_a02_future_attempt_stamp_does_not_block_the_coupon_check(tmp_path):
    client = coupons.CouponClient(fetch=lambda u, t: b"", clock=_Clock(T0),
                                  cache_dir=tmp_path / "coupons")
    client._record(T0 + 400 * 86400, "allow")
    assert client.due() is True
    client._record(T0 - 60, "allow")
    assert client.due() is False


def test_a02_detector_redetects_after_the_clock_went_back():
    calls = []

    def probe():
        calls.append(1)
        return {"install_dir": None, "documents_dir": None}

    det = detect.Detector(probe=probe, config=lambda: {}, clock=lambda: T0)
    det.refresh(T0)
    det.on_poll("unconfigured", T0 - 2 * detect.RETRY_S)
    assert len(calls) == 2, "a clock set back must not stall the hourly re-detect"
    det.on_poll("unconfigured", T0 - 2 * detect.RETRY_S + 60)
    assert len(calls) == 2, "and the hourly floor holds from the new stamp"


# -- SERVER-A-03: a corrupt verdict date in the runtime file is a 500 ----------------

def _note():
    raw = (FIX / "patch-20261008.html").read_text(encoding="utf-8")
    return {"group_no": 10670, "title": "[Updates] Patch Notes - October 8, 2026",
            "url": eventnotices.detail_url(10670), "stamp": None, "fetched_at": T0,
            "text": "\n".join(eventnotices._lines(raw))}


def test_a03_corrupt_verdict_fields_are_dropped_not_a_crash(tmp_path):
    path = tmp_path / "v.json"
    dataverdicts.VerdictService(lambda: [_note()], path=path, clock=lambda: T0).run()
    doc = json.loads(path.read_text())
    key = "xp_epochs.json#cap75-xp-rescale"
    assert doc["verdicts"][key]["verdict"] == "confirmed"
    for bad in ({"date": 5}, {"checked_at": ["x"]}, {"notice_no": True}):
        d = json.loads(json.dumps(doc))
        d["verdicts"][key].update(bad)
        path.write_text(json.dumps(d))
        svc = dataverdicts.VerdictService(lambda: [_note()], path=path, clock=lambda: T0)
        v = svc.view()["verdicts"][key]  # TypeError before the fix (date vs int)
        assert v["verdict"] == "confirmed" and isinstance(v["date"], str)
        assert isinstance(v["notice_no"], int) and not isinstance(v["notice_no"], bool)
    assert patchverify.VERDICTS  # the key set the cleaner checks against


# -- SERVER-A-04: a non-list stored row list is a 500 on Events / Today -------------

def _tick_source():
    for no, rule in eventcurrency.load_rules().items():
        for s in rule["sources"]:
            if s["kind"] in eventcurrency.TICK_KINDS:
                return no, s, rule
    raise AssertionError("the seed has no weekly / once source")


def test_a04_corrupt_wishlist_items_degrade(tmp_path):
    store = Store(tmp_path / "store")
    store.put(eventcurrency.DOMAIN, {"items": 5, "balances": {}, "ocr": {}})
    svc = eventcurrency.CurrencyService(store, clock=lambda: T0)
    assert isinstance(svc.view()["events"], list)  # TypeError before the fix
    assert svc.loss_rows() == []


def test_a04_corrupt_tick_list_degrades(tmp_path):
    no, src, rule = _tick_source()
    lo, _ = eventcurrency._span(src, rule)
    when = lo.timestamp() + 3600
    store = Store(tmp_path / "store")
    store.put(eventcurrency.TICKS_DOMAIN, {"ticks": {no: {src["id"]: 5}}})
    svc = eventcurrency.CurrencyService(store, clock=lambda: when)
    key = f"{no}:{src['id']}"
    rows = svc.untick(key)  # TypeError before the fix
    assert any(r["key"] == key and r["done"] is False for r in rows)
    rows = svc.tick_at(key, when)
    assert any(r["key"] == key and r["done"] is True for r in rows)
