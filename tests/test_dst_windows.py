"""Plan 176: DST transition windows - boss spawns shift for the days between the
maintenance before a US clock change and the change itself; the daily reset
stays on UTC. Static data plus local time arithmetic; no network."""

import datetime as dt
import json
import socket
from pathlib import Path

import pytest

from server.ew import bosses, signals, today
from server.ew.store import Store

UTC = dt.timezone.utc
REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "server" / "ew" / "data" / "dst_windows.json"


def T(*a):
    return dt.datetime(*a, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("plan 176 must not touch the network")
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


# --- data file ---------------------------------------------------------------

def test_data_file_lists_fall_and_spring_2026():
    doc = json.loads(DATA.read_text(encoding="ascii"))
    rows = doc["windows"]
    for w in rows:
        assert set(w) == {"start_utc", "end_utc", "offset_hours", "source", "verified"}
    fall = [w for w in rows if w["start_utc"].startswith("2026-10-29")]
    assert len(fall) == 1 and fall[0]["offset_hours"] == 1
    assert fall[0]["end_utc"] == "2026-11-01T09:00:00+00:00"  # 02:00 PDT
    assert isinstance(fall[0]["verified"], str)  # the official notice was read
    spring = [w for w in rows if w["start_utc"].startswith("2026-03-05")]
    assert len(spring) == 1 and spring[0]["offset_hours"] == -1
    assert spring[0]["end_utc"] == "2026-03-08T10:00:00+00:00"  # 02:00 PST


def test_load_windows_rejects_bad(tmp_path):
    good = json.loads(DATA.read_text(encoding="ascii"))
    p = tmp_path / "w.json"
    for mut in (lambda d: d["windows"][0].update(offset_hours=2),
                lambda d: d["windows"][0].update(start_utc="2026-10-29T07:00:00"),
                lambda d: d["windows"][0].update(end_utc=d["windows"][0]["start_utc"]),
                lambda d: d["windows"][0].update(source=""),
                lambda d: d["windows"][0].update(extra=1)):
        doc = json.loads(json.dumps(good))
        mut(doc)
        p.write_text(json.dumps(doc))
        with pytest.raises(ValueError):
            bosses.load_windows(p)


# --- windows: listed and derived ---------------------------------------------

def test_derived_windows_follow_the_rule_and_are_marked():
    ws = bosses.dst_windows(T(2026, 12, 1), bosses.load_windows())
    spring27 = [w for w in ws if w["start_utc"].startswith("2027-03")]
    assert len(spring27) == 1
    w = spring27[0]
    assert w["start_utc"] == "2027-03-11T07:00:00+00:00"  # Thursday maintenance
    assert w["end_utc"] == "2027-03-14T10:00:00+00:00"    # 02:00 PST
    assert w["offset_hours"] == -1 and w["derived"] is True and w["verified"] is False
    fall27 = [w for w in ws if w["start_utc"].startswith("2027-10")]
    fall27 = [w for w in ws if w["start_utc"].startswith("2027-11")]
    assert fall27 and fall27[0]["start_utc"] == "2027-11-04T07:00:00+00:00"
    assert fall27[0]["end_utc"] == "2027-11-07T09:00:00+00:00"
    assert fall27[0]["offset_hours"] == 1 and fall27[0]["derived"] is True


def test_listed_window_wins_over_derived():
    ws = bosses.dst_windows(T(2026, 11, 1), bosses.load_windows())
    fall26 = [w for w in ws if w["start_utc"].startswith("2026-10")]
    assert len(fall26) == 1 and fall26[0]["derived"] is False
    assert isinstance(fall26[0]["verified"], str)


# --- next spawns ----------------------------------------------------------------

def test_acceptance_2026_10_30_reads_plus_one_hour():
    # Fri 2026-10-30 02:00 PDT; the table's Fri 10:00 slot spawns at 11:00 PDT.
    out = bosses.next_spawns(T(2026, 10, 30, 9), n=1)
    s = out[0]
    assert s["day"] == "2026-10-30"
    assert s["at_utc"] == "2026-10-30T18:00:00+00:00"
    assert s["at_pt"] == "2026-10-30T11:00:00-07:00"
    assert s["shift_h"] == 1
    assert s["window"]["ends"] == "2026-11-01T09:00:00+00:00"
    assert s["window"]["source"].startswith("https://")
    assert s["window"]["verified"] and s["window"]["derived"] is False


def test_acceptance_2026_11_02_reads_table_time():
    out = bosses.next_spawns(T(2026, 11, 2, 8), n=1)   # Mon 00:00 PST
    s = out[0]
    assert s["at_pt"] == "2026-11-02T00:00:00-08:00" and s["shift_h"] == 0
    assert s["window"] is None


def test_slot_before_the_window_does_not_move():
    out = bosses.next_spawns(T(2026, 10, 28, 12), n=1)   # Wed 05:00 PDT
    assert out[0]["at_pt"] == "2026-10-28T10:00:00-07:00" and out[0]["shift_h"] == 0


def test_last_slot_in_window_moves_first_after_does_not():
    # Sun 2026-11-01 00:00 PT slot: still before 02:00 PDT -> 01:00 PDT.
    out = bosses.next_spawns(T(2026, 11, 1, 6, 30), n=2)   # Sat 23:30 PDT, after 22:15+1h
    assert out[0]["day"] == "2026-11-01" and out[0]["shift_h"] == 1
    assert out[0]["at_utc"] == "2026-11-01T08:00:00+00:00"
    assert out[1]["shift_h"] == 0 and out[1]["at_pt"].endswith("-08:00")


def test_spring_window_moves_minus_one_hour():
    out = bosses.next_spawns(T(2026, 3, 6, 8), n=1)    # Fri 00:00 PST
    s = out[0]
    assert s["shift_h"] == -1
    assert s["at_pt"] == "2026-03-06T09:00:00-08:00"   # table 10:00, one hour earlier
    assert s["window"]["verified"] is False


def test_spawn_order_is_by_shifted_time():
    out = bosses.next_spawns(T(2026, 10, 29, 12), n=10)
    ats = [s["at_utc"] for s in out]
    assert ats == sorted(ats)


def test_explicit_empty_windows_turn_the_shift_off():
    out = bosses.next_spawns(T(2026, 10, 30, 9), n=1, windows=[])
    assert out[0]["at_pt"] == "2026-10-30T10:00:00-07:00" and out[0]["shift_h"] == 0


# --- reset stays on UTC -----------------------------------------------------------

def test_daily_reset_does_not_shift_in_window():
    now = T(2026, 10, 30, 12)
    assert today.next_daily_reset(now) == T(2026, 10, 31)
    assert today.last_daily_reset(now) == T(2026, 10, 30)


# --- service view: banner input ---------------------------------------------------

def test_view_dst_while_window_active(tmp_path):
    svc = bosses.BossService(Store(tmp_path / "store"), clock=lambda: T(2026, 10, 30, 7).timestamp())
    v = svc.view()
    d = v["dst"]
    assert d["shift_h"] == 1 and d["ends_pt"] == "Sun 02:00 PT"
    assert d["end_utc"] == "2026-11-01T09:00:00+00:00"
    assert d["verified"] and d["derived"] is False
    assert v["today"]["slots"][0]["shift_h"] == 1


def test_view_dst_none_outside(tmp_path):
    svc = bosses.BossService(Store(tmp_path / "store"), clock=lambda: T(2026, 11, 10, 7).timestamp())
    assert svc.view()["dst"] is None


def test_view_dst_spring_derived_reads_expected_fields(tmp_path):
    svc = bosses.BossService(Store(tmp_path / "store"), clock=lambda: T(2027, 3, 12, 8).timestamp())
    d = svc.view()["dst"]
    assert d["shift_h"] == -1 and d["derived"] is True and d["verified"] is False
    assert d["ends_pt"] == "Sun 02:00 PT"


# --- digest line (plan 174 row) ---------------------------------------------------

def test_dst_pending_within_seven_days_unverified():
    ws = bosses.dst_windows(T(2027, 3, 5), bosses.load_windows())
    p = bosses.dst_pending(T(2027, 3, 5), ws)
    assert p is not None and p["start_utc"] == "2027-03-11T07:00:00+00:00"
    assert p["shift_h"] == -1 and p["derived"] is True
    assert bosses.dst_pending(T(2027, 2, 20), ws) is None           # > 7 days out
    ws26 = bosses.dst_windows(T(2026, 10, 25), bosses.load_windows())
    assert bosses.dst_pending(T(2026, 10, 25), ws26) is None         # verified window


def test_digest_data_row_carries_dst_line():
    dst = {"start_utc": "2027-03-11T07:00:00+00:00", "end_utc": "2027-03-14T10:00:00+00:00",
           "shift_h": -1, "derived": True, "verified": False}
    out = signals.digest({"data": {"last_notice": {"date": "2027-03-04"}, "confirmed": 1,
                                   "unchecked": 0, "contradicted": [], "dst": dst}},
                         T(2027, 3, 5).timestamp())
    row = next(r for r in out["rows"] if r["id"] == "data")
    assert (row["level"], row["reason"]) == ("warn", "dst_unverified")
    assert "2027-03-11" in row["detail"] and "-1 h" in row["detail"]
    assert row["hint"] and row["hint"] != signals.GENERIC_HINT
    quiet = signals.digest({"data": {"last_notice": {"date": "2027-03-04"}, "confirmed": 1,
                                     "unchecked": 0, "contradicted": [], "dst": None}},
                           T(2027, 3, 5).timestamp())
    assert next(r for r in quiet["rows"] if r["id"] == "data")["level"] == "ok"
