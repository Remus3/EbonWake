"""Plan 161: a note's attachment (same stem, not .md) is part of that note,
never its own order item or ANSWER; an order lane that ends with every item
BLOCKED routes to the session instead of auto-answering. Git-free: the inbox
methods are called directly on a Tick with injected deps."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ew_loop  # noqa: E402
import loop_inbox  # noqa: E402

from ew_loopkit import ROADMAP, FakeSpawn, _inbox_root, deps  # noqa: E402

STEM = "2026-10-18-2312-from-MAIN-ORDER-to-EW-OPERATOR-MARKED-FIXES"
ORDER_TEXT = "# From MAIN - ORDER\nfix the two marked items, see the screenshot\n"


def seen_lines(root):
    path = root / "ops/loop/control/inbox_seen.jsonl"
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def world(tmp_path, roadmap=ROADMAP, results=None):
    root, inbox, outbox = _inbox_root(tmp_path, roadmap=roadmap)
    sp = FakeSpawn(results or [])
    d = deps(root, spawn=sp)
    return root, inbox, outbox, sp, d


# ---------------------------------------------------------------- A. attachments

def test_attachment_beside_its_note_is_part_of_that_order(tmp_path):
    root, inbox, outbox, sp, d = world(tmp_path)
    (inbox / f"{STEM}.md").write_text(ORDER_TEXT)
    (inbox / f"{STEM}.png").write_bytes(b"\x89PNG\r\n")
    t = ew_loop.Tick(d)
    batch = {}
    assert t.answer(inbox / f"{STEM}.png", outbox, batch) is True
    assert t.answer(inbox / f"{STEM}.md", outbox, batch) is False  # awaiting lane
    orders = ew_loop.queued_orders(root)
    assert [o["note"] for o in orders] == [f"{STEM}.md"]
    assert orders[0]["attachments"] == [f"{STEM}.png"]
    assert f"{STEM}.png" in ew_loop.order_prompt(orders[0])
    lines = [x for x in seen_lines(root) if x["note"] == f"{STEM}.png"]
    assert len(lines) == 1 and lines[0]["verdict"] == "ATTACHMENT"
    assert sp.calls == [] and batch == {} and not list(outbox.iterdir())


def test_attachment_is_never_queued_even_when_offered_first_alone(tmp_path):
    root, inbox, outbox, sp, d = world(tmp_path)
    (inbox / f"{STEM}.png").write_bytes(b"\x89PNG\r\n")
    t = ew_loop.Tick(d)
    assert t.answer(inbox / f"{STEM}.png", outbox, {}) is True
    assert ew_loop.queued_orders(root) == [] and sp.calls == []
    lines = [x for x in seen_lines(root) if x["note"] == f"{STEM}.png"]
    assert len(lines) == 1 and lines[0]["verdict"] == "ORPHAN-ATTACHMENT"
    # the note arriving later still picks its attachment up by stem
    (inbox / f"{STEM}.md").write_text(ORDER_TEXT)
    assert t.answer(inbox / f"{STEM}.md", outbox, {}) is False
    assert ew_loop.queued_orders(root)[0]["attachments"] == [f"{STEM}.png"]


def test_note_attachments_lists_same_stem_non_md_files_only(tmp_path):
    inbox = tmp_path / "in"
    inbox.mkdir()
    for n in (f"{STEM}.md", f"{STEM}.png", f"{STEM}.txt", f"{STEM}-2.png",
              f".{STEM}.png.tmp", "other.png"):
        (inbox / n).write_text("x")
    assert loop_inbox.note_attachments(inbox / f"{STEM}.md") == [f"{STEM}.png",
                                                                  f"{STEM}.txt"]
    assert loop_inbox.is_attachment_name(f"{STEM}.png")
    assert not loop_inbox.is_attachment_name(f"{STEM}.md")
    assert not loop_inbox.is_attachment_name(f"{STEM}.MD")


def test_full_tick_inbox_pass_queues_one_order_for_note_plus_png(tmp_path):
    root, inbox, outbox, sp, d = world(tmp_path)
    t = ew_loop.Tick(d)
    t.inbox()  # baseline
    (inbox / f"{STEM}.md").write_text(ORDER_TEXT)
    (inbox / f"{STEM}.png").write_bytes(b"\x89PNG\r\n")
    t = ew_loop.Tick(d)
    t.inbox()
    assert [o["note"] for o in ew_loop.queued_orders(root)] == [f"{STEM}.md"]
    assert sp.calls == [] and not list(outbox.iterdir())


# ---------------------------------------------------------------- B. all BLOCKED

def blocked_roadmap(oid, bullets):
    return (ROADMAP + f"\n## Order {oid} - blocked items\n\nSome prose.\n\n"
            + "".join(f"- {b}\n" for b in bullets)
            + "\n## Order Nffffff - blocked items\n\n- x: DONE\n")


def test_all_blocked_parser():
    oid = "Nc266c6"
    yes = blocked_roadmap(oid, ["Section 1 alerts read: BLOCKED - `gh` not allowed.",
                                "Section 2 fixes: BLOCKED - depends on section 1."])
    assert loop_inbox.all_blocked(yes, oid) is True
    part = blocked_roadmap(oid, ["Section 1: DONE (pinned actions).",
                                 "Section 2: BLOCKED - needs gh."])
    assert loop_inbox.all_blocked(part, oid) is False
    na = blocked_roadmap(oid, ["Section 1: NOT-APPLICABLE - no alerts.",
                               "Section 2: BLOCKED - needs gh."])
    assert loop_inbox.all_blocked(na, oid) is False
    assert loop_inbox.all_blocked(ROADMAP, oid) is False  # no section
    assert loop_inbox.all_blocked(blocked_roadmap(oid, []), oid) is False  # no bullets
    # only the named order's section counts
    other = blocked_roadmap("Naaaaaa", ["a: BLOCKED - x"])
    assert loop_inbox.all_blocked(other, "Nffffff") is False


NAME = "2026-10-18-2243-from-MAIN-ORDER-to-ALL-SIX-GITHUB-SECURITY-FINDINGS.md"


def merged_order_world(tmp_path, bullets):
    oid = ew_loop.order_id(NAME)
    root, inbox, outbox, sp, d = world(
        tmp_path, roadmap=blocked_roadmap(oid, bullets),
        results=[{"rc": 0, "error": None, "result": "# From EW - ANSWER\ndone"}])
    (inbox / NAME).write_text("# From MAIN - ORDER\nread the alerts with gh\n")
    t = ew_loop.Tick(d)
    assert t.answer(inbox / NAME, outbox, {}) is False  # queued
    ew_loop.Items(root).put({"id": oid, "kind": "order", "state": "merged",
                             "commit": "456a865", "verdict": "PASS", "rounds": 0,
                             "title": NAME, "note": NAME})
    return root, inbox, outbox, sp, d, oid


def test_all_blocked_order_routes_to_session_instead_of_answering(tmp_path):
    root, inbox, outbox, sp, d, oid = merged_order_world(
        tmp_path, ["alerts read: BLOCKED - gh outside allow list",
                   "commit, push: BLOCKED by this lane's own order"])
    t = ew_loop.Tick(d)
    assert t.answer(inbox / NAME, outbox, {}) is False
    assert sp.calls == [] and not list(outbox.iterdir())
    assert ew_loop.Items(root).get(oid)["session_route"] == "all-blocked"
    assert any("all items BLOCKED" in s for s in t.log)
    routed = ew_loop.session_orders(root)
    assert [o["id"] for o in routed] == [oid]
    assert routed[0]["needs"] == ["all items BLOCKED"]
    _, work, skipped = ew_loop.Tick(d).work_list()
    assert oid not in [w["id"] for w in work]
    hit = [h for h in skipped if h["id"] == oid]
    assert hit and hit[0]["skip"] == "session"
    assert hit[0]["reason"] == "session: needs all items BLOCKED"
    # a re-run is a no-op: still no spawn, no note
    assert ew_loop.Tick(d).answer(inbox / NAME, outbox, {}) is False
    assert sp.calls == []
    # the session carries it out and marks it; the next pass answers once
    ew_loop.session_done(root, oid, "abc1234", clock=lambda: 1_790_000_000.0)
    assert ew_loop.session_orders(root) == []
    assert ew_loop.Tick(d).answer(inbox / NAME, outbox, {}) is True
    assert len(sp.calls) == 1 and "abc1234" in sp.calls[0]["prompt"]
    assert len(list(outbox.iterdir())) == 1
    assert ew_loop.Tick(d).answer(inbox / NAME, outbox, {}) is True
    assert len(sp.calls) == 1


def test_order_with_a_done_item_is_answered_as_before(tmp_path):
    root, inbox, outbox, sp, d, oid = merged_order_world(
        tmp_path, ["pin actions: DONE", "alerts read: BLOCKED - gh outside allow list"])
    assert ew_loop.Tick(d).answer(inbox / NAME, outbox, {}) is True
    assert len(sp.calls) == 1 and len(list(outbox.iterdir())) == 1
    assert "session_route" not in ew_loop.Items(root).get(oid)
    assert ew_loop.session_orders(root) == []


def test_order_prompt_asks_for_every_item_with_its_state():
    p = ew_loop.order_prompt({"id": "N123456", "note": "n.md", "text": "do x"})
    assert "EVERY item" in p and "DONE" in p and "NOT-APPLICABLE" in p
    assert "Order N123456 - blocked items" in p
