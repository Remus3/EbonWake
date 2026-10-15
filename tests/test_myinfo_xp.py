"""Plan 132: My Info (P) exact XP OCR - absolute XP samples for the leveling
rate fit.

The parser runs over fixture {text, lines} docs; AutoOcr runs over a fake
ScreenShot folder with an injected OCR runner. Nothing reads the game.
"""

import datetime as dt

import pytest

from server.ew import knownissues, leveling, ocr, ocrauto, ocrinfer, xpbooks
from server.ew import grind as grindmod
from server.ew.store import Store

T0 = 1_800_000_000.0
UTC = dt.timezone.utc
TOTAL = 5_000_000_000


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, UTC).replace(microsecond=0).isoformat()


def _doc(*texts):
    lines = [{"text": t, "x": 0, "y": 20 * i, "w": 100, "h": 10} for i, t in enumerate(texts)]
    return {"text": "\n".join(texts), "lines": lines}


def _myinfo(cur="1,234,567,890", nxt="3,765,432,110", mx="5,000,000,000", pct="24.691%",
            level="Lv. 66"):
    rows = ["My Information", level, f"Current EXP {cur}"]
    if nxt is not None:
        rows.append(f"EXP to Next Level {nxt}")
    if mx is not None:
        rows.append(f"Max EXP {mx}")
    if pct is not None:
        rows.append(pct)
    return _doc(*rows)


# -- slice 1: the parser -------------------------------------------------------------

def test_clean_read_is_exact_and_sum_verified():
    f = ocrinfer.myinfo_xp_field(_myinfo())
    assert f["kind"] == "myinfo_xp" and f["name"] == "myinfo_xp"
    assert f["value"] == {"level": 66, "xp": 1_234_567_890, "to_next": 3_765_432_110,
                          "pct": 24.691}
    assert f["conf"] >= ocrauto.AUTO_APPLY_MIN
    assert "mismatch" not in f


def test_commas_dropped_still_verified_by_the_sum():
    f = ocrinfer.myinfo_xp_field(_myinfo(cur="1234567890", nxt="3765432110", mx="5000000000"))
    assert f["value"]["xp"] == 1_234_567_890 and f["value"]["to_next"] == 3_765_432_110
    assert f["conf"] >= ocrauto.AUTO_APPLY_MIN


def test_commas_dropped_without_max_is_below_the_auto_gate():
    f = ocrinfer.myinfo_xp_field(_myinfo(cur="1234567890", nxt="3765432110", mx=None))
    assert f["value"]["xp"] == 1_234_567_890
    assert f["conf"] < ocrauto.AUTO_APPLY_MIN
    assert "dropped" in f["why"]


def test_cut_digit_group_breaks_the_sum():
    # plan 016 hazard: a comma read as a space cuts the last group off
    f = ocrinfer.myinfo_xp_field(_myinfo(cur="1,234,567 890"))
    assert f["value"]["xp"] == 1_234_567
    assert f["conf"] < 0.9 and "max" in f["why"]


def test_broken_groups_are_low_conf():
    f = ocrinfer.myinfo_xp_field(_myinfo(cur="1,234567,890", mx=None, pct=None))
    assert f["conf"] < 0.9 and "group" in f["why"]


def test_to_next_derived_from_max():
    f = ocrinfer.myinfo_xp_field(_myinfo(nxt=None))
    assert f["value"]["to_next"] == 3_765_432_110


def test_pct_derived_when_not_shown():
    f = ocrinfer.myinfo_xp_field(_myinfo(pct=None))
    assert f["value"]["pct"] == 24.691 and "mismatch" not in f


def test_pct_mismatch_is_flagged():
    f = ocrinfer.myinfo_xp_field(_myinfo(pct="30.000%"))
    assert f["mismatch"] is True and "mismatch" in f["why"]


def test_no_level_or_no_xp_no_field():
    assert ocrinfer.myinfo_xp_field(_myinfo(level="My Info")) is None
    assert ocrinfer.myinfo_xp_field(_doc("Lv. 66", "24.691%")) is None
    assert ocrinfer.myinfo_xp_field(_doc("Lv 61 12.500%")) is None


def test_xp_above_total_no_field():
    assert ocrinfer.myinfo_xp_field(_myinfo(cur="6,000,000,000", nxt=None, pct=None)) is None


# -- slice 2/3: leveling rate fit ---------------------------------------------------

class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


def _lev(tmp_path, issues=(), t=T0 + 7200):
    store = Store(tmp_path / "store")
    return leveling.LevelingService(store, clock=Clock(t), epochs=[], deadlines=[],
                                    issues=list(issues))


def _pct(xp, total=TOTAL):
    return round(100 * xp / total, 3)


def test_absolute_rate_and_eta(tmp_path):
    lev = _lev(tmp_path)
    lev.ocr_sample(66, _pct(1_000_000_000), T0, xp=1_000_000_000, to_next=4_000_000_000)
    lev.ocr_sample(66, _pct(1_500_000_000), T0 + 3600, xp=1_500_000_000,
                   to_next=3_500_000_000)
    v = lev.view()
    assert v["rate_xp_h"] == 500_000_000
    assert v["rate_source"] == "xp"
    assert v["rate_pct_h"] == pytest.approx(10.0)
    assert v["xp"] == 1_500_000_000 and v["to_next"] == 3_500_000_000
    assert v["eta_next_s"] == 7 * 3600


def test_exact_pct_beats_the_rounded_pct(tmp_path):
    # two reads 0.0004 % apart: both round to 20.0, the absolute delta is real
    lev = _lev(tmp_path)
    lev.ocr_sample(66, 20.0, T0, xp=1_000_000_000, to_next=4_000_000_000)
    lev.ocr_sample(66, 20.0, T0 + 3600, xp=1_000_020_000, to_next=3_999_980_000)
    assert lev.view()["rate_xp_h"] == 20_000
    assert leveling.rate_pct_h(lev.samples()) == pytest.approx(0.0004, abs=1e-6)


def test_level_up_inside_a_window_is_summed(tmp_path):
    lev = _lev(tmp_path)
    lev.ocr_sample(66, 90.0, T0, xp=4_500_000_000, to_next=500_000_000)
    lev.ocr_sample(67, _pct(500_000_000, 7_000_000_000), T0 + 3600, xp=500_000_000,
                   to_next=6_500_000_000)
    assert lev.view()["rate_xp_h"] == 1_000_000_000


def test_two_level_jump_needs_the_middle_total(tmp_path):
    lev = _lev(tmp_path)
    lev.ocr_sample(66, 90.0, T0, xp=4_500_000_000, to_next=500_000_000)
    lev.ocr_sample(68, 1.0, T0 + 3600, xp=80_000_000, to_next=7_920_000_000)
    assert lev.view()["rate_xp_h"] is None  # Lv 67 total never observed
    assert lev.view()["rate_source"] == "pct"


def test_two_level_jump_with_an_observed_middle_total():
    a = {"level": 66, "xp": 4_500_000_000, "to_next": 500_000_000}
    b = {"level": 68, "xp": 80_000_000, "to_next": 7_920_000_000}
    assert leveling.xp_gain(a, b, {}) is None
    assert leveling.xp_gain(a, b, {67: 7_000_000_000}) == 500_000_000 + 7_000_000_000 + 80_000_000
    assert leveling.xp_gain(b, a, {67: 7_000_000_000}) is None  # backwards
    assert leveling.xp_gain(a, {"level": 66, "xp": 4_600_000_000, "to_next": 400_000_000},
                            {}) == 100_000_000
    assert leveling.xp_gain(a, {"level": 66, "pct": 95.0}, {}) is None  # no absolute read


def test_level_xp_table_grows_from_reads_and_undo_removes_it(tmp_path):
    lev = _lev(tmp_path)
    ts = lev.ocr_sample(66, 20.0, T0, xp=1_000_000_000, to_next=4_000_000_000)
    rows = lev.view()["level_xp"]
    assert rows == [{"level": 66, "total": TOTAL, "ts": ts, "source": "operator shot"}]
    lev.ocr_sample_del(ts)
    assert lev.view()["level_xp"] == []


def test_fallback_to_percent(tmp_path):
    lev = _lev(tmp_path)
    lev.ocr_sample(61, 10.0, T0)
    lev.ocr_sample(61, 12.0, T0 + 3600)
    v = lev.view()
    assert v["rate_xp_h"] is None and v["rate_source"] == "pct"
    assert v["rate_pct_h"] == pytest.approx(2.0)
    assert v["xp"] is None and v["to_next"] is None
    assert v["eta_next_s"] == 44 * 3600


def test_newest_sample_pct_only_keeps_pct_eta(tmp_path):
    lev = _lev(tmp_path)
    lev.ocr_sample(66, 20.0, T0, xp=1_000_000_000, to_next=4_000_000_000)
    lev.ocr_sample(66, 30.0, T0 + 3600, xp=1_500_000_000, to_next=3_500_000_000)
    lev.ocr_sample(66, 40.0, T0 + 7200)
    v = lev.view()
    assert v["xp"] is None and v["to_next"] is None
    assert v["eta_next_s"] == leveling.eta_next_s(40.0, v["rate_pct_h"])


def test_suspect_window_excludes_absolute_samples(tmp_path):
    row = knownissues.validate({
        "id": "lv66-stall", "title": "Lv 66 XP shortfall", "affects": ["leveling"],
        "from": _iso(T0 - 60), "until": _iso(T0 + 86400), "source": "official notice",
        "verified": True})
    lev = _lev(tmp_path, issues=[row])
    lev.ocr_sample(66, 20.0, T0, xp=1_000_000_000, to_next=4_000_000_000)
    lev.ocr_sample(66, 30.0, T0 + 3600, xp=1_500_000_000, to_next=3_500_000_000)
    v = lev.view()
    assert v["rate_xp_h"] is None and v["rate_pct_h"] is None
    assert all(s["suspect"] == "lv66-stall" for s in v["samples"])


def test_sample_keeps_xp_through_a_reload(tmp_path):
    lev = _lev(tmp_path)
    lev.ocr_sample(66, 20.0, T0, xp=1_000_000_000, to_next=4_000_000_000)
    s = lev.samples()[0]
    assert s["xp"] == 1_000_000_000 and s["to_next"] == 4_000_000_000
    assert s["source"] == "ocr"


def test_bad_xp_rejected(tmp_path):
    lev = _lev(tmp_path)
    for xp, nxt in ((-1, 5), (5, -1), (0, 0), (True, 5), (1.5, 5), (5, None)):
        with pytest.raises(ValueError):
            lev.ocr_sample(66, 20.0, T0, xp=xp, to_next=nxt)


# -- slice 1/2: the auto-OCR worker -------------------------------------------------

class FakeGame:
    def __init__(self, shot_dir):
        self.shot_dir = shot_dir
        self.shots = []

    def add(self, name, ts, size=10):
        (self.shot_dir / name).write_bytes(b"x" * size)
        self.shots.insert(0, {"name": name, "size": size, "mtime": _iso(ts)})

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
    g = grindmod.GrindService(store, clock=clock, presets=[])
    books = xpbooks.XpBooksService(store, clock=clock)
    lev = leveling.LevelingService(store, clock=clock, epochs=[], deadlines=[], books=books,
                                   issues=[])
    reader = ocr.OcrService(game, tmp_path / "ocr", runner=lambda p: docs[p.name])
    auto = ocrauto.AutoOcr(store, game, reader, g, settings=lambda: {}, clock=clock,
                           leveling=lev)
    auto.on_game(None, "logged_in", T0 - 7200)

    class Env:
        pass

    e = Env()
    e.__dict__.update(game=game, docs=docs, clock=clock, store=store, lev=lev, auto=auto)
    return e


def _shot(e, name, ts, doc):
    e.game.add(name, ts)
    e.docs[name] = doc
    e.clock.t = ts + 60
    e.auto.scan()
    e.auto.drain()


def _review(e):
    # the stored items: the view does not list `hold`
    return [r for r in e.store.get("ocr_review").get("items", [])
            if r["kind"] in ("myinfo_xp", "level")]


def test_kind_is_registered():
    assert "myinfo_xp" in ocrauto.KINDS
    assert "myinfo_xp" not in ocrauto.FIX_KINDS  # accept / discard only


def test_clean_shot_commits_an_absolute_sample_and_logs_it(env):
    _shot(env, "a.jpg", T0, _myinfo())
    s = env.lev.samples()
    assert len(s) == 1  # the level read of the same shot is not a second sample
    assert s[0]["xp"] == 1_234_567_890 and s[0]["to_next"] == 3_765_432_110
    assert s[0]["pct"] == 24.691 and s[0]["source"] == "ocr"
    applied = [a for a in env.auto.view()["applied"] if a["kind"] == "myinfo_xp"]
    assert len(applied) == 1 and applied[0]["value"]["xp"] == 1_234_567_890
    assert _review(env) == []


def test_commas_dropped_with_max_commits(env):
    _shot(env, "a.jpg", T0, _myinfo(cur="1234567890", nxt="3765432110", mx="5000000000"))
    assert env.lev.samples()[0]["xp"] == 1_234_567_890


def test_low_conf_read_is_queued_and_accept_commits(env):
    _shot(env, "a.jpg", T0, _myinfo(cur="1234567890", nxt="3765432110", mx=None))
    assert env.lev.samples() == []
    (item,) = _review(env)
    assert item["kind"] == "myinfo_xp"
    with pytest.raises(ValueError):
        env.auto.review({"id": item["id"], "action": "fix", "value": 1})
    env.auto.review({"id": item["id"], "action": "accept"})
    assert env.lev.samples()[0]["xp"] == 1_234_567_890


def test_mismatch_read_is_held(env):
    _shot(env, "a.jpg", T0, _myinfo(pct="30.000%"))
    assert env.lev.samples() == []
    (item,) = _review(env)
    assert item["hold"] == "mismatch" and "mismatch" in item["why"]


def test_xp_going_back_is_held(env):
    _shot(env, "a.jpg", T0, _myinfo())
    _shot(env, "b.jpg", T0 + 600, _myinfo(cur="1,000,000,000", nxt="4,000,000,000",
                                          pct="20.000%"))
    assert len(env.lev.samples()) == 1
    (item,) = _review(env)
    assert item["hold"] == "back"


def test_undo_removes_the_sample_and_its_level_row(env):
    _shot(env, "a.jpg", T0, _myinfo())
    (row,) = [a for a in env.auto.view()["applied"] if a["kind"] == "myinfo_xp"]
    env.auto.undo_applied(row["id"])
    assert env.lev.samples() == []
    assert env.lev.view()["level_xp"] == []


def test_two_shots_give_an_absolute_rate(env):
    _shot(env, "a.jpg", T0, _myinfo(cur="1,000,000,000", nxt="4,000,000,000",
                                    pct="20.000%"))
    _shot(env, "b.jpg", T0 + 3600, _myinfo(cur="1,500,000,000", nxt="3,500,000,000",
                                           pct="30.000%"))
    v = env.lev.view()
    assert v["rate_xp_h"] == 500_000_000 and v["rate_source"] == "xp"
