"""2026-11-01 false BLOCKED notes (Nba8669, Nb25a6f, both retracted): the kit
v24 / v25 answers went out under SHORTENED names
(`...-ANSWER-re-<stamp>-from-MAIN-ORDER-to-ALL-SEVEN-FLEET-KIT-v24-ONE-ANSWER.md`)
and wrote no seen line, so handled() - which matched only `-re-<full stem>.md`
- read a finished order as unsettled and the 24 h bound sent BLOCKED. An
outbox note answers a note when its title line (or a batched `## Re` heading)
names the note in full, whatever the answer's own file name."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ew_loop  # noqa: E402

from ew_loopkit import ROADMAP, FakeSpawn, _inbox_root, deps  # noqa: E402

KIT_NAME = ("2026-10-26-0315-from-MAIN-ORDER-to-ALL-SEVEN-FLEET-KIT-v24-cumulative-"
            "lanes-race-claims-cwd-sidecar-path-vw-chart-no-width-art-ONE-ANSWER.md")
SHORT = ("2026-10-26-0425-from-EW-ANSWER-re-2026-10-26-0315-from-MAIN-ORDER-to-"
         "ALL-SEVEN-FLEET-KIT-v24-ONE-ANSWER.md")
KIT_TEXT = "# From MAIN - ORDER\nvendor kit into ops/fleet_kit/\nHOP: 1\n"
T0 = 1_790_000_000.0
DAY = 24 * 3600


def world(tmp_path):
    root, inbox, outbox = _inbox_root(tmp_path, roadmap=ROADMAP)
    now = [T0]
    spawn = FakeSpawn([])
    d = deps(root, spawn=spawn, clock=lambda: now[0])
    (inbox / KIT_NAME).write_text(KIT_TEXT)
    return root, inbox, outbox, spawn, d, now


def offer(d, inbox, outbox):
    return ew_loop.Tick(d).answer(inbox / KIT_NAME, outbox, {})


def seen(root):
    return ew_loop.settled_notes(root)


def test_shortened_answer_name_with_full_title_is_handled(tmp_path):
    root, inbox, outbox, spawn, d, now = world(tmp_path)
    (outbox / SHORT).write_text(f"# From EW - ANSWER re {KIT_NAME}\nHOP: 2\n\nDONE.\n")
    now[0] = T0 + 6 * DAY
    assert offer(d, inbox, outbox) is True
    assert not list(outbox.glob("*-ANSWER-blocked-*.md")) and spawn.calls == []
    assert KIT_NAME in seen(root)  # backfilled, so the next tick is a ledger hit


def test_batched_answer_heading_counts(tmp_path):
    root, inbox, outbox, spawn, d, now = world(tmp_path)
    (outbox / "2026-11-01-1755-from-EW-ANSWER-to-MAIN-batched-2-answers.md").write_text(
        "# From EW - ANSWER to MAIN: 2 batched answers\n\nHOP: 2\n\n"
        f"## Re other-note.md\n\nDONE.\n\n## Re {KIT_NAME}\n\nDONE.\n")
    assert offer(d, inbox, outbox) is True
    assert KIT_NAME in seen(root)


def test_blocked_note_and_passing_mentions_do_not_settle(tmp_path):
    root, inbox, outbox, spawn, d, now = world(tmp_path)
    (outbox / "x-from-EW-ANSWER-blocked-y.md").write_text(
        f"# From EW - ANSWER re {KIT_NAME}: BLOCKED, waiting on a session\n")
    (outbox / "z-from-EW-ANSWER-re-other.md").write_text(
        f"# From EW - ANSWER re other.md\n\nSee {KIT_NAME} too.\n## Re {KIT_NAME}x\n")
    (outbox / "w-from-EW-ANSWER-re-prefix.md").write_text(
        f"# From EW - ANSWER re {KIT_NAME[:-3]}\n")
    assert offer(d, inbox, outbox) is False
    assert KIT_NAME not in seen(root)


def test_full_stem_file_name_still_counts(tmp_path):
    root, inbox, outbox, spawn, d, now = world(tmp_path)
    (outbox / f"s-from-EW-ANSWER-re-{Path(KIT_NAME).stem}.md").write_text("no title\n")
    assert offer(d, inbox, outbox) is True
