"""Plan 142: hardening audit server-b regression tests (docs/audit/20261017-server-b.md).

Each test pins one SERVER-B-NN finding and failed before its fix. No socket,
no git, no network: every clock and fetch is injected.
"""

import datetime as dt
import json

import pytest

from server.ew import httpcache, inventory, itemnames, knownissues, leveling
from server.ew.store import Store, atomic_write_json

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 10, 5, 12, 0, 0, tzinfo=UTC)


class Clock:
    def __init__(self, t=2_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def _client(tmp_path, clock, fetch=None):
    return httpcache.CachedClient(fetch=fetch, clock=clock, cache_dir=tmp_path / "c")


# -- SERVER-B-01: cache stamps from the future / non-finite ---------------------

def test_b01_future_fetched_at_is_stale_not_fresh_forever(tmp_path):
    """Clock moved back an hour after a fetch: the entry must not read fresh
    (and never refresh) until the clock catches up."""
    clock = Clock()
    c = _client(tmp_path, clock)
    atomic_write_json(c.cache_dir / "k.json", {"fetched_at": clock.t + 3600, "data": "old"})
    calls = []
    res = c.cached_get("k", 600, lambda: calls.append(1) or "new")
    assert calls == [1] and res["data"] == "new" and res["stale"] is False
    assert res["age_s"] == 0


def test_b01_future_fetched_at_refresh_async_starts(tmp_path):
    clock = Clock()
    c = _client(tmp_path, clock)
    atomic_write_json(c.cache_dir / "k.json", {"fetched_at": clock.t + 3600, "data": "old"})
    ran = []
    assert c.refresh_async("k", 600, lambda: "new", spawn=lambda fn: ran.append(fn)) is True
    assert len(ran) == 1  # plan 150: the refresh really was handed to spawn
    peek = c.peek("k", 600)
    assert peek["stale"] is True and peek["age_s"] >= 0


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_b01_non_finite_fetched_at_is_no_cache(tmp_path, bad):
    """json accepts NaN / Infinity; such an entry was served and iso() raised."""
    clock = Clock()
    c = _client(tmp_path, clock)
    (c.cache_dir).mkdir(parents=True)
    (c.cache_dir / "k.json").write_text('{"fetched_at": %s, "data": 1}' % bad, encoding="ascii")
    assert c.peek("k", 600) is None


# -- SERVER-B-02: backoff entries that never expire / explode -------------------

def _backoff(c, entry):
    c.cache_dir.mkdir(parents=True, exist_ok=True)
    (c.cache_dir / "backoff.json").write_text(json.dumps({"k": entry}), encoding="ascii")


def test_b02_backoff_until_beyond_max_is_expired(tmp_path):
    """A backoff `until` further out than BACKOFF_MAX_S (the clock moved back)
    must not block the key until the clock catches up."""
    clock = Clock()
    c = _client(tmp_path, clock)
    _backoff(c, {"n": 2, "until": clock.t + 30 * 86400, "error": "x"})
    calls = []
    res = c.cached_get("k", 600, lambda: calls.append(1) or "ok")
    assert calls == [1] and res["data"] == "ok"


def test_b02_backoff_infinite_until_is_expired(tmp_path):
    clock = Clock()
    c = _client(tmp_path, clock)
    c.cache_dir.mkdir(parents=True)
    (c.cache_dir / "backoff.json").write_text(
        '{"k": {"n": 1, "until": Infinity, "error": "x"}}', encoding="ascii")
    assert c.cached_get("k", 600, lambda: "ok")["data"] == "ok"


def test_b02_huge_n_does_not_hang(tmp_path):
    """A corrupt n of 10**9 made `30 * 2 ** n` a multi-hundred-MB bigint."""
    clock = Clock()
    c = _client(tmp_path, clock)
    _backoff(c, {"n": 10 ** 9, "until": 0, "error": "x"})

    def boom():
        raise httpcache.UpstreamError("down")
    res = c.cached_get("k", 600, boom)
    assert res["error"] == "down"
    bo = c.key_backoff("k")
    assert bo["until"] == clock.t + httpcache.BACKOFF_MAX_S
    assert bo["n"] <= httpcache.BACKOFF_N_MAX


def test_b02_backoff_wait_capped():
    assert httpcache.backoff_wait(0) == httpcache.BACKOFF_BASE_S
    assert httpcache.backoff_wait(10 ** 12) == httpcache.BACKOFF_MAX_S
    assert httpcache.backoff_wait(-5) == httpcache.BACKOFF_BASE_S


def test_b02_utildb_huge_n_does_not_hang(tmp_path):
    clock = Clock()
    db = itemnames.UtilDb(fetch=lambda url, t: (_ for _ in ()).throw(OSError("off")),
                          clock=clock, cache_dir=tmp_path / "u")
    db.cache_dir.mkdir(parents=True)
    (db.cache_dir / "backoff.json").write_text(
        json.dumps({"utildb": {"n": 10 ** 9, "until": 0}}), encoding="ascii")
    assert db.lookup([16080]) is None
    assert db.key_backoff("utildb")["until"] == clock.t + httpcache.BACKOFF_MAX_S


# -- SERVER-B-03: hot_add `until` out of datetime range = 400, not 500 ----------

def test_b03_hot_add_until_out_of_range_is_value_error(tmp_path):
    svc = leveling.LevelingService(Store(tmp_path / "s"), clock=lambda: T0.timestamp())
    with pytest.raises(ValueError):
        svc.hot_add({"days": [0], "start": "10:00", "end": "11:00", "label": "Hot",
                     "pct": 100, "until": "9999-12-31T23:59:00-05:00"})


# -- SERVER-B-04: known-issues load raises ValueError, never OverflowError -------

def test_b04_known_issue_out_of_range_from_is_value_error(tmp_path):
    p = tmp_path / "ki.json"
    p.write_text(json.dumps([{"id": "x", "title": "t", "affects": ["leveling"],
                              "from": "0001-01-01T00:00:00+01:00", "until": None,
                              "source": "s", "verified": False}]), encoding="ascii")
    with pytest.raises(ValueError):
        knownissues.load(p)


# -- SERVER-B-05: str.isdigit() keys before int() --------------------------------

SUPER2 = chr(0xB2)  # superscript two: isdigit() True, int() raises


def test_b05_leveling_level_xp_non_ascii_digit_key_is_dropped(tmp_path):
    store = Store(tmp_path / "s")
    svc = leveling.LevelingService(store, clock=lambda: T0.timestamp())
    doc = store.get("leveling")
    doc["level_xp"] = {SUPER2: {"total": 5, "ts": T0.isoformat()},
                       "61": {"total": 7, "ts": T0.isoformat()}}
    store.put("leveling", doc)
    assert [r["level"] for r in svc.view()["level_xp"]] == [61]


def test_b05_retry_after_non_ascii_digit_is_garbage():
    """A latin-1 header value of chr(0xB2) passed isdigit() and int() raised
    inside cached_get's error path, so no backoff was ever recorded."""
    assert httpcache.retry_after_s(SUPER2, 0) is None


def test_b05_itemnames_non_ascii_digit_keys_are_dropped(tmp_path):
    atomic_write_json(tmp_path / "idx.json", {
        "db": {SUPER2: {"name": "Bad", "fetched_at": 1.0}, "5": {"name": "Ok", "fetched_at": 1.0}},
        "cache": {SUPER2 + ":0": "Bad2", "6:0": "Ok2"}})
    clock = Clock()
    db = itemnames.UtilDb(fetch=lambda url, t: b"[]", clock=clock, cache_dir=tmp_path / "u")
    idx = itemnames.NameIndex(seed=[], market_cache_dir=tmp_path / "mc",
                              index_path=tmp_path / "idx.json", utildb=db, clock=clock)
    assert idx.name(5) == "Ok" and idx.name(6) == "Ok2"
    assert sorted(idx.catalog().values()) == ["Ok", "Ok2"]


# -- SERVER-B-06: a non-finite OCR weight read must not break the card ----------

@pytest.mark.parametrize("mx", [float("inf"), float("nan")])
def test_b06_inventory_non_finite_weight_read(tmp_path, mx):
    reads = {"weight": {"value": {"used": 10, "max": mx}, "at": T0.isoformat(),
                        "source": "ocr"}}
    svc = inventory.InventoryService(Store(tmp_path / "s"), clock=lambda: T0.timestamp(),
                                     reads=reads.get)
    v = svc.view()
    assert v["inputs"]["base_lt"]["source"] != "ocr"
    assert v["weight_now"]["max"] is None and v["weight_now"]["used"] == 10
    json.dumps(v, allow_nan=False)  # the dashboard's JSON.parse rejects Infinity / NaN
