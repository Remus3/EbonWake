"""Plan 169: Imperial Reward Seal ledger - per-category seal counts, exchange
affordability, the Golden Seal conversion countdown + before-maintenance
digest row, the unknown-rate wording, the data file schema and the
/api/imperial wiring."""

import copy
import datetime as dt
import json

import pytest

from server.ew import app as ewapp
from server.ew import imperial, maint, maintdigest, patchverify, seals
from server.ew.store import Store

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 11, 20, 12, 0, tzinfo=UTC).timestamp()
CONVERT = dt.datetime(2026, 12, 3, 7, 0, tzinfo=UTC)  # default Thursday 07:00 UTC slot


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


def _data(tmp_path, exchange=(), rate=None):
    doc = json.loads(seals.DATA_PATH.read_text(encoding="ascii"))
    doc["exchange"] = list(exchange)
    doc["golden"]["rate"] = rate
    p = tmp_path / "reward_seals.json"
    p.write_text(json.dumps(doc), encoding="ascii")
    return p


ROW = {"id": "cooking-box-a", "category": "cooking", "item": "Box A", "cost": 10, "limit": None,
       "source": "https://example.org/seals", "verified": False}


def svc(tmp_path, exchange=(), rate=None, clock=None, maint_inputs=None):
    return seals.SealService(Store(tmp_path / "store"), clock=clock or Clock(),
                             data_path=_data(tmp_path, exchange, rate),
                             maint_inputs=maint_inputs)


# --- data file ----------------------------------------------------------------------

def test_data_file_schema_ascii_and_sources():
    raw = seals.DATA_PATH.read_bytes()
    assert all(b < 128 for b in raw) and b"\r" not in raw
    doc = seals.load_data()
    assert [c["id"] for c in doc["categories"]] == list(seals.CATEGORIES)
    assert seals.CATEGORIES == ("cooking", "fishing", "subjugation", "training",
                                "work-supervisor", "alchemy")
    g = doc["golden"]
    assert g["converts"] == "2026-12-03" and g["rate"] is None
    for row in doc["categories"] + [g] + doc["exchange"]:
        assert isinstance(row["source"], str) and row["source"]
        assert row["verified"] is False or isinstance(row["verified"], str)


def test_data_rows_are_patch_verifier_rows():
    """Plan 085: every seal row carries `verified`; hinted rows compile."""
    got = patchverify.load()
    keys = set(got["hinted"]) | set(got["unchecked"])
    assert any(k.startswith("reward_seals.json#") for k in keys)
    assert "reward_seals.json#golden-seal" in keys


@pytest.mark.parametrize("mut", [
    lambda d: d.pop("golden"),
    lambda d: d["categories"].pop(),
    lambda d: d["categories"][0].update(id="mining"),
    lambda d: d["golden"].update(converts="2026-13-03"),
    lambda d: d["golden"].update(rate=5),
    lambda d: d["golden"].update(verified="yes"),
    lambda d: d["exchange"].append(dict(ROW, category="mining")),
    lambda d: d["exchange"].append(dict(ROW, cost=0)),
    lambda d: d["exchange"].append(dict(ROW, limit=0)),
    lambda d: d["exchange"].append(dict(ROW, item="caf" + chr(0xE9))),
    lambda d: d["exchange"].extend([ROW, ROW]),
    lambda d: d["exchange"].append(dict(ROW, id="cooking-other")),  # id != category-slug(item)
    lambda d: d["exchange"].append(dict(ROW, extra=1)),
])
def test_validate_rejects_malformed(mut):
    doc = copy.deepcopy(seals.load_data())
    mut(doc)
    with pytest.raises(ValueError):
        seals.validate_data(doc)


def test_broken_data_file_never_breaks_the_view(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{", encoding="ascii")
    s = seals.SealService(Store(tmp_path / "store"), clock=Clock(), data_path=p)
    v = s.view()
    assert v["data_error"] and v["categories"] and v["golden"]["date"] is None


# --- pure math ----------------------------------------------------------------------

def test_totals_sum_known_counts_only():
    t = seals.totals({"cooking": 5, "fishing": None, "alchemy": 7})
    assert t == {"total": 12, "known": 2, "unknown": ["fishing", "subjugation", "training",
                                                       "work-supervisor"]}
    assert seals.totals({}) == {"total": 0, "known": 0, "unknown": list(seals.CATEGORIES)}


def test_affordability_and_nearest():
    rows = [dict(ROW, id="cooking-a", item="a", cost=4), dict(ROW, id="cooking-b", item="b", cost=10),
            dict(ROW, id="cooking-c", item="c", cost=25),
            dict(ROW, id="fishing-d", category="fishing", item="d", cost=3)]
    out = seals.afford(rows, {"cooking": 10})
    by = {r["id"]: r for r in out}
    assert [(by[k]["afford"], by[k]["times"], by[k]["short"]) for k in
            ("cooking-a", "cooking-b", "cooking-c")] == [(True, 2, 0), (True, 1, 0), (False, 0, 15)]
    assert (by["fishing-d"]["afford"], by["fishing-d"]["times"], by["fishing-d"]["short"]) == (
        None, None, None)  # count unknown: never guessed
    near = seals.nearest(out)
    assert near["cooking"] == {"ready": "cooking-b", "next": "cooking-c"}
    assert near["fishing"] == {"ready": None, "next": None}
    assert near["alchemy"] == {"ready": None, "next": None}


def test_nearest_next_is_smallest_shortfall():
    rows = [dict(ROW, id="cooking-a", item="a", cost=40), dict(ROW, id="cooking-b", item="b", cost=12)]
    near = seals.nearest(seals.afford(rows, {"cooking": 2}))
    assert near["cooking"] == {"ready": None, "next": "cooking-b"}


# --- Golden Seal conversion ------------------------------------------------------------

def _now(t):
    return dt.datetime.fromtimestamp(t, UTC)


def test_conversion_warning_before_date_with_held_seals():
    c = seals.conversion(3, "2026-12-03", None, _now(T0), CONVERT)
    assert c["warn"] is True and c["passed"] is False and c["held"] == 3
    assert c["at_utc"] == "2026-12-03T07:00:00+00:00"
    assert c["in_s"] == int((CONVERT - _now(T0)).total_seconds())
    assert c["rate"] is None
    assert seals.UNKNOWN_RATE in c["text"] and "3 Golden Seals" in c["text"]
    assert "2026-12-03" in c["text"]


def test_conversion_unknown_count_still_warns_none_held_does_not():
    c = seals.conversion(None, "2026-12-03", None, _now(T0), CONVERT)
    assert c["warn"] is True and "count not typed" in c["text"]
    c0 = seals.conversion(0, "2026-12-03", None, _now(T0), CONVERT)
    assert c0["warn"] is False and c0["passed"] is False


def test_conversion_passed_after_maintenance_start():
    after = CONVERT + dt.timedelta(minutes=1)
    c = seals.conversion(3, "2026-12-03", None, after, CONVERT)
    assert c["passed"] is True and c["warn"] is False and c["in_s"] == 0
    assert "converted" in c["text"]


def test_unknown_rate_wording_and_known_rate_wording():
    c = seals.conversion(3, "2026-12-03", None, _now(T0), CONVERT)
    assert c["rate_text"] == seals.UNKNOWN_RATE == "conversion rate not announced"
    k = seals.conversion(3, "2026-12-03", "1 Golden Seal = 10 Reward Seals", _now(T0), CONVERT)
    assert k["rate_text"] == "1 Golden Seal = 10 Reward Seals"
    assert seals.UNKNOWN_RATE not in k["text"] and "1 Golden Seal = 10 Reward Seals" in k["text"]


# --- service ----------------------------------------------------------------------------

def test_service_counts_persist_and_validate(tmp_path):
    s = svc(tmp_path, exchange=[ROW])
    v = s.set_count({"category": "cooking", "count": 12})
    assert v["counts"]["cooking"] == 12 and v["totals"]["total"] == 12
    v = s.set_count({"category": "golden", "count": 4})
    assert v["golden"]["held"] == 4 and v["totals"]["total"] == 12  # golden is not a category
    s2 = seals.SealService(Store(tmp_path / "store"), clock=Clock(), data_path=_data(tmp_path, [ROW]))
    assert s2.view()["counts"]["cooking"] == 12
    v = s.set_count({"category": "cooking", "count": None})
    assert v["counts"]["cooking"] is None
    for bad in ({"category": "mining", "count": 1}, {"category": "cooking", "count": -1},
                {"category": "cooking", "count": True}, {"category": "cooking"},
                {"category": "cooking", "count": seals.COUNT_MAX + 1}, "x"):
        with pytest.raises(ValueError):
            s.set_count(bad)


def test_service_exchange_rows_and_nearest(tmp_path):
    s = svc(tmp_path, exchange=[ROW])
    v = s.ex_add({"category": "cooking", "item": "Big box", "cost": 30})
    assert [r["id"] for r in v["exchange"]] == ["cooking-box-a", "cooking-big-box"]
    assert {r["origin"] for r in v["exchange"]} == {"seed", "operator"}
    v = s.set_count({"category": "cooking", "count": 12})
    assert v["nearest"]["cooking"] == {"ready": "cooking-box-a", "next": "cooking-big-box"}
    with pytest.raises(ValueError):
        s.ex_add({"category": "cooking", "item": "Box A", "cost": 5})  # seed id taken
    with pytest.raises(ValueError):
        s.ex_add({"category": "cooking", "item": "x", "cost": 0})
    with pytest.raises(ValueError):
        s.ex_del("cooking-box-a")  # seed rows live in the data file
    v = s.ex_del("cooking-big-box")
    assert [r["id"] for r in v["exchange"]] == ["cooking-box-a"]


def test_service_golden_countdown_uses_maintenance_slot_and_notice(tmp_path):
    s = svc(tmp_path)
    s.set_count({"category": "golden", "count": 2})
    g = s.view()["golden"]
    assert g["at_utc"] == "2026-12-03T07:00:00+00:00" and g["warn"] is True
    notices = {"2026-12-03": {"start_utc": "2026-12-03T06:00:00+00:00",
                              "end_utc": "2026-12-03T10:00:00+00:00", "source": "notice"}}
    s2 = svc(tmp_path, maint_inputs=lambda: {"slot": None, "notices": notices})
    assert s2.view()["golden"]["at_utc"] == "2026-12-03T06:00:00+00:00"
    s3 = svc(tmp_path, maint_inputs=lambda: 1 / 0)  # a broken source = the default slot
    assert s3.view()["golden"]["at_utc"] == "2026-12-03T07:00:00+00:00"


def test_digest_rows_only_while_warning(tmp_path):
    clock = Clock()
    s = svc(tmp_path, clock=clock)
    s.set_count({"category": "golden", "count": 0})
    assert s.digest_rows() == []
    s.set_count({"category": "golden", "count": 5})
    rows = s.digest_rows()
    assert len(rows) == 1 and rows[0]["kind"] == "seal"
    assert rows[0]["ends"] == "2026-12-03T07:00:00+00:00"
    assert "5 Golden Seals" in rows[0]["title"] and seals.UNKNOWN_RATE in rows[0]["title"]
    clock.t = (CONVERT + dt.timedelta(hours=1)).timestamp()
    assert s.digest_rows() == []


def test_digest_shows_golden_row_before_the_conversion_maintenance(tmp_path):
    clock = Clock(dt.datetime(2026, 12, 2, 12, 0, tzinfo=UTC).timestamp())
    s = svc(tmp_path, clock=clock)
    s.set_count({"category": "golden", "count": 5})
    d = maintdigest.DigestService(Store(tmp_path / "d"), loss_rows=lambda: [],
                                  items=s.digest_rows, hot=lambda: [],
                                  maint_inputs=lambda: {"slot": maint.DEFAULT, "notices": {}},
                                  clock=clock)
    v = d.view()
    assert v["show"] is True
    assert [r["kind"] for r in v["ending"]] == ["seal"]
    clock.t = dt.datetime(2026, 11, 25, 12, 0, tzinfo=UTC).timestamp()  # the week before
    assert d.view()["ending"] == []


# --- imperial wiring ---------------------------------------------------------------------

def _imp(tmp_path, s):
    doc = json.loads(imperial.DATA_PATH.read_text(encoding="ascii"))
    p = tmp_path / "imperial_boxes.json"
    p.write_text(json.dumps(doc), encoding="ascii")
    return imperial.ImperialService(Store(tmp_path / "istore"), clock=Clock(), data_path=p,
                                    seals=s)


def test_imperial_view_carries_seals_and_delegates_writes(tmp_path):
    s = svc(tmp_path, exchange=[ROW])
    imp = _imp(tmp_path, s)
    v = imp.view()
    assert v["seals"]["categories"][0]["id"] == "cooking"
    v = imp.seal_count({"category": "fishing", "count": 9})
    assert v["seals"]["counts"]["fishing"] == 9 and "types" in v
    v = imp.seal_ex_add({"category": "fishing", "item": "Rod", "cost": 5})
    assert v["seals"]["nearest"]["fishing"]["ready"] == "fishing-rod"
    v = imp.seal_ex_del("fishing-rod")
    assert all(r["id"] != "fishing-rod" for r in v["seals"]["exchange"])
    assert imperial.ImperialService(Store(tmp_path / "x"), clock=Clock()).view()["seals"] is None


class _FakeHandler:
    def __init__(self, imp):
        self.server = type("S", (), {"imperial": imp})()


def test_post_imperial_routes_seal_ops(tmp_path):
    imp = _imp(tmp_path, svc(tmp_path))
    h = _FakeHandler(imp)
    v = ewapp.Handler._post_imperial(h, {"seal_count": {"category": "training", "count": 3}})
    assert v["seals"]["counts"]["training"] == 3
    with pytest.raises(ValueError):
        ewapp.Handler._post_imperial(h, {"seal_bogus": 1})
