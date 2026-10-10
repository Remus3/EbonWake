"""Plan 111: auto-apply high-confidence OCR suggestions (book use, zone reads,
world boss loot ticks) at AUTO_APPLY_MIN with an Undo and the `auto_applied`
log; low confidence still queues. Stub OCR docs only; nothing runs Tesseract."""

import datetime as dt

import pytest

from server.ew import bosses, grind, leveling, ocr, ocrauto, ocrinfer, spots, xpbooks, zoneinfo
from server.ew.store import Store

T0 = 1_790_000_000.0
CAPS = [{"level_min": 56, "level_max": 61, "note": "per-kill XP cap ~0.2% of the level"}]
EPOCHS = [{"id": "cap75-xp-rescale", "starts_utc": "2026-01-01T00:00:00+00:00", "label": "cap",
           "source": "test", "verified": False, "kill_xp_cap": CAPS}]


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).replace(microsecond=0).isoformat()


def _doc(*texts):
    lines = [{"text": t, "x": 0, "y": 20 * i, "w": 100, "h": 10} for i, t in enumerate(texts)]
    return {"text": "\n".join(texts), "lines": lines}


def _panel(rows=(("Polly Forest Fighter", "0.0450%"), ("Polly Forest Shaman", "0.0520%"))):
    lines = [{"text": "Monster Zone Info", "x": 600, "y": 120, "w": 300, "h": 18},
             {"text": "Lv. 56 Polly's Forest", "x": 420, "y": 170, "w": 300, "h": 18}]
    for i, (name, pct) in enumerate(rows):
        lines.append({"text": f"{name}  {pct}", "x": 440, "y": 210 + 30 * i, "w": 560, "h": 18})
    return {"text": "\n".join(x["text"] for x in lines), "lines": lines}


class FakeGame:
    def __init__(self, shot_dir):
        self.shot_dir = shot_dir
        self.shots = []

    def add(self, name, ts, size=10):
        (self.shot_dir / name).write_bytes(b"x" * size)
        self.shots.insert(0, {"name": name, "size": size, "mtime": _iso(ts)})

    def view(self):
        return {"screenshots": [dict(s) for s in self.shots]}


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def env(tmp_path):
    shot_dir = tmp_path / "ScreenShot"
    shot_dir.mkdir()
    game = FakeGame(shot_dir)
    docs = {}
    clock = Clock()
    store = Store(tmp_path / "store")
    g = grind.GrindService(store, clock=clock, presets=[])
    books = xpbooks.XpBooksService(store, clock=clock)
    lev = leveling.LevelingService(store, clock=clock, epochs=EPOCHS, deadlines=[], books=books,
                                   buffs=lambda: g.view()["buffs"])
    zones = zoneinfo.ZoneXpService(store, spots.load_table(), state=lev.xp_state,
                                   active_spot=lambda: None, clock=clock)
    boss = bosses.BossService(store, clock=clock)
    reader = ocr.OcrService(game, tmp_path / "ocr", runner=lambda p: docs[p.name])
    auto = ocrauto.AutoOcr(store, game, reader, g, settings=lambda: {}, clock=clock,
                           leveling=lev, zones=zones, bosses=boss)

    class Env:
        pass

    e = Env()
    e.__dict__.update(game=game, docs=docs, clock=clock, store=store, books=books, lev=lev,
                      zones=zones, bosses=boss, auto=auto)
    return e


def _run(e, shots, start=T0 - 7200):
    e.auto.on_game(None, "logged_in", start)
    for name, ts, doc in shots:
        e.game.add(name, ts)
        e.docs[name] = doc
    e.clock.t = max(ts for _, ts, _ in shots) + 60
    e.auto.scan()
    e.auto.drain()


def _applied(e, kind=None):
    return [a for a in e.auto.view()["applied"] if kind is None or a["kind"] == kind]


def _review(e, kind):
    return [r for r in e.auto.view()["review"] if r["kind"] == kind]


# -- book use ---------------------------------------------------------------------

PREV = {"ts": _iso(T0 - 300), "level": 61, "pct": 10}


@pytest.mark.parametrize("level_conf,conf", [(0.96, 0.96), (0.94, 0.94), (1.0, 1.0)])
def test_book_conf_is_size_match_times_level_read(level_conf, conf):
    sug = ocrinfer.book_suggestion(PREV, 61, 17.5, T0, None, {"large": 7.5}, level_conf)
    assert sug["conf"] == conf and sug["value"]["size"] == "large"


def test_book_conf_zero_when_two_sizes_fit():
    sug = ocrinfer.book_suggestion(PREV, 61, 17.5, T0, None, {"medium": 7.0, "large": 7.5}, 1.0)
    assert sug["conf"] == 0 and "another book size" in sug["why"]


def test_confident_book_use_applies_logs_and_undo_restores(env):
    env.clock.t = T0 - 600
    env.books.add({"size": "large", "n": 1})
    _run(env, [("a.jpg", T0, _doc("Lv 61 10.000%")),
               ("b.jpg", T0 + 300, _doc("Lv 61 17.500%"))])
    assert _review(env, "book_use") == []
    [row] = _applied(env, "book_use")
    assert row["conf"] >= ocrauto.AUTO_APPLY_MIN and row["file"] == "b.jpg"
    assert row["value"] == {"size": "large", "pct_before": 10, "pct_after": 17.5}
    assert row["undone"] is False and row["id"].startswith("a")
    assert env.books.view(61, 17.5, None)["owned"]["large"] == 0
    env.auto.undo_applied(row["id"])
    assert env.books.view(61, 17.5, None)["owned"]["large"] == 1
    assert env.books.view(61, 17.5, None)["used"] == []
    assert _applied(env, "book_use")[0]["undone"] is True
    with pytest.raises(ValueError):
        env.auto.undo_applied(row["id"])


def test_book_use_below_the_gate_queues(env):
    env.clock.t = T0 - 600
    env.books.add({"size": "large", "n": 1})
    _run(env, [("a.jpg", T0, _doc("Lv 61 10.000%")),
               ("b.jpg", T0 + 300, _doc("Lv 61 17.950%"))])   # 6 % off one large book
    [item] = _review(env, "book_use")
    assert item["conf"] < ocrauto.AUTO_APPLY_MIN
    assert _applied(env) == []
    assert env.books.view(61, 17.95, None)["owned"]["large"] == 1


def test_undo_from_the_commit_list_marks_the_log_row(env):
    env.clock.t = T0 - 600
    env.books.add({"size": "large", "n": 1})
    _run(env, [("a.jpg", T0, _doc("Lv 61 10.000%")),
               ("b.jpg", T0 + 300, _doc("Lv 61 17.500%"))])
    uid = next(c["id"] for c in env.auto.view()["commits"] if c["kind"] == "book_use")
    env.auto.undo(uid)
    assert _applied(env, "book_use")[0]["undone"] is True


# -- zone reads -------------------------------------------------------------------

def test_confident_zone_read_commits_logs_and_undo_restores(env):
    env.lev.ocr_sample(57, 40.0, T0 - 600)
    _run(env, [("z1.jpg", T0, _panel())])
    [row] = _applied(env, "zone_xp")
    assert row["conf"] >= ocrauto.AUTO_APPLY_MIN and row["value"]["zone_name"] == "Polly's Forest"
    assert [z["key"] for z in env.zones.view()["zones"]] == ["polly-forest"]
    env.auto.undo_applied(row["id"])
    assert env.zones.view()["zones"] == []
    assert _applied(env, "zone_xp")[0]["undone"] is True


def test_low_confidence_zone_read_queues(env):
    env.lev.ocr_sample(57, 40.0, T0 - 600)
    _run(env, [("z1.jpg", T0, _panel(rows=[("Polly Forest Fighter", "00450%")]))])
    [r] = _review(env, "zone_xp")
    assert r["conf"] < ocrauto.AUTO_COMMIT_MIN
    assert _applied(env) == [] and env.zones.view()["zones"] == []


# -- world boss loot --------------------------------------------------------------

def _spawn(table, want=None, skip=("Garmoth",)):
    now = dt.datetime.fromtimestamp(T0, dt.timezone.utc)
    for s in bosses.next_spawns(now, 60, table):
        if (want is None and not set(s["bosses"]) & set(skip)) or want in s["bosses"]:
            return s, dt.datetime.fromisoformat(s["at_utc"]).timestamp()
    raise AssertionError("no spawn found")


def test_boss_named_in_the_shot_inside_the_window_ticks_by_auto(env):
    s, at = _spawn(env.bosses.table)
    boss = s["bosses"][-1]
    _run(env, [("loot.jpg", at + 300, _doc(f"{boss}'s Treasure Box", "Obtained"))],
         start=at - 3600)
    v = env.bosses.view()
    assert v["looted"] == {s["day"]: [boss]} and v["auto"] == {s["day"]: [boss]}
    [row] = _applied(env, "boss")
    assert row["value"] == {"day": s["day"], "boss": boss} and row["conf"] == 1.0
    # Undo unticks and blocks a re-tick from the next shot of the same screen
    env.auto.undo_applied(row["id"])
    assert env.bosses.view()["looted"] == {}
    assert _applied(env, "boss")[0]["undone"] is True
    _run(env, [("loot2.jpg", at + 400, _doc(f"{boss}'s Treasure Box"))], start=at - 3600)
    assert env.bosses.view()["looted"] == {}


def test_time_only_or_before_spawn_stays_a_suggestion(env):
    s, at = _spawn(env.bosses.table)
    boss = s["bosses"][-1]
    _run(env, [("near.jpg", at + 300, _doc("Silver 1,000")),
               ("early.jpg", at - 300, _doc(f"{boss}'s Treasure Box"))], start=at - 3600)
    assert env.bosses.view()["looted"] == {}
    assert _applied(env, "boss") == []


def test_garmoth_weekly_cap_blocks_an_auto_tick(env):
    s, at = _spawn(env.bosses.table, want="Garmoth")
    cap = env.bosses.table["rules"]["garmoth_loot_per_week"]
    day = dt.date.fromisoformat(s["day"])
    env.clock.t = at + 360
    reset = bosses.last_weekly_reset(dt.datetime.fromtimestamp(at, dt.timezone.utc))
    ticked = _iso(max(reset.timestamp(), at - 600) + 1)
    looted = {f"{(day - dt.timedelta(days=i + 1)).isoformat()}|Garmoth": ticked
              for i in range(cap)}
    env.store.put("bosses", {"looted": looted})
    assert env.bosses.view()["garmoth"]["looted"] == cap
    _run(env, [("g.jpg", at + 300, _doc("Garmoth's Treasure Box"))], start=at - 3600)
    assert s["day"] not in env.bosses.view()["looted"]
    assert _applied(env, "boss") == []


def test_garmoth_ticks_under_the_cap(env):
    s, at = _spawn(env.bosses.table, want="Garmoth")
    _run(env, [("g.jpg", at + 300, _doc("Garmoth's Treasure Box"))], start=at - 3600)
    assert env.bosses.view()["looted"][s["day"]] == ["Garmoth"]
    assert env.bosses.view()["garmoth"]["looted"] == 1


def test_operator_untick_blocks_auto_tick(env):
    s, at = _spawn(env.bosses.table)
    boss = s["bosses"][-1]
    env.clock.t = at + 360
    env.bosses.untick({"boss": boss, "day": s["day"]})
    assert env.bosses.auto_tick(s["day"], boss) is False
    env.bosses.tick({"boss": boss, "day": s["day"]})       # a manual tick still works
    assert env.bosses.view()["looted"] == {s["day"]: [boss]}
    assert env.bosses.view()["auto"] == {}


# -- log --------------------------------------------------------------------------

def test_log_bounded_newest_first(env):
    for i in range(ocrauto.MAX_APPLIED + 5):
        env.auto._log_applied("boss", {"day": "2026-09-21", "boss": "Kzarka"}, 1.0, f"{i}.jpg",
                              f"x{i}")
    items = env.store.get("auto_applied")["items"]
    assert len(items) == ocrauto.MAX_APPLIED
    assert items[0]["file"] == f"{ocrauto.MAX_APPLIED + 4}.jpg"
    view = env.auto.view()["applied"]
    assert len(view) == ocrauto.VIEW_APPLIED and view[0]["id"] == items[0]["id"]
    assert set(view[0]) == {"id", "at", "kind", "value", "conf", "file", "undone"}


@pytest.mark.parametrize("bad", ["u1", "a", "ax", 3, None, "a99"])
def test_undo_applied_rejects_bad_ids(env, bad):
    with pytest.raises(ValueError):
        env.auto.undo_applied(bad)
