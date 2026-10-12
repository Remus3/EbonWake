"""Plan 127: one Black Spirit's Scheduler screenshot (Menu F8) ticks every
matched done daily / weekly Today row (by: auto, logged in `auto_applied` with
an Undo); open rows are never unticked; an unmatched quest line is queued once
for review as "unknown scheduler row" and its accept adds a Today row.

Stub OCR docs only (nothing runs Tesseract); nothing is read from or sent to
the game.
"""

import datetime as dt
import json

import pytest

from server.ew import autotick, bosses, gamewatch, grind, ocr, ocrauto, ocrinfer, today
from server.ew.store import Store

UTC = dt.timezone.utc


def T(*a):
    return dt.datetime(*a, tzinfo=UTC)


def _iso(when):
    return when.replace(microsecond=0).isoformat()


def _doc(*texts):
    return {"text": "\n".join(texts),
            "lines": [{"text": t, "x": 0, "y": 20 * i, "w": 400, "h": 10}
                      for i, t in enumerate(texts)]}


# 4 quest rows: 2 done (one seed row, one plan 127 seed row), 1 open, 1 unknown.
SCHED = _doc("Black Spirit's Scheduler",
             "Daily  Weekly",
             "[Weekly] Black Spirit's Weekly Quest  Completed",
             "Lyngbakr Ecology Survey  Completed",
             "Daily Challenges  In Progress  05:12",
             "Margoria Sea Patrol  2d 4h")


class Clock:
    def __init__(self, when):
        self.t = when.timestamp()

    def __call__(self):
        return self.t


class FakeGame:
    def __init__(self, shot_dir):
        self.shot_dir = shot_dir
        self.shots = []
        self.state = "logged_in"

    def add(self, name, when, size=10):
        (self.shot_dir / name).write_bytes(b"x" * size)
        self.shots.insert(0, {"name": name, "size": size, "mtime": _iso(when)})

    def view(self):
        return {"state": self.state, "screenshots": [dict(s) for s in self.shots]}


@pytest.fixture
def env(tmp_path):
    shot_dir = tmp_path / "ScreenShot"
    shot_dir.mkdir()
    clk = Clock(T(2026, 10, 7, 12))
    store = Store(tmp_path / "store")
    game = FakeGame(shot_dir)
    svc = today.TodayService(store, clock=clk)
    rule, grants, verified = today.dice_preset()
    dice = gamewatch.DiceClock(store, rule, grants, verified=verified, clock=clk)
    table = bosses.load_table()
    at = autotick.AutoTick(store, svc, dice, game, table=table,
                           bosses=bosses.BossService(store, clock=clk, table=table),
                           settings=lambda: {}, clock=clk)
    docs = {}
    reader = ocr.OcrService(game, tmp_path / "ocr", runner=lambda p: docs[p.name])
    auto = ocrauto.AutoOcr(store, game, reader, grind.GrindService(store, clock=clk, presets=[]),
                           settings=lambda: {}, clock=clk, on_doc=at.on_doc, today_auto=at)

    class Env:
        pass

    e = Env()
    e.__dict__.update(clk=clk, store=store, game=game, today=svc, at=at, docs=docs, auto=auto)
    return e


def _login(e, when):
    e.at.on_game("running", "logged_in", when.timestamp())
    e.auto.on_game("running", "logged_in", when.timestamp())


def _shot(e, name, when, doc):
    e.game.add(name, when)
    e.docs[name] = doc
    e.clk.t = when.timestamp() + 30
    e.auto.scan()
    e.auto.drain()


def _items(e):
    return {i["id"]: i for i in e.today.view()["items"]}


def _review(e):
    return [r for r in e.auto.view()["review"] if r["kind"] == ocrauto.SCHED_KIND]


def _applied(e):
    return [a for a in e.auto.view()["applied"] if a["kind"] == "today"]


# -- cue data -----------------------------------------------------------------------

def test_scheduler_cue_data_schema():
    raw = json.loads(today.CUES_FILE.read_text(encoding="ascii"))["scheduler"]
    assert set(raw) == {"window", "row_patterns", "done", "open", "source", "verified"}
    assert raw["verified"] is False and raw["source"].strip()
    assert "lyngbakr-ecology-survey" in raw["row_patterns"]
    sched = today.load_scheduler()
    assert set(sched["row_patterns"]) == set(raw["row_patterns"])
    assert "scheduler" not in today.load_cues()  # not a plan 114 shot cue


@pytest.mark.parametrize("bad", [
    {"window": [], "row_patterns": {"a": ["x"]}, "done": ["d"], "open": ["o"], "source": "s",
     "verified": False},
    {"window": ["w"], "row_patterns": {"Bad Id": ["x"]}, "done": ["d"], "open": ["o"],
     "source": "s", "verified": False},
    {"window": ["w"], "row_patterns": {"a": ["("]}, "done": ["d"], "open": ["o"],
     "source": "s", "verified": False},
    {"window": ["w"], "row_patterns": {"a": ["x"]}, "done": ["d"], "open": ["o"],
     "source": "s", "verified": "no"},
    {"window": ["w"], "row_patterns": {"a": ["x"]}, "done": ["d"], "source": "s",
     "verified": False},
])
def test_bad_scheduler_data_raises(tmp_path, bad):
    p = tmp_path / "cues.json"
    p.write_text(json.dumps({"scheduler": bad}), encoding="ascii")
    with pytest.raises(ValueError):
        today.load_scheduler(p)


# -- parser -------------------------------------------------------------------------

def test_parser_rows_states_and_remaining_time():
    rows = ocrinfer.scheduler_rows(SCHED)
    by = {r["row"]: r for r in rows}
    assert by["black-spirit-weekly-quests"]["state"] == "done"
    assert by["lyngbakr-ecology-survey"]["state"] == "done"
    assert by["daily-challenges-y"]["state"] == "open"
    assert by["daily-challenges-y"]["remaining_s"] == 5 * 3600 + 12 * 60
    unknown = [r for r in rows if r["row"] is None]
    assert len(unknown) == 1 and unknown[0]["name"] == "Margoria Sea Patrol"
    assert unknown[0]["remaining_s"] == 2 * 86400 + 4 * 3600
    assert unknown[0]["state"] == "open"
    assert len(rows) == 4


@pytest.mark.parametrize("text, secs", [
    ("Guild Mission  1d 3h", 86400 + 3 * 3600), ("Guild Mission  3d", 3 * 86400),
    ("Guild Mission  4h 20m", 4 * 3600 + 20 * 60), ("Guild Mission  12:05", 12 * 3600 + 300),
    ("Guild Mission  01:02:03", 3723), ("Guild Mission  Completed", None),
])
def test_remaining_time_forms(text, secs):
    rows = ocrinfer.scheduler_rows(_doc("Scheduler", text))
    assert rows[0]["row"] == "guild-mission"
    assert rows[0].get("remaining_s") == secs


def test_not_a_scheduler_shot_has_no_rows():
    assert ocrinfer.scheduler_rows(_doc("Black Spirit weekly quest", "Completed")) == []
    assert ocrinfer.scheduler_rows({}) == []
    assert ocrinfer.scheduler_rows(None) == []


def test_title_match_for_operator_rows():
    rows = ocrinfer.scheduler_rows(_doc("Scheduler", "Margoria Sea Patrol  Completed"),
                                   titles={"margoria-sea-patrol": "Margoria Sea Patrol"})
    assert rows == [{"row": "margoria-sea-patrol", "name": "Margoria Sea Patrol",
                     "state": "done", "conf": ocrinfer.CONF_SCHED}]


# -- apply --------------------------------------------------------------------------

def test_fixture_ticks_only_the_done_rows_with_undo(env):
    _login(env, T(2026, 10, 7, 11))
    _shot(env, "sched.jpg", T(2026, 10, 7, 12), SCHED)
    items = _items(env)
    assert items["black-spirit-weekly-quests"]["done"] is True
    assert items["black-spirit-weekly-quests"]["by"] == "auto"
    assert items["lyngbakr-ecology-survey"]["done"] is True  # plan 127 seed row
    assert items["lyngbakr-ecology-survey"]["kind"] == "weekly"
    assert items["daily-challenges-y"]["done"] is False
    for iid in ("barter-run", "guild-mission", "pearl-shop-weekly-free-item"):
        assert items[iid]["done"] is False
    applied = _applied(env)
    assert sorted(a["value"]["row"] for a in applied) == [
        "black-spirit-weekly-quests", "lyngbakr-ecology-survey"]
    assert all(a["conf"] >= ocrauto.AUTO_APPLY_MIN and a["file"] == "sched.jpg"
               for a in applied)
    a = next(a for a in applied if a["value"]["row"] == "lyngbakr-ecology-survey")
    env.auto.undo_applied(a["id"])
    items = _items(env)
    assert items["lyngbakr-ecology-survey"]["done"] is False
    assert items["lyngbakr-ecology-survey"]["auto_blocked"] is True
    assert next(x for x in _applied(env) if x["id"] == a["id"])["undone"] is True
    # a second shot this week does not re-tick the undone row
    _shot(env, "sched2.jpg", T(2026, 10, 7, 13), SCHED)
    assert _items(env)["lyngbakr-ecology-survey"]["done"] is False


def test_open_row_never_unticks(env):
    _login(env, T(2026, 10, 7, 11))
    env.today.tick("daily-challenges-y")
    _shot(env, "sched.jpg", T(2026, 10, 7, 12), SCHED)
    assert _items(env)["daily-challenges-y"]["done"] is True


def test_shot_outside_logged_in_windows_ticks_nothing(env):
    _login(env, T(2026, 10, 7, 9))
    env.at.on_game("logged_in", "running", T(2026, 10, 7, 10).timestamp())
    assert env.at.scheduler(SCHED, T(2026, 10, 7, 12).timestamp()) is None
    _shot(env, "sched.jpg", T(2026, 10, 7, 12), SCHED)
    assert not any(i["done"] for i in env.today.view()["items"]
                   if i["id"] != "attendance-reward")  # the plan 068 login rule
    assert _review(env) == [] and _applied(env) == []
    assert "lyngbakr-ecology-survey" not in _items(env)


def test_operator_untick_blocks_until_reset(env):
    _login(env, T(2026, 10, 7, 11))
    _shot(env, "sched.jpg", T(2026, 10, 7, 12), SCHED)
    env.today.untick("black-spirit-weekly-quests")
    _shot(env, "sched2.jpg", T(2026, 10, 7, 13), SCHED)
    assert _items(env)["black-spirit-weekly-quests"]["done"] is False
    # after the weekly reset (Thursday 00:00 UTC) the same shot ticks again
    _shot(env, "sched3.jpg", T(2026, 10, 8, 1), SCHED)
    assert _items(env)["black-spirit-weekly-quests"]["done"] is True


def test_scheduler_shot_skips_generic_shot_cues(env):
    # the generic bs_weekly cue (black spirit + weekly + complete) would match the
    # whole Scheduler text; the per-line parse decides instead
    _login(env, T(2026, 10, 7, 11))
    doc = _doc("Black Spirit's Scheduler", "[Weekly] Black Spirit's Weekly Quest  In Progress",
               "Lyngbakr Ecology Survey  Completed")
    assert env.at.on_doc("s.jpg", doc, T(2026, 10, 7, 12).timestamp()) is False
    _shot(env, "s.jpg", T(2026, 10, 7, 12), doc)
    assert _items(env)["black-spirit-weekly-quests"]["done"] is False


def test_unknown_row_queued_once_and_accept_adds_row(env):
    _login(env, T(2026, 10, 7, 11))
    _shot(env, "sched.jpg", T(2026, 10, 7, 12), SCHED)
    _shot(env, "sched2.jpg", T(2026, 10, 7, 13), SCHED)
    q = _review(env)
    assert len(q) == 1
    assert q[0]["name"] == "Margoria Sea Patrol"
    assert q[0]["value"] == {"cadence": "weekly", "state": "open",
                             "remaining_s": 2 * 86400 + 4 * 3600}
    assert "unknown scheduler row" in q[0]["why"]
    with pytest.raises(ValueError):
        env.auto.review({"id": q[0]["id"], "action": "fix", "value": 1})
    env.auto.review({"id": q[0]["id"], "action": "accept"})
    row = _items(env)["margoria-sea-patrol"]
    assert row["kind"] == "weekly" and row["auto"] == "shot:scheduler" and row["done"] is False
    assert _review(env) == []
    done = _doc("Black Spirit's Scheduler", "Margoria Sea Patrol  Completed")
    _shot(env, "sched3.jpg", T(2026, 10, 7, 14), done)
    assert _items(env)["margoria-sea-patrol"]["done"] is True
    assert _review(env) == []


def test_discarded_unknown_is_not_queued_again(env):
    _login(env, T(2026, 10, 7, 11))
    _shot(env, "sched.jpg", T(2026, 10, 7, 12), SCHED)
    env.auto.review({"id": _review(env)[0]["id"], "action": "discard"})
    _shot(env, "sched2.jpg", T(2026, 10, 7, 13), SCHED)
    assert _review(env) == []


def test_daily_cadence_for_short_unknown_row(env):
    _login(env, T(2026, 10, 7, 11))
    _shot(env, "s.jpg", T(2026, 10, 7, 12), _doc("Scheduler", "Velia Fishing Request  03:10"))
    assert _review(env)[0]["value"]["cadence"] == "daily"


def test_removed_seed_row_is_not_reseeded(env):
    _login(env, T(2026, 10, 7, 11))
    _shot(env, "sched.jpg", T(2026, 10, 7, 12), SCHED)
    env.today.remove("lyngbakr-ecology-survey")
    _shot(env, "sched2.jpg", T(2026, 10, 7, 13), SCHED)
    assert "lyngbakr-ecology-survey" not in _items(env)
    assert _review(env)[0]["name"] == "Margoria Sea Patrol"  # still only the one unknown
    assert len(_review(env)) == 1


def test_auto_off_ticks_nothing(env):
    env.at.settings = lambda: {"checklist.auto": False}
    _login(env, T(2026, 10, 7, 11))
    _shot(env, "sched.jpg", T(2026, 10, 7, 12), SCHED)
    assert not any(i["done"] for i in env.today.view()["items"])
    assert _review(env) == [] and _applied(env) == []
