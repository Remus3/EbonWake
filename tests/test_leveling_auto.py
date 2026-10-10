"""Plan 116: leveling runs from automatic samples - onboarding done from any
sample, held level reads resolve on an agreeing second read, a profile marker
starts a rate segment, and level deadlines are derived from official notices.

AutoOcr runs over a fake ScreenShot folder with an injected OCR runner; the
notice tests parse fixture text. Nothing reads the game or the network.
"""

import datetime as dt
import json

import pytest

from server.ew import (eventnotices, leveling, levels, noticedeadlines, ocr, ocrauto, onboarding,
                       xpbooks)
from server.ew import grind as grindmod
from server.ew.store import Store

T0 = 1_800_000_000.0
UTC = dt.timezone.utc
SLOT = {"weekday": "thu", "start_utc": "08:00", "duration_min": 180}


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, UTC).replace(microsecond=0).isoformat()


def _doc(*texts):
    lines = [{"text": t, "x": 0, "y": 20 * i, "w": 100, "h": 10} for i, t in enumerate(texts)]
    return {"text": "\n".join(texts), "lines": lines}


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
    lev = leveling.LevelingService(store, clock=clock, epochs=[], deadlines=[], books=books)
    reader = ocr.OcrService(game, tmp_path / "ocr", runner=lambda p: docs[p.name])
    auto = ocrauto.AutoOcr(store, game, reader, g, settings=lambda: {}, clock=clock,
                           leveling=lev)
    auto.on_game(None, "logged_in", T0 - 7200)

    class Env:
        pass

    e = Env()
    e.__dict__.update(game=game, docs=docs, clock=clock, store=store, lev=lev, auto=auto,
                      tmp=tmp_path)
    return e


def _shot(e, name, ts, text):
    e.game.add(name, ts)
    e.docs[name] = _doc(text)
    e.clock.t = ts + 60
    e.auto.scan()
    e.auto.drain()


def _live(e):
    return [(s["level"], s["pct"]) for s in e.lev.samples()
            if s.get("pct") is not None and not s.get("superseded")]


def _held(e):
    return [r for r in e.auto.view()["review"] if r["kind"] == "level"]


# -- slice 1: onboarding -------------------------------------------------------------

def _step(store, tmp_path):
    st = onboarding.status(tmp_path, store, config_path=tmp_path / "none.json")
    return next(s for s in st["steps"] if s["id"] == "leveling")


def test_onboarding_done_from_an_ocr_only_sample(env):
    step = _step(env.store, env.tmp)
    assert step["done"] is False
    assert "screenshot" in step["hint"].lower() and "type" not in step["hint"].lower()
    _shot(env, "a.jpg", T0, "Lv 61 12.500%")
    assert _step(env.store, env.tmp)["done"] is True


def test_onboarding_done_from_a_profile_marker_only(tmp_path):
    store = Store(tmp_path / "store")
    lev = leveling.LevelingService(store, clock=Clock(), epochs=[], deadlines=[])
    assert lev.profile_marker(60) is True
    assert _step(store, tmp_path)["done"] is True


# -- slice 2: held reads self-resolve ---------------------------------------------------

def _misread_history(e):
    _shot(e, "a.jpg", T0, "Lv 61 20.000%")
    _shot(e, "b.jpg", T0 + 600, "Lv 61 50.000%")   # a misread that extended the history
    _shot(e, "c.jpg", T0 + 1200, "Lv 61 21.000%")  # true, held: "went back"
    assert [h["file"] for h in _held(e)] == ["c.jpg"]


def test_held_read_and_an_agreeing_later_read_both_commit(env):
    _misread_history(env)
    _shot(env, "d.jpg", T0 + 1500, "Lv 61 21.300%")
    assert _live(env) == [(61, 20), (61, 21), (61, 21.3)]
    b = next(s for s in env.lev.samples() if s["ts"] == _iso(T0 + 600))
    assert b["superseded"] is True and b["pct"] == 50  # marked, not deleted
    assert _held(env) == []
    applied = [a for a in env.auto.view()["applied"] if a["kind"] == "level"]
    assert len(applied) == 2
    v = env.lev.view()
    assert (v["level"], v["pct"]) == (61, 21.3)
    assert any(s.get("superseded") for s in v["samples"])


def test_single_held_read_stays_held(env):
    _misread_history(env)
    assert _live(env) == [(61, 20), (61, 50)]
    assert not any(s.get("superseded") for s in env.lev.samples())


@pytest.mark.parametrize("ts,text", [
    (T0 + 1260, "Lv 61 21.100%"),   # under 2 min after c.jpg: not independent
    (T0 + 1800, "Lv 61 22.000%"),   # more than 0.5 % apart: no agreement
])
def test_no_agreement_leaves_both_held(env, ts, text):
    _misread_history(env)
    _shot(env, "d.jpg", ts, text)
    assert _live(env) == [(61, 20), (61, 50)]
    assert sorted(h["file"] for h in _held(env)) == ["c.jpg", "d.jpg"]


def test_level_below_a_wrong_marker_resolves(env):
    _shot(env, "a.jpg", T0, "Lv 61 20.000%")
    env.clock.t = T0 + 300
    env.lev.profile_marker(63)  # a profile cache read wrong
    _shot(env, "c.jpg", T0 + 600, "Lv 61 21.000%")
    _shot(env, "d.jpg", T0 + 900, "Lv 61 21.200%")
    assert _live(env) == [(61, 20), (61, 21), (61, 21.2)]
    assert env.lev.view()["level"] == 61


def test_undo_restores_the_superseded_sample(env):
    _misread_history(env)
    _shot(env, "d.jpg", T0 + 1500, "Lv 61 21.300%")
    row = next(a for a in env.auto.view()["applied"]
               if a["kind"] == "level" and a["file"] == "d.jpg")
    env.auto.undo_applied(row["id"])
    assert (61, 21.3) not in _live(env)
    assert (61, 50) in _live(env)


# -- slice 3: profile anchor ------------------------------------------------------------

def test_profile_marker_starts_a_rate_segment(tmp_path):
    clock = Clock()
    lev = leveling.LevelingService(Store(tmp_path / "store"), clock=clock, epochs=[],
                                   deadlines=[])
    lev.ocr_sample(61, 12.5, T0)
    clock.t = T0 + 86400
    assert lev.profile_marker(62) is True  # a missed screenshot day
    lev.ocr_sample(62, 10, T0 + 86400 + 3600)
    lev.ocr_sample(62, 12, T0 + 86400 + 7200)
    clock.t = T0 + 86400 + 7300
    v = lev.view()
    assert v["rate_pct_h"] == 2.0
    assert v["segment_utc"] == _iso(T0 + 86400)
    assert v["eta_next_s"] == int(88 / 2 * 3600)
    # the same history without the marker blends the missed day into the rate
    other = leveling.LevelingService(Store(tmp_path / "s2"), clock=clock, epochs=[],
                                     deadlines=[])
    for lv, pct, ts in ((61, 12.5, T0), (62, 10, T0 + 90000), (62, 12, T0 + 93600)):
        other.ocr_sample(lv, pct, ts)
    assert other.view()["rate_pct_h"] != 2.0 and other.view()["segment_utc"] is None


def test_marker_below_the_sampled_level_starts_no_segment(tmp_path):
    clock = Clock()
    lev = leveling.LevelingService(Store(tmp_path / "store"), clock=clock, epochs=[],
                                   deadlines=[])
    lev.ocr_sample(62, 10, T0)
    lev.ocr_sample(62, 12, T0 + 3600)
    assert leveling.segment_start(lev.samples() + [
        {"ts": _iso(T0 + 4000), "level": 62, "pct": None, "source": "profile"}]) is None


# -- slice 4: derived deadlines ---------------------------------------------------------

NOTICE_LINES = [
    "Olvia Academy Class 4 opens for new adventurers.",
    "Adventurers must reach Lv. 61 by Nov 26, 2026 (Thu) before maintenance to graduate.",
    "Enrollment for characters Lv. 56 or higher is open until Nov 19, 2026 (Thu) "
    "before maintenance.",
]


def test_notice_text_yields_deadline_lines():
    pats = noticedeadlines.load_patterns()
    out = noticedeadlines.extract(NOTICE_LINES, 2026, 11, pats)
    assert [(d["level"], d["kind"], d["until"]["date"]) for d in out] == [
        (61, "reach", "2026-11-26"), (56, "enrol", "2026-11-19")]
    assert all(d["conf"] >= ocrauto.AUTO_APPLY_MIN for d in out)
    assert all(d["text"].isascii() for d in out)


def test_parse_notice_carries_deadlines_and_bumps_parse_v():
    page = "<div class='contents'>" + "".join(f"<p>{ln}</p>" for ln in NOTICE_LINES) + "</div>"
    n = eventnotices.parse_notice(page, "[Event] Olvia Academy", 2026, 11)
    assert [d["level"] for d in n["deadlines"]] == [61, 56]
    assert n["parse_v"] >= 4
    entry = {"stamp": None, "fetched_at": 1.0, "window": None, "deadlines": n["deadlines"] + [
        "junk", {"text": "x", "level": 99, "kind": "reach", "conf": 1,
                 "until": n["deadlines"][0]["until"]}], "parse_v": 4}
    assert eventnotices._clean_detail(entry)["deadlines"] == n["deadlines"]
    assert eventnotices._clean_detail(dict(entry, deadlines=None))["deadlines"] == []


def _notice_rows(lines=NOTICE_LINES, gno=10700):
    n = {"group_no": gno, "title": "[Event] Olvia Academy Class 4",
         "url": eventnotices.detail_url(gno), "stamp": "2026-11-05", "board": 3}
    d = {"deadlines": noticedeadlines.extract(lines, 2026, 11, noticedeadlines.load_patterns())}
    return eventnotices.NoticeService.deadline_rows([n], {gno: d}, SLOT, {})


def _lev(tmp_path, tracked=(), now=dt.datetime(2026, 11, 6, tzinfo=UTC)):
    return leveling.LevelingService(Store(tmp_path / "store"), clock=Clock(now.timestamp()),
                                    epochs=[], deadlines=list(tracked))


def test_notice_deadline_row_is_added_with_by_notice(tmp_path):
    rows = _notice_rows()
    assert {r["needs_level"] for r in rows} == {61, 56}
    r61 = next(r for r in rows if r["needs_level"] == 61)
    assert r61["enrol_by_utc"] == "2026-11-26T08:00:00+00:00"
    lev = _lev(tmp_path)
    lev.ocr_sample(60, 50, dt.datetime(2026, 11, 5, tzinfo=UTC).timestamp())
    lev.notice_deadlines(rows)
    v = lev.view()
    got = {d["needs_level"]: d for d in v["deadlines"]}
    assert got[61]["by"] == "notice" and got[61]["source"] == eventnotices.detail_url(10700)
    assert got[61]["state"] == "unknown" and got[56]["state"] == "done"
    assert v["deadline_suggestions"] == []
    # undoable: a deleted notice row never comes back on the next sync
    lev.deadline_del(got[61]["id"])
    lev.notice_deadlines(rows)
    assert 61 not in {d["needs_level"] for d in lev.view()["deadlines"]}


def test_low_conf_pattern_is_a_suggestion_only(tmp_path):
    rows = _notice_rows(["Characters at Lv. 58 can join the season; sign up ends "
                         "Nov 20, 2026 (Thu) before maintenance."])
    assert rows and all(r["conf"] < ocrauto.AUTO_APPLY_MIN for r in rows)
    lev = _lev(tmp_path)
    lev.notice_deadlines(rows)
    v = lev.view()
    assert [d["needs_level"] for d in v["deadlines"]] == []
    assert [d["needs_level"] for d in v["deadline_suggestions"]] == [58]
    lev.deadline_accept(v["deadline_suggestions"][0]["id"])
    v = lev.view()
    assert [(d["needs_level"], d["by"]) for d in v["deadlines"]] == [(58, "notice")]
    assert v["deadline_suggestions"] == []


def test_dedupe_against_tracked_rows(tmp_path):
    tracked = levels.validate_deadline({
        "id": "olvia-class-4", "label": "Olvia Academy", "needs_level": 61,
        "enrol_by_utc": "2026-11-26T00:00:00+00:00", "quests_by_utc": None,
        "source": "guide", "verified": False})
    lev = _lev(tmp_path, tracked=[tracked])
    lev.notice_deadlines(_notice_rows())
    rows = lev.view()["deadlines"]
    assert [(d["needs_level"], d["by"]) for d in rows] == [(56, "notice"), (61, "tracked")]


def test_pattern_file_is_tracked_data_verified_false():
    raw = noticedeadlines.PATTERNS_FILE.read_bytes()
    assert raw.isascii() and b"\r" not in raw
    doc = json.loads(raw)
    assert doc["verified"] is False and doc["patterns"]
    assert len(noticedeadlines.load_patterns()) == len(doc["patterns"])


def test_gate_matches_plan_111():
    assert leveling.NOTICE_AUTO_MIN == ocrauto.AUTO_APPLY_MIN


# -- acceptance --------------------------------------------------------------------------

def test_acceptance_three_ocr_reads_one_profile_refresh(env):
    """No typed sample: a rate, an ETA and one derived deadline with its status."""
    _shot(env, "s1.jpg", T0, "Lv 60 80.000%")
    env.clock.t = T0 + 86400
    env.lev.profile_marker(61)
    _shot(env, "s2.jpg", T0 + 86400 + 1800, "Lv 61 5.000%")
    _shot(env, "s3.jpg", T0 + 86400 + 5400, "Lv 61 8.000%")
    now = env.clock.t
    enrol = dt.datetime.fromtimestamp(now + 30 * 86400, UTC).date()
    line = (f"Adventurers must reach Lv. 62 by {enrol.strftime('%b')} {enrol.day}, "
            f"{enrol.year} (Thu) before maintenance.")
    n = {"group_no": 10800, "title": "[Event] Level Up", "url": eventnotices.detail_url(10800),
         "stamp": None, "board": 3}
    d = {"deadlines": noticedeadlines.extract([line], enrol.year, enrol.month,
                                              noticedeadlines.load_patterns())}
    env.lev.notice_deadlines(eventnotices.NoticeService.deadline_rows([n], {10800: d}, SLOT, {}))
    assert not any(s.get("source") is None for s in env.lev.samples())
    v = env.lev.view()
    assert v["rate_pct_h"] == 3.0 and v["eta_next_s"] == int(92 / 3 * 3600)
    assert len(v["deadlines"]) == 1 and v["deadlines"][0]["by"] == "notice"
    assert v["deadlines"][0]["state"] in ("on_track", "tight", "late")
