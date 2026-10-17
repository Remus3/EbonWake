"""Plan 114: more Today auto rules - `shot:<cue>` (OCR text of a logged-in
screenshot the operator took matches a tracked cue) and `bosses:N` (the week's
world boss loot ticks reach N). Event rows stay manual.

Inputs are the session-log state, the plan 063 OCR doc of each shot and EW's
own boss ticks; nothing is read from or sent to the game.
"""

import datetime as dt
import json
import re

import pytest

from server.ew import autotick, bosses, gamewatch, ocrauto, today
from server.ew.store import Store

UTC = dt.timezone.utc


def T(*a):
    return dt.datetime(*a, tzinfo=UTC)


class Clock:
    def __init__(self, when):
        self.t = when.timestamp()

    def __call__(self):
        return self.t

    def set(self, when):
        self.t = when.timestamp()


class FakeGame:
    def __init__(self):
        self.listeners, self.pollers = [], []
        self.state, self.shots = "not_running", []

    def view(self):
        return {"state": self.state, "screenshots": [dict(s) for s in self.shots]}


def _doc(*texts):
    return {"text": "\n".join(texts),
            "lines": [{"text": t, "x": 0, "y": 20 * i, "w": 100, "h": 10}
                      for i, t in enumerate(texts)]}


def _item(v, iid):
    return next(i for i in v["items"] if i["id"] == iid)


def _rig(tmp_path, when, enabled=True):
    clk = Clock(when)
    store = Store(tmp_path / "store")
    svc = today.TodayService(store, clock=clk)
    rule, grants, verified = today.dice_preset()
    dice = gamewatch.DiceClock(store, rule, grants, verified=verified, clock=clk)
    game = FakeGame()
    table = bosses.load_table()
    boss_svc = bosses.BossService(store, clock=clk, table=table)
    changes = []
    at = autotick.AutoTick(store, svc, dice, game, table=table, bosses=boss_svc,
                           settings=lambda: {"checklist.auto": enabled}, clock=clk,
                           on_change=lambda: changes.append(1))
    return clk, svc, boss_svc, at, changes


def _login(at, when):
    at.on_game("running", "logged_in", when.timestamp())


def _logout(at, when):
    at.on_game("logged_in", "running", when.timestamp())


SHOT_ROWS = {
    "daily-challenges-y": "shot:challenges_daily",
    "barter-run": "shot:barter",
    "guild-mission": "shot:guild_mission",
    "black-spirit-weekly-quests": "shot:bs_weekly",
    "pearl-shop-weekly-free-item": "shot:pearl_free",
}
FIXTURES = {
    "daily-challenges-y": _doc("Challenges", "Daily", "All rewards claimed", "Completed"),
    "barter-run": _doc("Barter", "Exchange complete", "Parley 1,200"),
    "guild-mission": _doc("Guild Mission", "Mission Complete", "Reward: Guild Funds"),
    "black-spirit-weekly-quests": _doc("Black Spirit", "[Weekly] Kill monsters", "Complete"),
    "pearl-shop-weekly-free-item": _doc("Pearl Shop", "Weekly free item", "Purchase Limit 0/1"),
}


# --- grammar ----------------------------------------------------------------------

@pytest.mark.parametrize("rule, want", [
    ("shot:barter", ("shot", "barter")),
    ("shot:challenges_daily", ("shot", "challenges_daily")),
    ("bosses:1", ("bosses", 1)),
    ("bosses:12", ("bosses", 12)),
    ("login", ("login", None)),
    ("ready_minutes:60", ("ready_minutes", 60)),
])
def test_grammar_accepts(rule, want):
    assert today.parse_auto(rule) == want


@pytest.mark.parametrize("rule", [
    "shot:", "shot:Barter", "shot: barter", "shot:bar ter", "shot:" + "a" * 41, "shot",
    "bosses", "bosses:0", "bosses:01", "bosses:-1", "bosses:x", "bosses:101", "boss:1",
])
def test_grammar_rejects(rule):
    with pytest.raises(ValueError):
        today.parse_auto(rule)


def test_event_rows_take_no_shot_rule(tmp_path):
    svc = today.TodayService(Store(tmp_path / "store"), clock=Clock(T(2026, 10, 7, 12)))
    with pytest.raises(ValueError):
        svc.add({"title": "Ev", "kind": "event", "until": "2026-10-20", "auto": "shot:barter"})
    v = svc.add({"title": "Mine", "kind": "daily", "auto": "shot:barter"})
    assert _item(v, "mine")["auto"] == "shot:barter"


# --- cue data ---------------------------------------------------------------------

def test_cue_file_schema():
    raw = json.loads(today.CUES_FILE.read_text(encoding="ascii"))
    raw.pop(today.SCHED_CUE)  # plan 127: its own shape (test_scheduler_ocr)
    assert set(raw) == {"challenges_daily", "barter", "guild_mission", "bs_weekly",
                        "pearl_free"}
    for cue, row in raw.items():
        assert re.fullmatch(r"[a-z0-9_]{1,40}", cue)
        assert set(row) <= {"patterns", "all", "source", "verified"}
        assert row["patterns"] and all(isinstance(p, str) for p in row["patterns"])
        for p in row["patterns"] + row.get("all", []):
            re.compile(p)
        assert isinstance(row["source"], str) and row["source"].strip()
        assert row["verified"] is False
    cues = today.load_cues()
    assert set(cues) == set(raw)


@pytest.mark.parametrize("doc", [
    [], {"x": 1}, {"Bad": {"patterns": ["a"], "source": "s", "verified": False}},
    {"x": {"patterns": [], "source": "s", "verified": False}},
    {"x": {"patterns": ["("], "source": "s", "verified": False}},
    {"x": {"patterns": ["a"], "source": "", "verified": False}},
    {"x": {"patterns": ["a"], "source": "s", "verified": "no"}},
    {"x": {"patterns": ["a"], "source": "s", "verified": False, "extra": 1}},
    {"x": {"patterns": ["a"], "all": "b", "source": "s", "verified": False}},
])
def test_bad_cue_file_raises(tmp_path, doc):
    p = tmp_path / "cues.json"
    p.write_text(json.dumps(doc), encoding="ascii")
    with pytest.raises(ValueError):
        today.load_cues(p)


def test_cue_match_needs_any_pattern_and_every_all():
    cues = today.load_cues()
    assert today.cue_matches(cues["barter"], "BARTER\nexchange COMPLETE")
    assert not today.cue_matches(cues["barter"], "Barter")  # no completion text
    assert not today.cue_matches(cues["barter"], "exchange complete")  # no barter
    assert not today.cue_matches(cues["barter"], None)


# --- seed + migration -------------------------------------------------------------

def test_seed_binds_the_new_rules(tmp_path):
    v = today.TodayService(Store(tmp_path / "store"), clock=Clock(T(2026, 10, 7, 12))).view()
    for iid, rule in SHOT_ROWS.items():
        assert _item(v, iid)["auto"] == rule
    assert _item(v, "weekly-boss-rewards")["auto"] == "bosses:1"
    assert _item(v, "attendance-reward")["auto"] == "login"


def test_migration_adds_rules_only_where_missing(tmp_path):
    store = Store(tmp_path / "store")
    store.put("today", {"items": [
        {"id": "barter-run", "title": "Barter run", "kind": "daily", "until": None, "order": 0},
        {"id": "guild-mission", "title": "Guild mission", "kind": "daily", "until": None,
         "order": 1, "auto": "login"},
        {"id": "weekly-boss-rewards", "title": "Weekly boss rewards", "kind": "weekly",
         "until": None, "order": 2},
        {"id": "festival", "title": "Festival", "kind": "event", "until": "2026-10-30",
         "order": 3}], "ticks": {}})
    v = today.TodayService(store, clock=Clock(T(2026, 10, 7, 12))).view()
    assert _item(v, "barter-run")["auto"] == "shot:barter"
    assert _item(v, "guild-mission")["auto"] == "login"  # an existing rule is kept
    assert _item(v, "weekly-boss-rewards")["auto"] == "bosses:1"
    assert "auto" not in _item(v, "festival")  # event rows stay manual


# --- shot cues --------------------------------------------------------------------

@pytest.mark.parametrize("iid", sorted(SHOT_ROWS))
def test_each_fixture_ticks_only_its_row(tmp_path, iid):
    clk, svc, _, at, changes = _rig(tmp_path, T(2026, 10, 7, 12))
    _login(at, T(2026, 10, 7, 11))
    shot_at = T(2026, 10, 7, 11, 30).timestamp()
    assert at.on_doc("s.jpg", FIXTURES[iid], shot_at) is True
    v = svc.view()
    row = _item(v, iid)
    assert row["done"] is True and row["by"] == "auto"
    assert row["ticked_at"] == "2026-10-07T11:30:00+00:00"
    others = [i["id"] for i in v["items"] if i["done"] and i["id"] != iid
              and i["id"] != "attendance-reward"]
    assert others == []
    assert changes


def test_shot_outside_logged_in_windows_ticks_nothing(tmp_path):
    clk, svc, _, at, _ = _rig(tmp_path, T(2026, 10, 7, 14))
    _login(at, T(2026, 10, 7, 11))
    _logout(at, T(2026, 10, 7, 12))
    doc = FIXTURES["barter-run"]
    assert at.on_doc("a.jpg", doc, T(2026, 10, 7, 10, 59).timestamp()) is False
    assert at.on_doc("b.jpg", doc, T(2026, 10, 7, 12, 0, 30).timestamp()) is False
    assert _item(svc.view(), "barter-run")["done"] is False


def test_unrelated_text_ticks_nothing(tmp_path):
    clk, svc, _, at, changes = _rig(tmp_path, T(2026, 10, 7, 12))
    _login(at, T(2026, 10, 7, 11))
    assert at.on_doc("a.jpg", _doc("Silver 1,234,567"), T(2026, 10, 7, 11, 5).timestamp()) \
        is False
    assert not any(i["done"] for i in svc.view()["items"] if i["id"] in SHOT_ROWS)


def test_disabled_ticks_nothing(tmp_path):
    clk, svc, _, at, _ = _rig(tmp_path, T(2026, 10, 7, 12), enabled=False)
    _login(at, T(2026, 10, 7, 11))
    assert at.on_doc("a.jpg", FIXTURES["barter-run"], T(2026, 10, 7, 11, 5).timestamp()) \
        is False


def test_untick_blocks_until_reset(tmp_path):
    clk, svc, _, at, _ = _rig(tmp_path, T(2026, 10, 7, 12))
    _login(at, T(2026, 10, 7, 11))
    doc = FIXTURES["barter-run"]
    assert at.on_doc("a.jpg", doc, T(2026, 10, 7, 11, 5).timestamp())
    row = _item(svc.untick("barter-run"), "barter-run")
    assert row["done"] is False and row["auto_blocked"] is True
    assert at.on_doc("b.jpg", doc, T(2026, 10, 7, 11, 50).timestamp()) is False
    clk.set(T(2026, 10, 8, 1))
    assert at.on_doc("c.jpg", doc, T(2026, 10, 8, 0, 30).timestamp()) is True
    assert _item(svc.view(), "barter-run")["by"] == "auto"


def test_weekly_shot_row_holds_until_thursday(tmp_path):
    clk, svc, _, at, _ = _rig(tmp_path, T(2026, 10, 7, 12))  # a Wednesday
    _login(at, T(2026, 10, 7, 11))
    at.on_doc("a.jpg", FIXTURES["pearl-shop-weekly-free-item"], T(2026, 10, 7, 11).timestamp())
    clk.set(T(2026, 10, 7, 23, 59))
    assert _item(svc.view(), "pearl-shop-weekly-free-item")["done"] is True
    clk.set(T(2026, 10, 8, 0, 0))
    assert _item(svc.view(), "pearl-shop-weekly-free-item")["done"] is False


# --- bosses:N ---------------------------------------------------------------------

def _boss_on(boss_svc, day):
    week = bosses._by_weekday(boss_svc.table)
    return week[dt.date.fromisoformat(day).weekday()][0]["bosses"][0]


def test_bosses_rule_ticks_on_first_weekly_loot_and_resets_thursday(tmp_path):
    clk, svc, boss_svc, at, _ = _rig(tmp_path, T(2026, 10, 7, 20))  # Wed, PT 13:00
    assert at.evaluate(clk()) is False
    assert _item(svc.view(), "weekly-boss-rewards")["done"] is False
    day = "2026-10-07"
    boss_svc.tick({"boss": _boss_on(boss_svc, day), "day": day})
    assert at.evaluate(clk()) is True
    row = _item(svc.view(), "weekly-boss-rewards")
    assert row["done"] is True and row["by"] == "auto"
    clk.set(T(2026, 10, 8, 0, 0))  # Thursday 00:00 UTC: weekly reset
    assert _item(svc.view(), "weekly-boss-rewards")["done"] is False
    assert at.evaluate(clk()) is False  # last week's loot does not count
    assert _item(svc.view(), "weekly-boss-rewards")["done"] is False


def test_bosses_rule_counts_n(tmp_path):
    clk, svc, boss_svc, at, _ = _rig(tmp_path, T(2026, 10, 7, 20))
    svc.add({"title": "Two bosses", "kind": "weekly", "auto": "bosses:2"})
    day = "2026-10-07"
    boss_svc.tick({"boss": _boss_on(boss_svc, day), "day": day})
    at.evaluate(clk())
    assert _item(svc.view(), "two-bosses")["done"] is False
    other = "2026-10-06"
    boss_svc.tick({"boss": _boss_on(boss_svc, other), "day": other})  # ticked this week
    at.evaluate(clk())
    assert _item(svc.view(), "two-bosses")["done"] is True


def test_bosses_rule_untick_blocks(tmp_path):
    clk, svc, boss_svc, at, _ = _rig(tmp_path, T(2026, 10, 7, 20))
    day = "2026-10-07"
    boss_svc.tick({"boss": _boss_on(boss_svc, day), "day": day})
    at.evaluate(clk())
    svc.untick("weekly-boss-rewards")
    at.evaluate(clk())
    assert _item(svc.view(), "weekly-boss-rewards")["done"] is False


# --- the plan 063 worker hands its doc over (no second OCR) ----------------------

class _OcrGame:
    shot_dir = None

    def view(self):
        return {"screenshots": []}


class _Reader:
    def __init__(self, doc):
        self.doc_ = doc
        self.calls = 0

    def doc(self, name):
        self.calls += 1
        return self.doc_


def test_ocr_worker_calls_on_doc_once_per_read(tmp_path):
    seen = []
    reader = _Reader(FIXTURES["barter-run"])
    auto = ocrauto.AutoOcr(Store(tmp_path / "store"), _OcrGame(), reader, None,
                           clock=lambda: 1_790_000_100.0,
                           on_doc=lambda f, d, s: seen.append((f, d["text"], s)))
    auto.on_game(None, "logged_in", 1_790_000_000.0)
    shot = {"name": "x.jpg", "size": 10, "mtime": "2026-09-22T11:33:30+00:00"}
    auto._process("k", shot)
    assert reader.calls == 1
    assert seen == [("x.jpg", FIXTURES["barter-run"]["text"],
                     dt.datetime(2026, 9, 22, 11, 33, 30, tzinfo=UTC).timestamp())]


def test_ocr_worker_survives_a_broken_on_doc(tmp_path):
    def boom(*a):
        raise RuntimeError("x")

    reader = _Reader(FIXTURES["barter-run"])
    auto = ocrauto.AutoOcr(Store(tmp_path / "store"), _OcrGame(), reader, None,
                           clock=lambda: 1_790_000_100.0, on_doc=boom)
    auto._process("k", {"name": "x.jpg", "size": 10, "mtime": "2026-09-22T11:33:30+00:00"})
    # reached without raising, and the shot was still read: the hook's error never
    # breaks the worker (plan 151 TESTS-B-03: was a vacuous `ocr is not None`)
    assert reader.calls == 1


def test_app_wires_ocr_doc_to_autotick():
    src = (today.Path(autotick.__file__).parent / "app.py").read_text(encoding="ascii")
    assert "self.ocr_auto.on_doc = self.autotick.on_doc" in src
    assert "bosses=self.bosses" in src
