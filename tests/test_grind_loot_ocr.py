"""Plan 113: grind loot OCR kind. A loot-window shot read during an auto grind
session matches the spot's loot table first, then the plan 028 item-name
catalog; the counts (a newer shot replaces the running total) are applied to the
auto session when it closes, priced from the plan 002 cache (never fetched in
the close path) with VP / fame from tax(). Stub OCR docs only; nothing runs
Tesseract or reads the game."""

import datetime as dt

import pytest

from server.ew import grind, ocr, ocrauto
from server.ew.store import Store

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 10, 5, 10, 0, 0, tzinfo=UTC).timestamp()
MIN = 60.0
M = 1_000_000

ARCS, SBMC, TRACE = "Ancient Relic Crystal Shard", "Sealed Black Magic Crystal", "Trace of Nature"
TABLES = {"hystria": {"source": "fixture", "verified": False, "items": [
    {"name": ARCS, "marketable": True, "id": 4987},
    {"name": TRACE, "marketable": False, "vendor_price": 1000}]}}
CATALOG = {(4990, 0): SBMC, (16001, 0): "Black Stone (Armor)", (721003, 0): "Caphras Stone",
           (5301, 0): "Coal", (4987, 0): ARCS, (4990, 5): "+5 should never match"}
PRICES = {4987: 2 * M, 4990: 5 * M}


def iso(ts):
    return dt.datetime.fromtimestamp(ts, UTC).isoformat()


def _doc(*texts):
    return {"text": "\n".join(texts),
            "lines": [{"text": t, "x": 0, "y": 30 * i, "w": 300, "h": 20}
                      for i, t in enumerate(texts)]}


# -- slice 1: extract_loot catalog second pass ----------------------------------------

def test_off_table_line_matched_via_the_catalog():
    out = ocr.extract_loot([f"{ARCS} x12", f"{SBMC} x2", "Mystery Thing x4"], [ARCS],
                           catalog=CATALOG)
    by = {r["name"]: r for r in out["rows"]}
    assert by[ARCS]["source"] == "table" and by[ARCS]["count"] == 12
    cat = by[SBMC]
    assert cat == {"name": SBMC, "count": 2, "confidence": ocr.CATALOG_CONF_SCALE,
                   "id": 4990, "marketable": True, "source": "catalog"}
    assert out["unmatched"] == ["Mystery Thing x4"]


def test_distance_two_on_a_long_name_none_on_a_short_one():
    rows = ocr.parse_loot(["Sealed Biack Magic Crystai x2", "Coel x3"], [], catalog=CATALOG)
    assert [(r["name"], r["id"], r["count"]) for r in rows] == [(SBMC, 4990, 2)]
    assert rows[0]["confidence"] < ocr.CATALOG_CONF_SCALE  # lowered for the distance
    assert ocr.parse_loot(["Sealxd Biack Magic Crystai x2"], [], catalog=CATALOG) == []  # 3 edits
    assert [r["name"] for r in ocr.parse_loot(["Coal x3"], [], catalog=CATALOG)] == ["Coal"]


def test_catalog_skips_enhanced_sids_and_table_names_win():
    rows = ocr.parse_loot(["+5 should never match x1", f"{ARCS} x3"], [ARCS], catalog=CATALOG)
    assert [(r["name"], r["source"]) for r in rows] == [(ARCS, "table")]


# -- pipeline -------------------------------------------------------------------------

class FakeGame:
    def __init__(self, shot_dir):
        self.shot_dir = shot_dir
        self.shots = []

    def add(self, name, ts, size=10):
        (self.shot_dir / name).write_bytes(b"x" * size)
        self.shots.insert(0, {"name": name, "size": size, "mtime": iso(ts)})

    def view(self):
        return {"screenshots": [dict(s) for s in self.shots]}


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def env(tmp_path):
    shot_dir = tmp_path / "ScreenShot"
    shot_dir.mkdir()
    game = FakeGame(shot_dir)
    docs = {}
    clock = Clock(T0)
    store = Store(tmp_path / "store")
    prices = dict(PRICES)
    fetched = []

    def fetch(iid):  # the live (fetching) price path: never used on close
        fetched.append(iid)
        return prices.get(iid)
    g = grind.GrindService(store, clock=clock, presets=[], loot_tables=TABLES, prices=fetch,
                           tax=lambda: {"vp": True, "fame_pct": 1.0})
    g.cached_price = prices.get
    reader = ocr.OcrService(game, tmp_path / "ocr", runner=lambda p: docs[p.name])
    auto = ocrauto.AutoOcr(store, game, reader, g, settings=lambda: {}, clock=clock,
                           loot_target=g.loot_target, catalog=lambda: dict(CATALOG))
    g.ocr_loot = auto.loot_prefill
    auto.on_change = g.refill_loot
    g.add_spot("Hystria")
    g.log({"spot": "hystria", "minutes": 5, "silver": 0, "trash": 0})
    started = iso(T0)
    assert g.auto_start(started)["spot"] == "hystria"
    auto.on_game(None, "logged_in", T0 - 60)

    class Env:
        pass

    e = Env()
    e.__dict__.update(game=game, docs=docs, clock=clock, store=store, grind=g, auto=auto,
                      started=started, prices=prices, fetched=fetched)
    return e


def _shots(e, shots):
    for name, ts, doc in shots:
        e.game.add(name, ts)
        e.docs[name] = doc
    e.clock.t = max(e.clock.t, max(ts for _, ts, _ in shots) + 60)
    e.auto.scan()
    e.auto.drain()


def _net(price, count):
    return price * count * 6500 * 13100 // 10 ** 8  # 35 % tax, VP +30 %, fame +1 %


def _last(e):
    return e.grind.view()["sessions"][0]


def test_acceptance_auto_close_applies_three_loot_rows_with_the_hand_value(env):
    _shots(env, [("l1.jpg", T0 + 10 * MIN, _doc(f"{ARCS} x5", f"{TRACE} x100")),
                 ("l2.jpg", T0 + 50 * MIN, _doc(f"{ARCS} x12", f"{TRACE} x300", f"{SBMC} x2"))])
    sid = env.grind.auto_stop(env.started, iso(T0 + 60 * MIN))
    s = _last(env)
    assert s["id"] == sid and s["auto"] is True and s["loot_src"] == "ocr"
    rows = {r["name"]: r for r in s["loot"]}
    assert set(rows) == {ARCS, TRACE, SBMC}
    assert (rows[ARCS]["count"], rows[TRACE]["count"], rows[SBMC]["count"]) == (12, 300, 2)
    assert (rows[ARCS]["source"], rows[TRACE]["source"], rows[SBMC]["source"]) == (
        "table", "table", "catalog")
    assert rows[SBMC]["id"] == 4990 and rows[SBMC]["kind"] == "market"
    want = 20_436_000 + 8_515_000 + 300_000
    assert want == _net(2 * M, 12) + _net(5 * M, 2) + 300 * 1000
    assert s["loot_value"]["total"] == want and s["valued_silver"] == want
    assert s["loot_value"]["unknown"] == []
    assert env.fetched == []  # no fetch in the close path


def test_missing_price_is_unknown_then_valued_by_the_next_refresh(env):
    del env.prices[4990]
    _shots(env, [("l1.jpg", T0 + 10 * MIN, _doc(f"{SBMC} x2"))])
    env.grind.auto_stop(env.started, iso(T0 + 60 * MIN))
    s = _last(env)
    assert s["loot_value"]["unknown"] == [SBMC] and s["loot_value"]["total"] == 0
    env.prices[4990] = 5 * M
    assert env.grind.refill_loot() == s["id"]
    s = _last(env)
    assert s["loot_value"]["unknown"] == [] and s["loot_value"]["total"] == _net(5 * M, 2)
    assert env.grind.refill_loot() is None  # nothing changed: no write


def test_a_newer_shot_replaces_the_running_total_and_an_older_one_never_does(env):
    _shots(env, [("l2.jpg", T0 + 40 * MIN, _doc(f"{SBMC} x7"))])
    _shots(env, [("l1.jpg", T0 + 20 * MIN, _doc(f"{SBMC} x3"))])  # read later, taken earlier
    env.grind.auto_stop(env.started, iso(T0 + 60 * MIN))
    assert {r["name"]: r["count"] for r in _last(env)["loot"]} == {SBMC: 7}


def test_loot_value_beats_the_silver_delta_and_the_delta_stays_without_loot(env):
    d = {"silver": 40 * M, "first": iso(T0), "last": iso(T0 + 50 * MIN), "n": 2, "conf": 1.0}
    _shots(env, [("l1.jpg", T0 + 10 * MIN, _doc(f"{ARCS} x1"))])
    env.grind.auto_stop(env.started, iso(T0 + 60 * MIN), silver=d)
    s = _last(env)
    assert s["silver"] == 40 * M and s["valued_silver"] == _net(2 * M, 1)
    started2 = iso(T0 + 120 * MIN)
    env.grind.auto_start(started2)
    env.grind.auto_stop(started2, iso(T0 + 180 * MIN), silver=dict(d))
    s = _last(env)
    assert s.get("loot") is None and s["valued_silver"] == 40 * M


def test_a_late_shot_read_after_the_close_fills_the_closed_session(env):
    env.grind.auto_stop(env.started, iso(T0 + 60 * MIN))
    assert _last(env).get("loot") is None
    _shots(env, [("late.jpg", T0 + 55 * MIN, _doc(f"{SBMC} x4"))])  # taken before the close
    s = _last(env)
    assert s["loot_src"] == "ocr" and {r["name"]: r["count"] for r in s["loot"]} == {SBMC: 4}
    # a shot taken well after the close is no loot of that session
    _shots(env, [("after.jpg", T0 + 90 * MIN, _doc(f"{SBMC} x99"))])
    assert {r["name"]: r["count"] for r in _last(env)["loot"]} == {SBMC: 4}


def test_low_confidence_rows_go_to_review_accept_fix_and_discard(env):
    _shots(env, [("l1.jpg", T0 + 10 * MIN, _doc("Sealed Biack Magic Crystai x2",
                                                "Caphras Stane x9"))])
    rev = [i for i in env.auto.view()["review"] if i["kind"] == "loot"]
    assert len(rev) == 2 and all(i["conf"] < ocrauto.AUTO_COMMIT_MIN for i in rev)
    assert env.store.get("ocr_loot").get("items") in (None, {})
    by = {i["value"]["name"]: i for i in rev}
    env.auto.review({"id": by[SBMC]["id"], "action": "fix", "value": 3})
    env.auto.review({"id": by["Caphras Stone"]["id"], "action": "discard"})
    with pytest.raises(ValueError):
        env.auto.review({"id": "r999", "action": "accept"})
    env.grind.auto_stop(env.started, iso(T0 + 60 * MIN))
    assert {r["name"]: r["count"] for r in _last(env)["loot"]} == {SBMC: 3}


def test_an_accepted_loot_review_undoes_while_unchanged(env):
    _shots(env, [("l1.jpg", T0 + 10 * MIN, _doc("Caphras Stane x9"))])
    rid = env.auto.view()["review"][0]["id"]
    env.auto.review({"id": rid, "action": "accept"})
    items = env.store.get("ocr_loot")["items"]
    assert items["Caphras Stone"]["count"] == 9 and items["Caphras Stone"]["id"] == 721003
    uid = env.auto.view()["commits"][0]["id"]
    env.auto.undo(uid)
    assert "Caphras Stone" not in env.store.get("ocr_loot")["items"]
    with pytest.raises(ValueError):
        env.auto.review({"id": rid, "action": "fix", "value": 0})  # gone already


def test_catalog_rows_become_auto_watch_candidates(env):
    del env.prices[4990]
    _shots(env, [("l1.jpg", T0 + 10 * MIN, _doc(f"{SBMC} x2", f"{ARCS} x3"))])
    env.grind.auto_stop(env.started, iso(T0 + 60 * MIN))
    got = {i["id"]: i["count"] for i in env.grind.loot_candidates()["items"]}
    assert got == {4987: 3, 4990: 2}


def test_app_curate_refills_loot_then_syncs_and_tolerates_a_failure():
    from server.ew import app as ewapp
    calls = []

    class G:
        def refill_loot(self):
            calls.append("refill")
            return "s1"

    class Fake:
        grind = G()
        autowatch = type("A", (), {"sync": lambda self: calls.append("sync")})()
        bus = type("B", (), {"bump": lambda self, d: calls.append(d)})()

    ewapp.EWServer._curate(Fake())
    assert calls == ["refill", "grind", "sync"]
    Fake.grind = object()  # no refill_loot: still curates
    calls.clear()
    ewapp.EWServer._curate(Fake())
    assert calls == ["sync"]


def test_name_index_catalog_merges_without_fetching(tmp_path):
    from server.ew import itemnames

    class NoNet:
        def lookup(self, ids):
            raise AssertionError("catalog() must never fetch")
    idx = itemnames.NameIndex([{"id": 4990, "sid": 0, "name": SBMC}], tmp_path / "mc",
                              tmp_path / "names.json", NoNet(), clock=lambda: T0)
    assert idx.catalog() == {(4990, 0): SBMC}


def test_loot_kind_is_registered_and_checked():
    assert "loot" in ocrauto.KINDS and "loot" in ocrauto.FIX_KINDS
    ok = {"name": SBMC, "count": 2, "id": 4990, "source": "catalog", "spot": "hystria",
          "started": iso(T0)}
    assert ocrauto._check_value("loot", ok) == ok
    for bad in (dict(ok, count=0), dict(ok, source="x"), dict(ok, extra=1), "x",
                dict(ok, name="")):
        with pytest.raises(ValueError):
            ocrauto._check_value("loot", bad)


def test_the_running_session_still_offers_the_prefill(env):
    _shots(env, [("l1.jpg", T0 + 10 * MIN, _doc(f"{ARCS} x5", f"{SBMC} x1"))])
    p = env.grind.loot("hystria")["prefill"]
    # the manual loot form lists the spot's own items only
    assert {r["name"]: r["count"] for r in p["items"]} == {ARCS: 5}
