"""MAIN ORDER N3ef61f: an order ANSWER takes each item's verdict from the
merged commit's recorded per-item outcome (the order's ROADMAP section),
never from the lane's merge state; no recorded outcome = UNVERIFIED, never
DONE. Git-free: the inbox methods run on a Tick with injected deps."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ew_loop  # noqa: E402
import loop_inbox  # noqa: E402

from ew_loopkit import ROADMAP, FakeSpawn, _inbox_root, deps  # noqa: E402

NAME = "2026-10-26-0300-from-MAIN-ORDER-to-EW-U5-batched-roadmap-106-lane-move.md"
# the LLM reply copies the merge state as DONE (the 0334 misreport)
MISREPORT = "# From EW - ANSWER re x\n\nItems 1-3: DONE in aed89e4 (merged, verdict PASS).\n"


def section(oid, bullets):
    return (ROADMAP + f"\n## Order {oid} - blocked items\n\nProse naming DONE.\n\n"
            + "".join(f"- {b}\n" for b in bullets)
            + "\n## Order Nffffff - blocked items\n\n- other: DONE\n")


def merged_pass_world(tmp_path, roadmap_for):
    oid = ew_loop.order_id(NAME)
    root, inbox, outbox = _inbox_root(tmp_path, roadmap=roadmap_for(oid))
    sp = FakeSpawn([{"rc": 0, "error": None, "result": MISREPORT}])
    d = deps(root, spawn=sp)
    (inbox / NAME).write_text("# From MAIN - ORDER\nmove the lanes\n")
    assert ew_loop.Tick(d).answer(inbox / NAME, outbox, {}) is False  # queued
    ew_loop.Items(root).put({"id": oid, "kind": "order", "state": "merged",
                             "commit": "aed89e4", "verdict": "PASS", "rounds": 1,
                             "title": NAME, "note": NAME})
    return root, inbox, outbox, sp, d, oid


def answer_lines(outbox):
    notes = list(outbox.iterdir())
    assert len(notes) == 1
    text = notes[0].read_text(encoding="ascii")
    block = text.split("## Per-item outcome", 1)[1]
    return text, [ln for ln in block.splitlines() if ln.startswith("- ")]


def test_merged_pass_lane_whose_body_says_blocked_yields_blocked_lines(tmp_path):
    root, inbox, outbox, sp, d, _ = merged_pass_world(tmp_path, lambda oid: section(oid, [
        "Item 1 (HALT, move lane-0..2): BLOCKED - this run IS the lane-0 executor",
        "Item 2a (worktree_path): NOT-APPLICABLE as a code change; read back BLOCKED",
        "Item 3 (mark row 106 [x]): BLOCKED - follows item 1"]))
    assert ew_loop.Tick(d).answer(inbox / NAME, outbox, {}) is True
    text, lines = answer_lines(outbox)
    assert lines == [
        "- BLOCKED: Item 1 (HALT, move lane-0..2): BLOCKED - this run IS the lane-0 executor",
        "- NOT-APPLICABLE: Item 2a (worktree_path): NOT-APPLICABLE as a code change; "
        "read back BLOCKED",
        "- BLOCKED: Item 3 (mark row 106 [x]): BLOCKED - follows item 1"]
    assert not any(ln.startswith("- DONE") for ln in lines)
    assert "commit aed89e4" in text and "authoritative" in text
    prompt = sp.calls[0]["prompt"]
    assert "NOT item verdicts" in prompt and "BLOCKED: Item 1" in prompt
    assert "Mark each item DONE" not in prompt


def test_no_recorded_outcome_is_unverified_never_done(tmp_path):
    root, inbox, outbox, sp, d, _ = merged_pass_world(tmp_path, lambda oid: ROADMAP)
    assert ew_loop.Tick(d).answer(inbox / NAME, outbox, {}) is True
    _, lines = answer_lines(outbox)
    assert len(lines) == 1 and lines[0].startswith("- UNVERIFIED:")
    assert "UNVERIFIED, never DONE" in sp.calls[0]["prompt"]


def test_item_verdict_parser():
    v = loop_inbox.item_verdict
    assert v("- Section 1: DONE (pinned)") == "DONE"
    assert v("- Section 2: BLOCKED - needs gh, else DONE") == "BLOCKED"
    assert v("- Reply: NOT-APPLICABLE - the loop writes it") == "NOT-APPLICABLE"
    assert v("- [x] done 2026-10-23 read back") == "DONE"
    assert v("- Item 4: moved, looks fine") == "UNVERIFIED"
    assert v("- UNDONE-ish: BLOCKED") == "BLOCKED"  # no partial-word match
    oid = "Nabcdef"
    got = loop_inbox.item_outcomes(section(oid, ["a: DONE", "b: maybe"]), oid)
    assert got == [("DONE", "a: DONE"), ("UNVERIFIED", "b: maybe")]
    assert loop_inbox.item_outcomes(ROADMAP, oid) == []
