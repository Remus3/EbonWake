"""Plan 118: Deadeye enhance state from OCR - an enhancement window shot reads
the current failstack, the crons on hand and the Agris pity stacks into the
plan 036 Stacks block and the plan 035 EV calc; typed entry stays optional.
Stub OCR engine only; nothing runs Tesseract or touches the game."""

import datetime as dt

import pytest

from server.ew import deadeye, enhance, grind, ocr, ocrauto, ocrinfer
from server.ew.store import Store

UTC = dt.timezone.utc
ROWS = enhance.load_table()["rows"]
KEYS = {(r["family"], r["step"]): r.get("agris_threshold") for r in ROWS}


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def _ln(text, y=0, x=0, w=300, h=20):
    return {"text": text, "x": x, "y": y, "w": w, "h": h}


def _doc(*lines):
    lines = [ln if isinstance(ln, dict) else _ln(ln, y=40 * i) for i, ln in enumerate(lines)]
    return {"text": "\n".join(ln["text"] for ln in lines), "lines": lines}


NOW = ts("2026-10-10T12:00:00Z")
WINDOW = _doc("Enhancement", "TRI: Sovereign Longbow", "Failstack: 45",
              "Use 560 Cron Stones (Owned: 1,234)", "Agris Essence 3 / 20")


def _by_kind(fields):
    return {f["kind"]: f for f in fields}


# -- slice 1: parser -------------------------------------------------------------------

def test_window_fixture_reads_all_three():
    out = _by_kind(ocrinfer.enhance_fields(WINDOW, KEYS))
    assert out["enh_fs"]["value"] == 45 and out["enh_fs"]["name"] == "fs"
    assert out["enh_crons"]["value"] == 1234 and out["enh_crons"]["name"] == "crons"
    assert out["enh_agris"]["value"] == {"family": "sovereign", "step": "TET", "stacks": 3}
    assert out["enh_agris"]["name"] == "sovereign TET"
    for f in out.values():
        assert f["conf"] >= ocrauto.AUTO_COMMIT_MIN and f["why"]


def test_no_anchor_no_fields():
    doc = _doc("Failstack: 45", "Cron Stone x 1,234", "Agris Essence 3 / 20")
    assert ocrinfer.enhance_fields(doc, KEYS) == []


@pytest.mark.parametrize("line", ["Failstack: 45", "Failstacks +45",
                                  "Enhancement Chance Increase +45", "FS 45"])
def test_fs_shapes(line):
    out = _by_kind(ocrinfer.enhance_fields(_doc("Enhance", line), KEYS))
    assert out["enh_fs"]["value"] == 45


def test_fs_out_of_range_ignored():
    assert ocrinfer.enhance_fields(_doc("Enhance", "Failstack: 1000"), KEYS) == []


@pytest.mark.parametrize("lines,want", [
    (("Cron Stone x 1,234",), 1234),
    (("Cron Stones Owned: 1,234",), 1234),
    (("Cron Stones 560 / 1,234",), 1234),
    (("Cron Stone", "Owned: 1,234"), 1234),
    (("Crom Stones x 80",), 80),
])
def test_cron_shapes(lines, want):
    out = _by_kind(ocrinfer.enhance_fields(_doc("Enhancement", *lines), KEYS))
    assert out["enh_crons"]["value"] == want


def test_cron_cost_line_skipped():
    assert ocrinfer.enhance_fields(_doc("Enhancement", "Required: 560 Cron Stones"), KEYS) == []


def test_two_fs_values_lower_the_confidence():
    out = _by_kind(ocrinfer.enhance_fields(_doc("Enhance", "Failstack: 45", "FS 50"), KEYS))
    assert out["enh_fs"]["conf"] < ocrauto.AUTO_COMMIT_MIN


def test_agris_with_plus_level_item():
    doc = _doc("Enhancement", "+15 Kharazad Ring", "Agris Stacks: 2")
    out = _by_kind(ocrinfer.enhance_fields(doc, KEYS))
    # +15 has no kharazad rows past +15 except PRI: the first level above with a row
    assert out["enh_agris"]["value"] == {"family": "kharazad", "step": "PRI", "stacks": 2}


def test_agris_fallback_key_lowers_conf():
    doc = _doc("Enhancement", "Agris Essence 3 / 20")
    assert ocrinfer.enhance_fields(doc, KEYS) == []
    out = _by_kind(ocrinfer.enhance_fields(doc, KEYS, fallback=("sovereign", "TET")))
    f = out["enh_agris"]
    assert f["value"] == {"family": "sovereign", "step": "TET", "stacks": 3}
    assert f["conf"] < ocrauto.AUTO_COMMIT_MIN and "plan step" in f["why"]


def test_agris_threshold_mismatch_lowers_conf():
    doc = _doc("Enhancement", "TRI: Sovereign Longbow", "Agris Essence 3 / 7")
    f = _by_kind(ocrinfer.enhance_fields(doc, KEYS))["enh_agris"]
    assert f["conf"] <= 0.5 and "threshold" in f["why"]


# -- slices 2-4: kind wiring, store, EV -----------------------------------------------

class FakeGame:
    def __init__(self, shot_dir):
        self.shot_dir = shot_dir
        self.shots = []

    def add(self, name, when, size=10):
        (self.shot_dir / name).write_bytes(b"x" * size)
        iso = dt.datetime.fromtimestamp(when, UTC).replace(microsecond=0).isoformat()
        self.shots.insert(0, {"name": name, "size": size, "mtime": iso})

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
    clock = Clock(NOW)
    store = Store(tmp_path / "store")
    dead = deadeye.DeadeyeService(store, clock=clock)
    g = grind.GrindService(store, clock=clock, presets=[])
    reader = ocr.OcrService(game, tmp_path / "ocr", runner=lambda p: docs[p.name])
    auto = ocrauto.AutoOcr(store, game, reader, g, settings=lambda: {}, clock=clock,
                           deadeye=dead)
    auto.on_game(None, "logged_in", NOW - 86400)

    class Env:
        pass

    e = Env()
    e.__dict__.update(game=game, docs=docs, clock=clock, store=store, dead=dead, auto=auto)
    return e


def _shot(e, name, when, doc):
    e.game.add(name, when)
    e.docs[name] = doc
    e.auto.scan()
    e.auto.drain()


def _st(e):
    return e.dead.view()["stacks"]


def test_kinds_registered():
    for k in ("enh_fs", "enh_crons", "enh_agris"):
        assert k in ocrauto.KINDS and k in ocrauto.FIX_KINDS


def test_acceptance_window_commits_and_undo(env):
    env.dead.crons_set({"owned": 10, "weekly_income": 300})
    env.clock.t = NOW + 60
    _shot(env, "enh.png", NOW + 30, WINDOW)
    st = _st(env)
    assert st["fs_now"]["value"] == 45 and st["fs_now"]["source"] == "ocr:enh.png"
    assert st["crons"] == {"owned": 1234, "weekly_income": 300}
    assert st["reads"]["crons"]["source"] == "ocr:enh.png"
    agris = [a for a in st["agris"] if (a["family"], a["step"]) == ("sovereign", "TET")]
    assert agris[0]["stacks"] == 3 and agris[0]["source"] == "ocr:enh.png"
    assert env.auto.view()["review"] == []
    for c in env.auto.view()["commits"]:
        env.auto.undo(c["id"])
    st = _st(env)
    assert st["fs_now"] is None and st["crons"]["owned"] == 10 and st["agris"] == []
    assert st["reads"]["crons"] is None


def test_older_shot_skipped(env):
    _shot(env, "new.png", NOW - 60, _doc("Enhancement", "Failstack: 50"))
    _shot(env, "old.png", NOW - 600, _doc("Enhancement", "Failstack: 45"))
    assert _st(env)["fs_now"]["value"] == 50
    assert env.auto.view()["review"] == []


def test_newer_typed_wins_over_older_read(env):
    _shot(env, "c.png", NOW - 3600, _doc("Enhancement", "Cron Stone x 1,234"))
    env.dead.crons_set({"owned": 500})  # typed at NOW, after the shot
    assert _st(env)["crons"]["owned"] == 500 and _st(env)["reads"]["crons"] is None
    _shot(env, "c2.png", NOW - 1800, _doc("Enhancement", "Cron Stone x 900"))
    assert _st(env)["crons"]["owned"] == 500  # older than the typed value: skipped
    env.clock.t = NOW + 20
    _shot(env, "c3.png", NOW + 10, _doc("Enhancement", "Cron Stone x 900"))
    assert _st(env)["crons"]["owned"] == 900


def test_typed_agris_newer_than_read_wins(env):
    env.dead.agris_set({"family": "sovereign", "step": "TET", "stacks": 5})
    _shot(env, "a.png", NOW - 60, WINDOW)
    agris = _st(env)["agris"]
    assert [(a["family"], a["step"], a["stacks"]) for a in agris] == [("sovereign", "TET", 5)]


def test_agris_above_threshold_held_then_fix(env):
    doc = _doc("Enhancement", "TRI: Sovereign Longbow", "Agris Stacks: 25")
    _shot(env, "h.png", NOW - 60, doc)
    rv = env.auto.view()["review"]
    assert [r["kind"] for r in rv] == ["enh_agris"] and "threshold" in rv[0]["why"]
    assert _st(env)["agris"] == []
    env.auto.review({"id": rv[0]["id"], "action": "fix", "value": 4})
    agris = _st(env)["agris"]
    assert [(a["family"], a["step"], a["stacks"]) for a in agris] == [("sovereign", "TET", 4)]


def test_agris_read_zero_clears_row(env):
    env.clock.t = NOW - 7200
    env.dead.agris_set({"family": "sovereign", "step": "TET", "stacks": 5})
    env.clock.t = NOW
    _shot(env, "z.png", NOW - 60, _doc("Enhancement", "TRI: Sovereign Longbow",
                                       "Agris Stacks: 0"))
    assert _st(env)["agris"] == []
    env.auto.undo(env.auto.view()["commits"][0]["id"])
    assert [a["stacks"] for a in _st(env)["agris"]] == [5]


def test_fallback_key_goes_to_review(env):
    env.dead.add_step({"item": "Sovereign Longbow", "current": "TRI", "target": "TET"})
    _shot(env, "f.png", NOW - 60, _doc("Enhancement", "Agris Essence 3 / 20"))
    rv = env.auto.view()["review"]
    assert [(r["kind"], r["value"]) for r in rv] == [
        ("enh_agris", {"family": "sovereign", "step": "TET", "stacks": 3})]
    env.auto.review({"id": rv[0]["id"], "action": "accept"})
    assert [a["stacks"] for a in _st(env)["agris"]] == [3]


def test_ocr_set_validation(env):
    for kind, value in (("enh_fs", -1), ("enh_fs", 1000), ("enh_fs", True),
                        ("enh_crons", 10 ** 10), ("nope", 1),
                        ("enh_agris", {"family": "x", "step": "ZZZ", "stacks": 1}),
                        ("enh_agris", {"family": "sovereign", "step": "TET", "stacks": -1})):
        with pytest.raises(ValueError):
            env.dead.ocr_set(kind, value, source="ocr:x.png", at=NOW)
    with pytest.raises(ValueError):
        env.dead.ocr_set("enh_fs", 5, source="typed", at=NOW)


def test_ev_query_uses_fs_read(tmp_path):
    store = Store(tmp_path / "store")
    reads = {"fs": None}
    svc = enhance.EnhanceService(store, prices=lambda i: None, fs_now=lambda: reads["fs"])
    q = {"family": ["sovereign"], "step": ["PRI"]}
    assert svc.query(q)["fs"] == 0 and svc.query(q)["fs_source"] == "default"
    reads["fs"] = 45
    out = svc.query(q)
    assert out["fs"] == 45 and out["fs_source"] == "ocr"
    typed = svc.query(dict(q, fs=["20"]))
    assert typed["fs"] == 20 and typed["fs_source"] == "query"


def test_fs_now_reader(env):
    assert env.dead.fs_now() is None
    _shot(env, "f.png", NOW - 60, _doc("Enhancement", "Failstack: 45"))
    assert env.dead.fs_now() == 45
