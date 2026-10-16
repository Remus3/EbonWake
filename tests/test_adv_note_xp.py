"""Plan 133: Adventurer's Note (F2) exact XP OCR - a second exact-XP window
beside plan 132 My Info (P), with a cross-check between the two.

The parser runs over fixture {text, lines} docs; AutoOcr runs over a fake
ScreenShot folder with an injected OCR runner. Nothing reads the game.
"""

import datetime as dt
from pathlib import Path

import pytest

from server.ew import knownissues, leveling, ocr, ocrauto, ocrinfer, xpbooks
from server.ew import grind as grindmod
from server.ew.store import Store

T0 = 1_800_000_000.0
UTC = dt.timezone.utc


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, UTC).replace(microsecond=0).isoformat()


def _doc(*texts):
    lines = [{"text": t, "x": 0, "y": 20 * i, "w": 100, "h": 10} for i, t in enumerate(texts)]
    return {"text": "\n".join(texts), "lines": lines}


def _f2(cur="1,234,567,890", nxt="3,765,432,110", mx="5,000,000,000", pct="24.691%",
        level="Lv. 66", title="Adventurer's Note"):
    rows = [title, level, f"Current EXP {cur}"]
    if nxt is not None:
        rows.append(f"EXP to Next Level {nxt}")
    if mx is not None:
        rows.append(f"Max EXP {mx}")
    if pct is not None:
        rows.append(pct)
    return _doc(*rows)


def _myinfo(cur="1,234,567,890", nxt="3,765,432,110", mx="5,000,000,000", pct="24.691%"):
    return _f2(cur=cur, nxt=nxt, mx=mx, pct=pct, title="My Information")


# -- slice 1: the parser -------------------------------------------------------------

def test_clean_f2_read_is_exact_and_sum_verified():
    f = ocrinfer.adv_note_xp_field(_f2())
    assert f["kind"] == "adv_note_xp" and f["name"] == "adv_note_xp"
    assert f["value"] == {"level": 66, "xp": 1_234_567_890, "to_next": 3_765_432_110,
                          "pct": 24.691}
    assert f["conf"] >= ocrauto.AUTO_APPLY_MIN


@pytest.mark.parametrize("title", ["Adventurer's Note", "ADVENTURERS NOTE",
                                   "Adventurer s Note (F2)"])
def test_title_variants(title):
    assert ocrinfer.adv_note_xp_field(_f2(title=title)) is not None


def test_commas_dropped_still_verified_by_the_sum():
    f = ocrinfer.adv_note_xp_field(_f2(cur="1234567890", nxt="3765432110", mx="5000000000"))
    assert f["value"]["xp"] == 1_234_567_890 and f["value"]["to_next"] == 3_765_432_110
    assert f["conf"] >= ocrauto.AUTO_APPLY_MIN


def test_commas_dropped_without_max_is_below_the_auto_gate():
    f = ocrinfer.adv_note_xp_field(_f2(cur="1234567890", nxt="3765432110", mx=None))
    assert f["conf"] < ocrauto.AUTO_APPLY_MIN and "dropped" in f["why"]


def test_cut_digit_group_breaks_the_sum():
    f = ocrinfer.adv_note_xp_field(_f2(cur="1,234,567 890"))
    assert f["conf"] < 0.9 and "max" in f["why"]


def test_pct_mismatch_is_flagged():
    f = ocrinfer.adv_note_xp_field(_f2(pct="30.000%"))
    assert f["mismatch"] is True


def test_no_title_no_f2_field_and_myinfo_unchanged():
    assert ocrinfer.adv_note_xp_field(_myinfo()) is None
    assert ocrinfer.myinfo_xp_field(_myinfo())["kind"] == "myinfo_xp"
    assert ocrinfer.adv_note_xp_field(_doc("Adventurer's Note", "Lv. 66")) is None


# -- slice 2: cross-check (pure) ---------------------------------------------------

def _s(ts, xp, to_next, src=None, level=66, **kw):
    s = {"ts": _iso(ts), "level": level, "pct": 1.0, "source": "ocr", "xp": xp,
         "to_next": to_next, **kw}
    if src is not None:
        s["xp_src"] = src
    return s


V = {"level": 66, "xp": 1_000_000_000, "to_next": 4_000_000_000, "pct": 20.0}


def test_cross_agreement_within_tolerance():
    # 0.01 % of 5e9 = 500,000: a total 400,000 off agrees
    assert ocrinfer.xp_cross([_s(T0, 1_000_000_000, 4_000_400_000)], "adv_note_xp", V,
                             T0 + 60) is None


def test_cross_disagreement_found():
    other = _s(T0, 1_000_000_000, 4_100_000_000)
    assert ocrinfer.xp_cross([other], "adv_note_xp", V, T0 + 60) is other
    tagged = _s(T0, 1_000_000_000, 4_100_000_000, src="f2")
    assert ocrinfer.xp_cross([tagged], "myinfo_xp", V, T0 + 60) is tagged


def test_cross_ignores_same_kind_far_reads_other_levels_and_superseded():
    bad = 4_100_000_000
    assert ocrinfer.xp_cross([_s(T0, 1, bad, src="f2")], "adv_note_xp", V, T0) is None
    assert ocrinfer.xp_cross([_s(T0, 1, bad)], "myinfo_xp", V, T0) is None  # untagged = myinfo
    assert ocrinfer.xp_cross([_s(T0, 1, bad)], "adv_note_xp", V, T0 + 601) is None
    assert ocrinfer.xp_cross([_s(T0, 1, bad, level=65)], "adv_note_xp", V, T0) is None
    assert ocrinfer.xp_cross([_s(T0, 1, bad, superseded=True)], "adv_note_xp", V, T0) is None
    assert ocrinfer.xp_cross([{"ts": _iso(T0), "level": 66, "pct": 1.0, "source": "ocr"}],
                             "adv_note_xp", V, T0) is None


def test_cross_window_edge_is_inclusive():
    other = _s(T0, 1, 4_100_000_000)
    assert ocrinfer.xp_cross([other], "adv_note_xp", V, T0 + 600) is other


# -- leveling source tag ---------------------------------------------------------------

def test_sample_keeps_its_source_tag(tmp_path):
    lev = leveling.LevelingService(Store(tmp_path / "s"), clock=lambda: T0, epochs=[],
                                   deadlines=[], issues=[])
    lev.ocr_sample(66, 20.0, T0, xp=1_000_000_000, to_next=4_000_000_000, xp_src="f2")
    assert lev.samples()[0]["xp_src"] == "f2"
    for bad in ("p", 1):
        with pytest.raises(ValueError):
            lev.ocr_sample(66, 20.0, T0, xp=1, to_next=4, xp_src=bad)
    with pytest.raises(ValueError):
        lev.ocr_sample(66, 20.0, T0, xp_src="f2")  # a tag needs an exact read


# -- slice 2: the auto-OCR worker ---------------------------------------------------

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
    return [r for r in e.store.get("ocr_review").get("items", [])
            if r["kind"] in ("myinfo_xp", "adv_note_xp", "level")]


def _counted(e):
    return [s for s in e.lev.samples() if not s.get("superseded")]


def test_kind_is_registered():
    assert "adv_note_xp" in ocrauto.KINDS
    assert "adv_note_xp" not in ocrauto.FIX_KINDS


def test_f2_shot_commits_a_tagged_sample_and_logs_it(env):
    _shot(env, "a.jpg", T0, _f2())
    (s,) = env.lev.samples()
    assert s["xp"] == 1_234_567_890 and s["xp_src"] == "f2"
    applied = [a for a in env.auto.view()["applied"] if a["kind"] == "adv_note_xp"]
    assert len(applied) == 1
    assert env.auto.xp_advisories() == []


def test_myinfo_shot_is_tagged_myinfo(env):
    _shot(env, "a.jpg", T0, _myinfo())
    assert env.lev.samples()[0]["xp_src"] == "myinfo"


def test_mismatch_f2_read_is_held(env):
    _shot(env, "a.jpg", T0, _f2(pct="30.000%"))
    assert env.lev.samples() == []
    assert _review(env)[0]["hold"] == "mismatch"


def test_agreeing_reads_both_count(env):
    _shot(env, "a.jpg", T0, _myinfo(cur="1,000,000,000", nxt="4,000,000,000", pct="20.000%"))
    _shot(env, "b.jpg", T0 + 300, _f2(cur="1,050,000,000", nxt="3,950,000,000",
                                      pct="21.000%"))
    assert [s["xp_src"] for s in _counted(env)] == ["myinfo", "f2"]
    assert _review(env) == [] and env.auto.xp_advisories() == []


def _disagree(env):
    _shot(env, "a.jpg", T0, _myinfo(cur="1,000,000,000", nxt="4,000,000,000", pct="20.000%"))
    _shot(env, "b.jpg", T0 + 300, _f2(cur="1,050,000,000", nxt="4,050,000,000", mx=None,
                                      pct=None))


def test_disagreement_holds_both_and_raises_an_advisory(env):
    _disagree(env)
    assert _counted(env) == []  # the My Info sample is superseded, F2 not committed
    (held,) = env.lev.samples()
    assert held["superseded"] is True and held["xp_src"] == "myinfo"
    (item,) = _review(env)
    assert item["kind"] == "adv_note_xp" and item["hold"] == "disagree"
    assert item["conflict"] == [held["ts"]] and "total" in item["why"]
    (adv,) = env.auto.xp_advisories()
    assert adv["id"] == "ocr-xp-disagree" and adv["affects"] == ["leveling"]
    assert adv["state"] == "active" and adv["exclude_samples"] is False
    knownissues.validate({k: v for k, v in adv.items() if k != "state"})


def test_disagreement_discard_counts_the_other_read_again(env):
    _disagree(env)
    (item,) = _review(env)
    env.auto.review({"id": item["id"], "action": "discard"})
    assert [s["xp_src"] for s in _counted(env)] == ["myinfo"]
    assert env.auto.xp_advisories() == []


def test_disagreement_accept_keeps_the_other_held_and_undo_restores(env):
    _disagree(env)
    (item,) = _review(env)
    env.auto.review({"id": item["id"], "action": "accept"})
    assert [s["xp_src"] for s in _counted(env)] == ["f2"]
    assert env.auto.xp_advisories() == []
    last = env.store.get("ocr_auto")["commits"][-1]
    assert last["kind"] == "adv_note_xp" and last["superseded"] == item["conflict"]
    env.auto.undo(last["id"])
    assert [s["xp_src"] for s in _counted(env)] == ["myinfo"]


def test_myinfo_after_f2_is_cross_checked_too(env):
    _shot(env, "a.jpg", T0, _f2(cur="1,000,000,000", nxt="4,000,000,000", pct="20.000%"))
    _shot(env, "b.jpg", T0 + 300, _myinfo(cur="1,050,000,000", nxt="4,050,000,000", mx=None,
                                          pct=None))
    (item,) = _review(env)
    assert item["kind"] == "myinfo_xp" and item["hold"] == "disagree"


def test_reads_over_ten_minutes_apart_are_not_cross_checked(env):
    _shot(env, "a.jpg", T0, _myinfo(cur="1,000,000,000", nxt="4,000,000,000", pct="20.000%"))
    _shot(env, "b.jpg", T0 + 900, _f2(cur="1,050,000,000", nxt="4,050,000,000",
                                      mx="5,100,000,000", pct=None))
    assert len(_counted(env)) == 2


def test_new_files_are_ascii_lf():
    root = Path(__file__).resolve().parents[1]
    for rel in ("tests/test_adv_note_xp.py", "docs/plans/133-adventurers-note-f2-ocr.md"):
        raw = (root / rel).read_bytes()
        assert b"\r" not in raw
        raw.decode("ascii")
