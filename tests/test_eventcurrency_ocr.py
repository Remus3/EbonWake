"""Plan 115: event currency balance OCR kind feeding eventcurrency - an
exchange window / tooltip read replaces the typed balance, drops counted.
Stub OCR engine only; nothing runs Tesseract or touches the game."""

import datetime as dt

import pytest

from server.ew import eventcurrency as ec
from server.ew import grind, ocr, ocrauto, ocrinfer
from server.ew.store import Store

UTC = dt.timezone.utc
RULES = ec.load_rules()
R = RULES["10673"]
NAME = R["currency"]  # "Seals of Purification"


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def _ln(text, y=0, x=0, w=300, h=20):
    return {"text": text, "x": x, "y": y, "w": w, "h": h}


def _doc(*lines):
    lines = [ln if isinstance(ln, dict) else _ln(ln, y=40 * i) for i, ln in enumerate(lines)]
    return {"text": "\n".join(ln["text"] for ln in lines), "lines": lines}


MID = ts("2026-10-21T10:00:00Z")
EXCHANGE = _doc(_ln("Event Exchange", y=40), _ln(NAME, y=100), _ln("Owned: 140", y=125),
                _ln("Valks' Cry (+250)", y=200), _ln("80", y=200, x=400, w=40))


# -- slice 1: parser -------------------------------------------------------------------

@pytest.mark.parametrize("doc", [
    _doc(f"{NAME} x 140"),
    _doc(f"140 {NAME}"),
    EXCHANGE,
])
def test_three_line_shapes(doc):
    out = ocrinfer.currency_field(doc, RULES, MID)
    assert [(f["kind"], f["name"], f["value"]) for f in out] == [("currency_balance", "10673", 140)]
    assert out[0]["conf"] >= ocrauto.AUTO_COMMIT_MIN and out[0]["why"]


def test_grouped_amount_and_tooltip_x_glued():
    out = ocrinfer.currency_field(_doc(f"{NAME} x1,240"), RULES, MID)
    assert out[0]["value"] == 1240 and out[0]["conf"] >= 0.9


def test_unknown_currency_ignored():
    assert ocrinfer.currency_field(_doc("Tokens of Fortune x 140"), RULES, MID) == []
    assert ocrinfer.currency_field(_doc(NAME), RULES, MID) == []  # a name with no amount


def test_inactive_event_ignored():
    for when in ("2026-10-01T00:00:00Z", "2026-11-05T07:00:00Z"):
        assert ocrinfer.currency_field(_doc(f"{NAME} x 140"), RULES, ts(when)) == []


def test_name_within_edit_distance_two():
    two = ocrinfer.currency_field(_doc("Seels of Purificatlon x 140"), RULES, MID)
    assert [f["value"] for f in two] == [140] and two[0]["conf"] < 1
    assert "~" in two[0]["why"]
    assert ocrinfer.currency_field(_doc("Seels of Pvrificatlon x 140"), RULES, MID) == []


def test_number_too_far_below_is_not_read():
    doc = _doc(_ln(NAME, y=100), _ln("Owned: 140", y=190))  # 70 px gap
    assert ocrinfer.currency_field(doc, RULES, MID) == []


def test_cost_line_skipped_and_two_amounts_lower_the_confidence():
    assert ocrinfer.currency_field(_doc(f"Cost: 80 {NAME}"), RULES, MID) == []
    two = ocrinfer.currency_field(_doc(f"80 {NAME}", f"{NAME} x 140"), RULES, MID)
    assert len(two) == 1 and two[0]["conf"] < ocrauto.AUTO_COMMIT_MIN
    owned = ocrinfer.currency_field(_doc(f"80 {NAME}", f"Owned {NAME} 140"), RULES, MID)
    assert owned[0]["value"] == 140 and owned[0]["conf"] >= ocrauto.AUTO_COMMIT_MIN


# -- slices 2-3: kind wiring, precedence -----------------------------------------------

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


DATES = {"2026-10-18": 90, "2026-10-19": 30, "2026-10-20": 70}


@pytest.fixture
def env(tmp_path):
    shot_dir = tmp_path / "ScreenShot"
    shot_dir.mkdir()
    game = FakeGame(shot_dir)
    docs = {}
    clock = Clock(MID)
    store = Store(tmp_path / "store")
    hist = {"dates": dict(DATES), "marked": []}
    cur = ec.CurrencyService(store, clock=clock, history=lambda: hist, rules=RULES)
    g = grind.GrindService(store, clock=clock, presets=[])
    reader = ocr.OcrService(game, tmp_path / "ocr", runner=lambda p: docs[p.name])
    auto = ocrauto.AutoOcr(store, game, reader, g, settings=lambda: {}, clock=clock,
                           currency=cur)
    auto.on_game(None, "logged_in", MID - 86400 * 5)

    class Env:
        pass

    e = Env()
    e.__dict__.update(game=game, docs=docs, clock=clock, store=store, cur=cur, auto=auto)
    return e


def _shot(e, name, when, doc):
    e.game.add(name, when)
    e.docs[name] = doc
    e.auto.scan()
    e.auto.drain()


def _row(e):
    return e.cur.view()["events"][0]


def test_kind_registered():
    assert "currency_balance" in ocrauto.KINDS and "currency_balance" in ocrauto.FIX_KINDS


def test_acceptance_exchange_window_sets_balance_with_source(env):
    logged = _row(env)
    assert logged["earned_src"] == "log"
    _shot(env, "ex.png", MID - 7200, EXCHANGE)
    row = _row(env)
    assert row["earned"] == 140 and row["earned_src"] == "ocr"
    assert row["guaranteed"] == 140 + logged["remaining"]  # drops are inside the read
    assert row["balance_at"] == "2026-10-21T08:00:00+00:00"
    assert "140 in hand (OCR, 2 h ago)" in row["label"]
    ent = env.store.get(ec.DOMAIN)["ocr"]["10673"]
    assert ent["source"] == "ocr:ex.png" and ent["expires_at"] == R["ends"]
    assert env.auto.view()["review"] == []


def test_commit_expires_at_event_end(env):
    _shot(env, "ex.png", MID - 60, EXCHANGE)
    ent = env.store.get(ec.DOMAIN)["ocr"]["10673"]
    assert ec.active_balance(ent, dt.datetime(2026, 11, 5, 6, 59, tzinfo=UTC)) == 140
    assert ec.active_balance(ent, dt.datetime(2026, 11, 5, 7, 0, tzinfo=UTC)) is None
    env.clock.t = ts("2026-11-05T07:00:00Z")
    assert env.cur.view()["events"] == []


def test_held_when_far_below_earned(env):
    assert _row(env)["logged"] > 20
    _shot(env, "low.png", MID - 60, _doc(f"{NAME} x 20"))
    rv = env.auto.view()["review"]
    assert [(r["kind"], r["value"]) for r in rv] == [("currency_balance", 20)]
    assert "below" in rv[0]["why"]
    assert _row(env)["earned_src"] == "log"
    env.auto.review({"id": env.store.get("ocr_review")["items"][0]["id"], "action": "accept"})
    assert _row(env)["earned"] == 20 and _row(env)["earned_src"] == "ocr"


def test_newer_typed_wins_over_older_read(env):
    _shot(env, "ex.png", MID - 3600, EXCHANGE)
    env.cur.balance({"event": "10673", "value": 300})  # typed at MID, after the shot
    row = _row(env)
    assert row["earned"] == 300 and row["earned_src"] == "typed"
    assert "(typed)" in row["label"]
    assert [o["value"] for o in env.cur.typed_overrides()] == [300]


def test_newer_read_wins_over_older_typed(env):
    env.clock.t = MID - 7200
    env.cur.balance({"event": "10673", "value": 300})
    env.clock.t = MID
    _shot(env, "ex.png", MID - 60, EXCHANGE)
    row = _row(env)
    assert row["earned"] == 140 and row["earned_src"] == "ocr"
    assert env.cur.typed_overrides() == []  # the typed value is not in force


def test_older_read_never_replaces_a_newer_one(env):
    _shot(env, "new.png", MID - 60, _doc(f"{NAME} x 200"))
    _shot(env, "old.png", MID - 600, EXCHANGE)
    assert _row(env)["earned"] == 200
    assert env.auto.view()["review"] == []


def test_undo_restores_previous_read(env):
    _shot(env, "a.png", MID - 600, EXCHANGE)
    _shot(env, "b.png", MID - 60, _doc(f"{NAME} x 200"))
    commits = env.auto.view()["commits"]
    assert [c["kind"] for c in commits] == ["currency_balance", "currency_balance"]
    env.auto.undo(commits[0]["id"])
    assert _row(env)["earned"] == 140
    env.auto.undo(commits[1]["id"])
    assert _row(env)["earned_src"] == "log"


def test_fix_value_commits_at_shot_time(env):
    _shot(env, "low.png", MID - 60, _doc(f"{NAME} x 20"))
    rid = env.store.get("ocr_review")["items"][0]["id"]
    env.auto.review({"id": rid, "action": "fix", "value": 220})
    assert _row(env)["earned"] == 220


def test_set_balance_validation(env):
    for bad in (("1", 5), ("10673", -1), ("10673", True), ("10673", 10 ** 8)):
        with pytest.raises(ValueError):
            env.cur.set_balance(bad[0], bad[1], source="ocr:x.png", at=MID)
    with pytest.raises(ValueError):
        env.cur.set_balance("10673", 5, source="typed", at=MID)
    with pytest.raises(ValueError):
        env.cur.set_balance("10673", 5, source="ocr:x.png", at=ts("2026-11-06T00:00:00Z"))


def test_label_ago_forms():
    row = {"unit": "seals", "earned": 140, "earned_src": "ocr", "guaranteed": 900,
           "ends": R["ends"], "wishlist_cost": 0, "shortfall": 0,
           "balance_at": "2026-10-21T08:00:00+00:00"}
    now = dt.datetime(2026, 10, 21, 8, 0, 30, tzinfo=UTC)
    assert ec.label(row, now).startswith("Seals: 140 in hand (OCR, just now)")
    assert "(OCR, 45 min ago)" in ec.label(row, now + dt.timedelta(minutes=45))
    assert "(OCR, 2 h ago)" in ec.label(row, now + dt.timedelta(hours=2))
    assert "(OCR, 3 d ago)" in ec.label(row, now + dt.timedelta(days=3))
    assert "(OCR)" in ec.label(row)
