"""Plan 112: grind silver auto. The OCR silver samples (plan 063, store domain
`silver`) taken across a plan 062 play window fill the auto grind session's
silver on close; a late screenshot fills a still-0 auto session once; a typed
silver edit beats the derived value. Samples are seeded by hand; nothing reads
the game."""

import datetime as dt

import pytest

from server.ew import app as ewapp
from server.ew import grind, ocrinfer, playsession, summary
from server.ew.store import Store

UTC = dt.timezone.utc
T10 = dt.datetime(2026, 10, 5, 10, 0, 0, tzinfo=UTC).timestamp()
MIN = 60.0
M = 1_000_000


def iso(ts):
    return dt.datetime.fromtimestamp(ts, UTC).isoformat()


def sample(ts, value, n=[0]):
    n[0] += 1
    return {"id": f"u{n[0]}", "at": iso(ts), "value": value, "source": f"ocr:shot{n[0]}.jpg"}


WIN = {"id": "p1", "start": iso(T10), "end": iso(T10 + 90 * MIN)}


# --- slice 1: pure silver_delta ------------------------------------------------------

def test_baseline_before_start_and_last_inside():
    s = [sample(T10 - 30 * MIN, 100 * M), sample(T10 + 40 * MIN, 150 * M),
         sample(T10 + 80 * MIN, 190 * M)]
    d = ocrinfer.silver_delta(s, WIN)
    assert d == {"silver": 90 * M, "first": iso(T10 - 30 * MIN), "last": iso(T10 + 80 * MIN),
                 "n": 3, "conf": 1.0, "why": None}


def test_baseline_is_the_last_sample_before_start():
    s = [sample(T10 - 60 * MIN, 50 * M), sample(T10 - 10 * MIN, 100 * M),
         sample(T10 + 60 * MIN, 130 * M)]
    d = ocrinfer.silver_delta(s, WIN)
    assert d["silver"] == 30 * M and d["first"] == iso(T10 - 10 * MIN) and d["n"] == 2


def test_baseline_too_old_falls_back_to_first_inside():
    s = [sample(T10 - ocrinfer.BASELINE_MAX_S - 60, 10 * M), sample(T10 + 5 * MIN, 100 * M),
         sample(T10 + 85 * MIN, 160 * M)]
    d = ocrinfer.silver_delta(s, WIN)
    assert d["silver"] == 60 * M and d["first"] == iso(T10 + 5 * MIN) and d["n"] == 2


def test_no_baseline_two_inside():
    s = [sample(T10 + 1 * MIN, 100 * M), sample(T10 + 89 * MIN, 125 * M)]
    assert ocrinfer.silver_delta(s, WIN)["silver"] == 25 * M


def test_one_point_is_none():
    assert ocrinfer.silver_delta([sample(T10 + 10 * MIN, 1 * M)], WIN) is None
    assert ocrinfer.silver_delta([], WIN) is None
    assert ocrinfer.silver_delta(None, WIN) is None
    assert ocrinfer.silver_delta([sample(T10, 1)], None) is None


def test_negative_delta_is_none_with_why():
    why = []
    s = [sample(T10 + 1 * MIN, 100 * M), sample(T10 + 80 * MIN, 60 * M)]
    assert ocrinfer.silver_delta(s, WIN, why=why) is None
    assert why and "fell" in why[0]


def test_end_takes_a_sample_shortly_after_logout_only():
    s = [sample(T10 + 1 * MIN, 100 * M), sample(T10 + 50 * MIN, 120 * M),
         sample(T10 + 90 * MIN + ocrinfer.AFTER_LOGOUT_S - 1, 140 * M),
         sample(T10 + 90 * MIN + ocrinfer.AFTER_LOGOUT_S + 60, 999 * M)]
    d = ocrinfer.silver_delta(s, WIN)
    assert d["silver"] == 40 * M and d["n"] == 3


def test_non_ocr_and_bad_samples_ignored():
    s = [sample(T10 + 1 * MIN, 100 * M), {"at": iso(T10 + 2 * MIN), "value": 5, "source": "typed"},
         {"at": "junk", "value": 1, "source": "ocr:x"}, {"at": iso(T10 + 3 * MIN), "value": "1",
                                                          "source": "ocr:x"},
         sample(T10 + 70 * MIN, 101 * M)]
    d = ocrinfer.silver_delta(s, WIN)
    assert d["silver"] == 1 * M and d["n"] == 2


def test_open_window_has_no_upper_bound():
    s = [sample(T10 + 1 * MIN, 100 * M), sample(T10 + 500 * MIN, 300 * M)]
    d = ocrinfer.silver_delta(s, dict(WIN, end=None))
    assert d["silver"] == 200 * M


# --- slice 4: spending guard ---------------------------------------------------------

def test_dip_mid_session_sums_positive_steps_with_lowered_conf():
    s = [sample(T10 - 5 * MIN, 100 * M), sample(T10 + 30 * MIN, 140 * M),
         sample(T10 + 31 * MIN, 90 * M),  # repaired / bought: -50m
         sample(T10 + 85 * MIN, 120 * M)]
    d = ocrinfer.silver_delta(s, WIN)
    assert d["silver"] == 70 * M  # +40m then +30m, the spend not counted
    assert d["conf"] < 1 and "dropped" in d["why"]


def test_dip_within_tolerance_is_ocr_noise():
    s = [sample(T10 + 1 * MIN, 1000 * M), sample(T10 + 30 * MIN, 1000 * M - 1000),
         sample(T10 + 80 * MIN, 1100 * M)]
    d = ocrinfer.silver_delta(s, WIN)
    assert d["silver"] == 100 * M and d["conf"] == 1.0 and d["why"] is None


def test_spend_net_negative_but_with_gains_counts_the_gains():
    s = [sample(T10 + 1 * MIN, 100 * M), sample(T10 + 40 * MIN, 130 * M),
         sample(T10 + 41 * MIN, 50 * M), sample(T10 + 80 * MIN, 60 * M)]
    d = ocrinfer.silver_delta(s, WIN)
    assert d["silver"] == 40 * M and d["conf"] < 1


# --- slices 2 + 3: grind fill on close, late fill once, typed beats derived -----------

class Clock:
    def __init__(self, t=T10):
        self.t = t

    def __call__(self):
        return self.t


class Rig:
    def __init__(self, tmp_path):
        self.clock = Clock()
        self.store = Store(tmp_path / "store")
        self.gs = grind.GrindService(self.store, clock=self.clock)
        self.gs.add_spot("Orc Camp")
        self.ss = summary.SummaryService(self.store, self.gs, clock=self.clock)
        self.ps = playsession.PlaySession(self.store, self.gs, self.ss,
                                          config=lambda: (True, 120), clock=self.clock)
        self.state = None

    def go(self, new, at):
        self.clock.t = at
        prev, self.state = self.state, new
        self.ss.on_game(prev, new, at)
        self.ps.on_game(prev, new, at)
        self.ps.tick(new, at)

    def tick(self, at):
        self.clock.t = at
        self.ps.tick(self.state, at)

    def seed(self, *samples):
        doc = self.store.get("silver")
        old = doc.get("samples") if isinstance(doc.get("samples"), list) else []
        self.store.put("silver", {"samples": old + list(samples)})

    def play(self, minutes=90):
        self.go("not_running", T10 - 5 * MIN)
        self.go("logged_in", T10)
        self.go("not_running", T10 + minutes * MIN)
        self.tick(T10 + (minutes + 3) * MIN)
        return self.gs.view()["sessions"][0]


@pytest.fixture()
def rig(tmp_path):
    return Rig(tmp_path)


def test_acceptance_three_samples_close_to_hand_computed_row(rig):
    rig.seed(sample(T10 - 20 * MIN, 1_000 * M), sample(T10 + 45 * MIN, 1_120 * M),
             sample(T10 + 88 * MIN, 1_210 * M))
    s = rig.play(90)
    assert s["minutes"] == 90 and s["silver"] == 210 * M
    assert s["silver_per_h"] == 140 * M  # 210m * 60 / 90
    assert s["auto"] is True and s["silver_src"] == "ocr_delta"
    assert s["silver_from"] == {"first_at": iso(T10 - 20 * MIN), "last_at": iso(T10 + 88 * MIN),
                                "n": 3, "conf": 1.0}


def test_close_without_samples_logs_zero_and_late_shot_fills_once(rig):
    s = rig.play(90)
    assert s["silver"] == 0 and s["auto"] is True and "silver_src" not in s
    # Late screenshots are read after the close (OCR runs async).
    rig.seed(sample(T10 + 2 * MIN, 500 * M), sample(T10 + 80 * MIN, 530 * M))
    assert rig.gs.refill_silver() == s["id"]
    s = rig.gs.view()["sessions"][0]
    assert s["silver"] == 30 * M and s["silver_src"] == "ocr_delta"
    # Once: a newer sample never re-fills a filled row.
    rig.seed(sample(T10 + 89 * MIN, 900 * M))
    assert rig.gs.refill_silver() is None
    assert rig.gs.auto_fill(s["id"], {"silver": 1, "first": iso(T10), "last": iso(T10),
                                      "n": 2, "conf": 1.0, "why": None}) is False
    assert rig.gs.view()["sessions"][0]["silver"] == 30 * M


def test_typed_edit_beats_derived_and_blocks_late_fill(rig):
    s = rig.play(90)
    rig.gs.edit({"id": s["id"], "silver": 77 * M})
    s = rig.gs.view()["sessions"][0]
    assert s["silver"] == 77 * M and s["silver_src"] == "typed" and "silver_from" not in s
    rig.seed(sample(T10 + 2 * MIN, 500 * M), sample(T10 + 80 * MIN, 530 * M))
    assert rig.gs.refill_silver() is None
    assert rig.gs.view()["sessions"][0]["silver"] == 77 * M
    # A typed 0 is still typed: a late shot never fills it.
    rig.gs.edit({"id": s["id"], "silver": 0})
    assert rig.gs.refill_silver() is None


def test_typed_edit_replaces_an_ocr_delta(rig):
    rig.seed(sample(T10 + 1 * MIN, 100 * M), sample(T10 + 80 * MIN, 150 * M))
    s = rig.play(90)
    assert s["silver_src"] == "ocr_delta"
    out = rig.gs.edit({"id": s["id"], "silver": 45 * M})
    s = out["sessions"][0]
    assert s["silver"] == 45 * M and s["silver_src"] == "typed" and "silver_from" not in s


def test_edit_validates(rig):
    s = rig.play(90)
    for bad in ({"id": s["id"]}, {"id": "s999", "silver": 1}, {"id": s["id"], "silver": -1},
                {"id": s["id"], "silver": True}, {"id": "x", "silver": 1}, "s1",
                {"id": s["id"], "silver": 1, "trash": 2}):
        with pytest.raises(ValueError):
            rig.gs.edit(bad)


def test_manual_sessions_untouched(rig):
    rig.gs.start("orc-camp")
    rig.seed(sample(T10 + 1 * MIN, 100 * M), sample(T10 + 50 * MIN, 150 * M))
    rig.clock.t = T10 + 60 * MIN
    rig.gs.stop({"silver": 0, "trash": 0})
    s = rig.gs.view()["sessions"][0]
    assert s["silver"] == 0 and "auto" not in s and "silver_src" not in s
    assert rig.gs.refill_silver() is None
    assert rig.gs.auto_fill(s["id"], {"silver": 5, "first": iso(T10), "last": iso(T10),
                                      "n": 2, "conf": 1.0, "why": None}) is False
    rig.gs.log({"spot": "orc-camp", "minutes": 30, "silver": 0, "trash": 0})
    assert rig.gs.refill_silver() is None
    assert all(x["silver"] == 0 for x in rig.gs.view()["sessions"])


def test_negative_delta_never_logs_a_negative_row(rig):
    rig.seed(sample(T10 + 1 * MIN, 500 * M), sample(T10 + 80 * MIN, 300 * M))
    s = rig.play(90)
    assert s["silver"] == 0 and "silver_src" not in s


def test_refill_skips_the_running_session_and_old_sessions(rig):
    rig.go("logged_in", T10)
    rig.seed(sample(T10 + 1 * MIN, 100 * M), sample(T10 + 30 * MIN, 150 * M))
    rig.clock.t = T10 + 40 * MIN
    assert rig.gs.refill_silver() is None  # still running: filled on close
    assert rig.gs.view()["sessions"] == []


def test_dip_row_carries_lowered_conf(rig):
    rig.seed(sample(T10 + 1 * MIN, 100 * M), sample(T10 + 30 * MIN, 140 * M),
             sample(T10 + 31 * MIN, 90 * M), sample(T10 + 85 * MIN, 120 * M))
    s = rig.play(90)
    assert s["silver"] == 70 * M and s["silver_from"]["conf"] < 1


def test_ocr_commit_notifier_refills_then_bumps(rig):
    """The app's AutoOcr on_change runs the late fill before the domain bumps;
    a failing fill never breaks the notifier."""
    s = rig.play(90)
    rig.seed(sample(T10 + 2 * MIN, 500 * M), sample(T10 + 80 * MIN, 530 * M))

    class Bus:
        bumped = []

        def bump(self, d):
            self.bumped.append(d)

    class Fake:
        grind = rig.gs
        bus = Bus()

    ewapp.EWServer._ocr_auto_changed(Fake())
    assert rig.gs.view()["sessions"][0]["silver"] == 30 * M
    assert "grind" in Fake.bus.bumped

    class Broken:
        def refill_silver(self):
            raise RuntimeError("boom")

    Fake.grind = Broken()
    Fake.bus.bumped.clear()  # plan 150: the bump after a failing fill is asserted
    ewapp.EWServer._ocr_auto_changed(Fake())
    assert "grind" in Fake.bus.bumped
    assert s["id"] == rig.gs.view()["sessions"][0]["id"]


def test_stored_provenance_survives_a_corrupt_doc(rig):
    rig.seed(sample(T10 + 1 * MIN, 100 * M), sample(T10 + 80 * MIN, 150 * M))
    rig.play(90)
    doc = rig.store.get("grind")
    doc["sessions"][0]["silver_from"] = "junk"
    doc["sessions"][0]["silver_src"] = 7
    doc["sessions"][0]["auto"] = "yes"
    rig.store.put("grind", doc)
    s = rig.gs.view()["sessions"][0]
    assert "silver_from" not in s and "silver_src" not in s and "auto" not in s
