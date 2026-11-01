"""Plan 164 (MAIN FIX N489d76): the session router counts what an order orders,
not what it mentions, and a session-routed order gets one BLOCKED ANSWER after
24 hours. Git-free: inbox methods are called directly on a Tick with fake deps."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ew_loop  # noqa: E402
import loop_inbox  # noqa: E402

from ew_loopkit import ROADMAP, FakeSpawn, _inbox_root, deps  # noqa: E402

sp = ew_loop.session_paths
ORDER_NAME = "2026-10-31-2215-from-MAIN-ORDER-to-EW-public-view.md"
# Reconstruction: a lane cannot read the inbox (plan 164 as-built deviation 3).
# It keeps the shape MAIN reported: seven repo items and one lead-in sentence
# pointing at the separate kit ORDER 2200 by its version number.
ORDER_2215 = """# From MAIN - ORDER to EW: public view

Channel code MAIN. TO EW. Separate from this one, ORDER 2200 ships kit v26; this
order does not depend on it. Do the work in your own tree.

1. Rewrite the README lead paragraph.
2. Add the banner alt text.
3. Back the idle deep-dive off to weekly.
4. Fix the changelog links.
5. Hide the overlay when the game loses focus.
6. Place the overlay by display ID.
7. Add the opt-in capture guard.
"""
FIX_NAME = ("2026-11-01-0825-from-MAIN-FIX-to-EW-loop-router-parks-an-order-on-a-prose-"
            "version-word-ONE-ANSWER.md")
FIX_LINES = """MAIN read your tree read-only and changed nothing. This note is written to pass
the router it reports. Plan 091's router matches anywhere in the note. Every fleet
kit note carries it. Mark it with `session-done`. Edit tools/loop_inbox.py.
"""


def test_order_2215_is_not_routed():
    assert sp(ORDER_NAME, ORDER_2215) == []


def test_this_fix_note_is_not_routed():
    assert sp(FIX_NAME, FIX_LINES) == []


def test_version_word_counts_only_in_the_name():
    assert sp("n.md", "after kit v26 lands, add a row") == []
    assert sp("n.md", "Adopt kit-v26 next week.") == []
    assert sp("2026-from-MAIN-ORDER-to-ALL-FLEET-KIT-v27.md", "ship it") == ["ops/fleet_kit/"]


def test_fleet_kit_note_and_ordered_edit_of_a_protected_path_still_route():
    assert sp("2026-FLEET-KIT-v10-ORDER.md", ORDER_2215) == ["ops/fleet_kit/"]
    assert sp("n.md", "1. Edit CLAUDE.md: add the rule.\n") == ["CLAUDE.md"]
    assert sp("n.md", "- vendor it into\n  ops/fleet_kit/ and re-pin\n") == ["ops/fleet_kit/"]
    assert sp("n.md", "Then update .claude/settings.json.") == [".claude/"]
    assert sp("n.md", "CLAUDE.md: add a rule.") == ["CLAUDE.md"]
    assert sp("n.md", "CLAUDE.md must be rewritten.") == ["CLAUDE.md"]
    assert sp("n.md", "ops/fleet_kit/MANIFEST.json needs a new pin.") == ["ops/fleet_kit/"]


def test_passing_mentions_of_protected_paths_do_not_route():
    for body in ("Read CLAUDE.md first. Add a row to the roadmap.",
                 "Do NOT commit, do NOT edit CLAUDE.md or ops/fleet_kit/.",
                 "Never edit CLAUDE.md and add a test to tests/test_x.py.",
                 "Under CLAUDE.md, fix the loop.",
                 "See ops/fleet_kit/fleet_inbox.py for classify. Fix the caller.",
                 "The hook lives in .claude/settings.json."):
        assert sp("n.md", body) == [], body


def test_routing_checks_each_target_alone():
    assert sp("n.md", "Read ops/fleet_kit/README. Edit CLAUDE.md.") == ["CLAUDE.md"]


# ---------------------------------------------------------------- the 24 h bound

KIT_NAME = "k-from-MAIN-ORDER-to-EW-kit-v10.md"
KIT_TEXT = "# From MAIN - ORDER\nvendor kit into ops/fleet_kit/\nHOP: 1\n"
T0 = 1_790_000_000.0
DAY = 24 * 3600


def world(tmp_path, results=None):
    root, inbox, outbox = _inbox_root(tmp_path, roadmap=ROADMAP)
    now = [T0]
    spawn = FakeSpawn(results or [])
    d = deps(root, spawn=spawn, clock=lambda: now[0])
    (inbox / KIT_NAME).write_text(KIT_TEXT)
    return root, inbox, outbox, spawn, d, now


def blocked_notes(outbox):
    return sorted(outbox.glob("*-ANSWER-blocked-*.md"))


def offer(d, inbox, outbox, name=KIT_NAME):
    return ew_loop.Tick(d).answer(inbox / name, outbox, {})


def test_blocked_answer_sent_once_after_24_hours(tmp_path):
    root, inbox, outbox, spawn, d, now = world(tmp_path)
    assert offer(d, inbox, outbox) is False  # queued at T0
    now[0] = T0 + DAY - 1
    assert offer(d, inbox, outbox) is False
    assert not list(outbox.iterdir())
    now[0] = T0 + DAY
    assert offer(d, inbox, outbox) is False  # still open for the session
    notes = blocked_notes(outbox)
    assert len(notes) == 1
    body = notes[0].read_text()
    oid = ew_loop.order_id(KIT_NAME)
    assert "BLOCKED" in body and oid in body and "ops/fleet_kit/" in body
    assert "session-done" in body and "HOP: 2" in body
    for later in (1, 2, 30):
        now[0] = T0 + later * DAY
        assert offer(d, inbox, outbox) is False
    assert blocked_notes(outbox) == notes and spawn.calls == []
    assert [o["id"] for o in ew_loop.session_orders(root)] == [oid]
    assert ew_loop.queued_orders(root)[0]["blocked_answer"] == notes[0].name


def test_blocked_answer_does_not_settle_the_order(tmp_path):
    root, inbox, outbox, spawn, d, now = world(
        tmp_path, [{"rc": 0, "error": None, "result": "# From EW - ANSWER\nvendored"}])
    offer(d, inbox, outbox)
    now[0] = T0 + DAY
    offer(d, inbox, outbox)
    oid = ew_loop.order_id(KIT_NAME)
    ew_loop.session_done(root, oid, "abc1234", clock=lambda: now[0])
    assert offer(d, inbox, outbox) is True
    assert len(spawn.calls) == 1 and "abc1234" in spawn.calls[0]["prompt"]
    assert len(list(outbox.glob("*-re-*.md"))) == 1 and len(blocked_notes(outbox)) == 1
    assert offer(d, inbox, outbox) is True
    assert len(spawn.calls) == 1 and len(blocked_notes(outbox)) == 1


def test_order_queued_before_plan_164_waits_from_the_note_mtime(tmp_path):
    root, inbox, outbox, spawn, d, now = world(tmp_path)
    oid = ew_loop.order_id(KIT_NAME)
    (root / ew_loop.ORDERS_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / ew_loop.ORDERS_REL).write_text(json.dumps({"orders": [
        {"id": oid, "note": KIT_NAME, "text": KIT_TEXT, "title": KIT_NAME}]}))
    os.utime(inbox / KIT_NAME, (T0 - DAY + 60, T0 - DAY + 60))
    offer(d, inbox, outbox)
    assert not blocked_notes(outbox)  # 23h59 old
    os.utime(inbox / KIT_NAME, (T0 - 3 * DAY, T0 - 3 * DAY))
    offer(d, inbox, outbox)
    notes = blocked_notes(outbox)
    assert len(notes) == 1 and "after 72 hours" in notes[0].read_text()


def test_lane_order_past_24_hours_gets_no_blocked_answer(tmp_path):
    root, inbox, outbox, spawn, d, now = world(tmp_path)
    name = "o-from-MAIN-ORDER-to-EW-work.md"
    (inbox / name).write_text("# From MAIN - ORDER\nfix the thing\n")
    offer(d, inbox, outbox, name)
    now[0] = T0 + 2 * DAY
    assert offer(d, inbox, outbox, name) is False
    assert not list(outbox.iterdir())


def test_capped_or_halted_tick_retries_the_blocked_answer(tmp_path):
    root, inbox, outbox, spawn, d, now = world(tmp_path)
    offer(d, inbox, outbox)
    now[0] = T0 + DAY
    t = ew_loop.Tick(d)
    t.cap.used = lambda: t.cap.cap
    assert t.answer(inbox / KIT_NAME, outbox, {}) is False
    assert not blocked_notes(outbox)
    assert not ew_loop.queued_orders(root)[0].get("blocked_answer")
    t = ew_loop.Tick(d)
    t.blocked = lambda: "halt"
    assert t.answer(inbox / KIT_NAME, outbox, {}) is False
    assert not blocked_notes(outbox)
    offer(d, inbox, outbox)
    assert len(blocked_notes(outbox)) == 1


def test_all_blocked_order_is_bound_too(tmp_path):
    root, inbox, outbox, spawn, d, now = world(tmp_path)
    name = "o-from-MAIN-ORDER-to-EW-work.md"
    oid = ew_loop.order_id(name)
    (inbox / name).write_text("# From MAIN - ORDER\nfix the thing\n")
    offer(d, inbox, outbox, name)
    ew_loop.Items(root).put({"id": oid, "kind": "order", "state": "merged", "commit": "c",
                             "note": name, "session_route": "all-blocked"})
    now[0] = T0 + DAY
    assert offer(d, inbox, outbox, name) is False
    notes = blocked_notes(outbox)
    assert len(notes) == 1 and loop_inbox.ALL_BLOCKED in notes[0].read_text()
