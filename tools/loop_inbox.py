"""EW loop inbox: channel-note prompts, routed orders and the Tick's inbox
pass as InboxMixin (plan 107 split of tools/ew_loop.py, which re-exports
every name here). Every side effect goes through self.d (Deps). Stdlib only."""

import datetime as _dt
import hashlib
import json
import os
import re
import time
from pathlib import Path

from loop_base import (
    CODE, DELIVERY_REL, DONE_STATES, INBOX_REL, Items, LEGACY_LEDGER_REL, MAX_ROUNDS,
    NOTE_HEAD, NOTE_MAX, NOTE_STAMP, ORDERS_REL, ROADMAP_REL, WATCH_REL, ascii_text,
    atomic_write, epoch_of,
    iso, read_json, read_jsonl, with_hop,
)
from loop_prompts import GATES

ROSTER_REL = Path("ops/fleet_roster.json")  # MAIN's fleet roster, relative to its root
ROSTER_UP = 3  # MAIN's inbox dir sits at most this many levels under its root


# ---------------------------------------------------------------- inbox helpers

def inbox_prompt(name, text, context=None):
    return ("You are the Ebonwake (EW) session answering ONE channel note. Reply with the "
            "note body only: markdown, ASCII, first line '# From EW - ANSWER re " + name
            + "'. Answer what is asked; do not change files. Never put a directory name, "
            "account id or email in the reply." + (" " + context if context else "")
            + "\n\n--- NOTE " + name + " ---\n" + text[:NOTE_MAX] + "\n--- END NOTE ---")


def order_id(name):
    return "N" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]


# plan 091: lane briefs forbid ops/fleet_kit/ and CLAUDE.md and lanes have no
# .claude/ write grant, so an ORDER changing one of them is blocked by
# construction; it goes to the interactive session instead of a lane.
_KIT_PATH = r"(?<![\w.])ops[\\/]fleet_kit\b"
_KIT_VERSION = r"\bkit[ _-]?v\d+\b"
_CLAUDE_DIR = re.compile(r"(?<![\w.])\.claude[\\/]")
_CLAUDE_MD = re.compile(r"(?<![\w.])CLAUDE\.md(?!\w|\.\w)")  # a sentence's end still counts
SESSION_TARGETS = (("ops/fleet_kit/", re.compile(_KIT_PATH + "|" + _KIT_VERSION, re.I)),
                   (".claude/", _CLAUDE_DIR),
                   ("CLAUDE.md", _CLAUDE_MD))
# Plan 164: in a note body only the paths count, and only where ordered changed
# (2026-10-31: a lead-in naming another order's kit version parked ORDER 2215).
BODY_TARGETS = (("ops/fleet_kit/", re.compile(_KIT_PATH, re.I)),
                (".claude/", _CLAUDE_DIR),
                ("CLAUDE.md", _CLAUDE_MD))
_CHANGE_VERB = re.compile(
    r"\b(?:add|adopt|amend|append|apply|bump|change|copy|create|delete|edit|embed|fix|"
    r"insert|install|merge|modify|move|patch|pin|put|remove|rename|replace|revert|"
    r"rewrite|set|update|vendor|wire|write)\b", re.I)
_NEGATED = re.compile(r"\b(?:not|don't|dont|never|without|no need to)\s+"
                      r"(?:[\w,']+\s+){0,3}$", re.I)
_CITED = re.compile(r"\b(?:per|see|cf|under|following|according to)\s+\W*$", re.I)
_PASSIVE = re.compile(r"\W*(?:\w+\W+){0,3}?(?:must be|should be|has to be|needs?|gets?)\b",
                      re.I)
_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+|\n\s*\n|\n(?=\s*(?:[-*]|\d+[.)])\s)")
_HEADING = re.compile(r"^(#.*)$", re.M)


def _ordered_in(sentence, rx):
    """True when a mention of target `rx` in this sentence is the object of an
    un-negated change verb: the nearest verb before it, else any verb after it
    ('CLAUDE.md: add a rule'), or a passive ('CLAUDE.md must be ...')."""
    for m in rx.finditer(sentence):
        before = sentence[:m.start()]
        if _CITED.search(before):
            continue
        if _PASSIVE.match(sentence, m.end()):
            return True
        verbs = list(_CHANGE_VERB.finditer(before))
        verb = verbs[-1] if verbs else _CHANGE_VERB.search(sentence, m.end())
        if verb and not _NEGATED.search(sentence[:verb.start()]):
            return True
    return False


def session_paths(name, text):
    """The protected targets an order changes, fixed order. Plan 164: the note
    NAME counts on any match (every fleet kit note carries its version there);
    the body counts only a protected path a sentence orders changed."""
    sentences = _SENTENCE_END.split(_HEADING.sub(r"\1\n", text or ""))
    hits = []
    for (target, name_rx), (_, body_rx) in zip(SESSION_TARGETS, BODY_TARGETS):
        if name_rx.search(name or "") or any(_ordered_in(s, body_rx) for s in sentences):
            hits.append(target)
    return hits


# Plan 164: a session-routed order unsettled this long gets one BLOCKED ANSWER
# naming what it needs (EW has few interactive sessions; the sender heard nothing).
SESSION_WAIT_S = 24 * 3600


def order_wait_start(order, note_path):
    """Epoch the order started waiting: its queued_ts, else (orders queued
    before plan 164) the note's mtime; None when neither is known."""
    ts = order.get("queued_ts")
    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
        return ts
    try:
        return Path(note_path).stat().st_mtime
    except OSError:
        return None


def session_wait_note(name, oid, needs, hours):
    return (f"# From EW - ANSWER re {name}: BLOCKED, waiting on a session\n\n"
            f"- BLOCKED: order {oid}, unsettled after {int(hours)} hours. It needs: "
            f"{', '.join(needs)}. A lane cannot carry that part.\n"
            "- Unblocks: an interactive EW session does the work and marks "
            "`session-done`; the loop then sends the order's ANSWER with per-item "
            "verdicts. This note is sent once per order and is not repeated.\n")


def order_prompt(order):
    att = [a for a in order.get("attachments") or [] if isinstance(a, str)]
    return ("You are an Ebonwake (EW) build lane in a detached git worktree. Read "
            "CLAUDE.md first. Carry out the channel ORDER note below in THIS tree. Do "
            "every item that needs only repo files. An item needing a password, an OAuth "
            "grant, a download, a tool outside your allow list or a physical act is left "
            "undone. A dependency bump is not a download: run `npm install` / `npm ci` "
            "with `--prefix app`, then `npm test --prefix app`, and read the alerts "
            "with `gh api repos/{owner}/{repo}/dependabot/alerts` (GET only: never "
            "-X PATCH, dismiss or close one; the alert closes when the bump lands). "
            "Change every file the note orders changed, or mark it BLOCKED / "
            "NOT-APPLICABLE by path. In a section 'Order " + order["id"] + " - blocked items' at the end "
            "of docs/plans/ROADMAP.md list EVERY item of the order, one bullet each, "
            "marked DONE, NOT-APPLICABLE or BLOCKED (one line, the reason). Do not "
            "write the ANSWER note; the loop writes it after merge. "
            + ("The note's attachment(s), part of this order, sit beside it in the "
               "inbox: " + ", ".join(att) + ". " if att else "")
            + GATES.format(task=order["id"])
            + "\n\n--- NOTE " + order["note"] + " ---\n" + order.get("text", "")[:NOTE_MAX]
            + "\n--- END NOTE ---")


# Plan 161: a note is an .md; any other file is an attachment of the .md with
# the same stem (2026-10-18: the .png of MAIN ORDER 2312 became item Na7e421).
NOTE_SUFFIX = ".md"


def is_attachment_name(name):
    return Path(name).suffix.lower() != NOTE_SUFFIX


def note_attachments(path):
    """Names of the non-.md files beside note `path` with its stem, sorted;
    dot files (in-flight copies) are never attachments."""
    path = Path(path)
    try:
        return sorted(p.name for p in path.parent.iterdir()
                      if p.is_file() and not p.name.startswith(".")
                      and p.stem == path.stem and is_attachment_name(p.name))
    except OSError:
        return []


def all_blocked(roadmap, oid):
    """Plan 161: True when ROADMAP's 'Order <oid> - blocked items' section has
    at least one bullet and every bullet is BLOCKED (none DONE /
    NOT-APPLICABLE): the lane did nothing, so the session carries it."""
    m = re.search(r"^## Order " + re.escape(oid) + r" - blocked items\s*$(.*?)(?=^## |\Z)",
                  roadmap or "", re.M | re.S)
    if not m:
        return False
    bullets = [ln for ln in m.group(1).splitlines() if re.match(r"\s*[-*] ", ln)]
    return bool(bullets) and all(
        "BLOCKED" in b and not re.search(r"\bDONE\b|NOT-APPLICABLE", b) for b in bullets)


ALL_BLOCKED = "all items BLOCKED"

# MAIN ORDER N3ef61f (2026-10-31): the 0334 ANSWER re Ne1235e called items
# 1-3 "DONE" because the answer writer read only the lane's merge state
# ("merged, verdict PASS"). An item's verdict comes from the merged commit's
# recorded per-item outcome - the bullets of its 'Order <oid> - blocked
# items' ROADMAP section - and an item with none is UNVERIFIED, never DONE.
ITEM_VERDICTS = ("DONE", "BLOCKED", "NOT-APPLICABLE")
UNVERIFIED = "UNVERIFIED"
_VERDICT_RX = re.compile(r"(?<![\w-])(DONE|BLOCKED|NOT-APPLICABLE)(?![\w-])")


def order_section(roadmap, oid):
    m = re.search(r"^## Order " + re.escape(oid) + r" - blocked items\s*$(.*?)(?=^## |\Z)",
                  roadmap or "", re.M | re.S)
    return m.group(1) if m else ""


def item_verdict(bullet):
    """The recorded verdict of one item bullet: the first DONE / BLOCKED /
    NOT-APPLICABLE token (a `[x]` box counts as DONE); none = UNVERIFIED."""
    if re.match(r"\s*[-*] \[x\]", bullet, re.I):
        return "DONE"
    m = _VERDICT_RX.search(bullet)
    return m.group(1) if m else UNVERIFIED


def item_outcomes(roadmap, oid):
    """[(verdict, item text)] for every bullet of the order's section, in order."""
    out = []
    for ln in order_section(roadmap, oid).splitlines():
        if re.match(r"\s*[-*] ", ln):
            text = re.sub(r"^\s*[-*] (\[[ xX]\] )?", "", ln).strip()
            out.append((item_verdict(ln), ascii_text(text, 300)))
    return out


def outcome_block(outcomes, commit):
    """The deterministic per-item section appended to every order ANSWER; it
    is the record and supersedes any verdict the reply text states."""
    head = (f"## Per-item outcome (recorded in commit {commit or 'none'}; this "
            "section is authoritative)")
    if not outcomes:
        return (head + "\n\n- " + UNVERIFIED + ": no per-item outcome recorded; "
                "no item is reported DONE.\n")
    return head + "\n\n" + "".join(f"- {v}: {t}\n" for v, t in outcomes)


def answer_context(rec, outcomes):
    """The inbox-prompt context of an order ANSWER: lane facts plus each
    item's recorded verdict, never the merge state as an item verdict."""
    ctx = (f"EW's loop carried this order out as lane item {rec.get('id')}: state "
           f"{rec.get('state')}, verdict {rec.get('verdict', 'none')}, "
           f"refute-rounds {rec.get('rounds', 0)}/{MAX_ROUNDS}, commit "
           f"{rec.get('commit', 'none')}. The lane's merge state and verdict are NOT "
           "item verdicts. ")
    if not outcomes:
        return ctx + ("The commit records no per-item outcome: report every item "
                      "UNVERIFIED, never DONE.")
    return ctx + ("Report each item with exactly its recorded verdict, never "
                  "upgraded; an item not listed is UNVERIFIED. Recorded: "
                  + " | ".join(f"{v}: {t}" for v, t in outcomes))

# Plan 163: the repo-relative files a note orders changed (keep-ref 9e52b0e
# passed with an empty app/ diff). A path has a slash and a file extension;
# URLs and the session-routed targets (plan 091) are never lane files.
URL_RX = re.compile(r"\S+://\S+")
PATH_RX = re.compile(r"(?<![\w./\\-])((?:[\w.-]+/)+[\w-][\w.-]*\.[A-Za-z0-9]+)(?![\w/-])")


def ordered_files(text):
    found = PATH_RX.findall(URL_RX.sub(" ", text or ""))
    return sorted({p for p in found
                   if not any(rx.search(p) for _, rx in SESSION_TARGETS)})


def blocked_paths(roadmap, oid):
    """Paths named in a BLOCKED / NOT-APPLICABLE bullet of the order's
    'Order <oid> - blocked items' ROADMAP section (plan 161 format)."""
    m = re.search(r"^## Order " + re.escape(oid) + r" - blocked items\s*$(.*?)(?=^## |\Z)",
                  roadmap or "", re.M | re.S)
    out = set()
    for ln in (m.group(1).splitlines() if m else ()):
        if re.match(r"\s*[-*] ", ln) and re.search(r"\bBLOCKED\b|NOT-APPLICABLE", ln):
            out.update(PATH_RX.findall(ln))
    return out


def missing_ordered(text, changed, roadmap, oid, exists):
    """Ordered files of this tree (`exists(path)` for the file or its parent
    directory) that are neither changed nor marked BLOCKED / NOT-APPLICABLE."""
    skip = set(changed) | blocked_paths(roadmap, oid)
    return [p for p in ordered_files(text)
            if p not in skip and (exists(p) or exists(p.rsplit("/", 1)[0]))]


def session_needs(order, rec):
    """What routes an order to the session: plan 091 protected targets, plus
    plan 161's all-BLOCKED lane result."""
    hits = session_paths(order.get("note", ""), order.get("text", ""))
    if (rec or {}).get("session_route") == "all-blocked":
        hits.append(ALL_BLOCKED)
    return hits


def queued_orders(root):
    doc = read_json(Path(root) / ORDERS_REL, {})
    orders = doc.get("orders") if isinstance(doc, dict) else None  # plan 149 TOOLS-03
    return [o for o in (orders if isinstance(orders, list) else [])
            if isinstance(o, dict) and o.get("id")]


def inbox_names(inbox):
    """Note names in inbox, oldest mtime first (FLEET item 7); dot files are
    never notes. Plan 149 TOOLS-09: a note removed while it is listed (MAIN
    moving a copy) is skipped, never a tick crash."""
    stamped = []
    for p in Path(inbox).iterdir():
        if p.name.startswith(".") or not p.is_file():
            continue
        try:
            stamped.append((p.stat().st_mtime, p.name))
        except OSError:
            continue
    return [name for _, name in sorted(stamped)]


# The kit fleet_inbox seen ledger (fleet_inbox.SEEN_REL). A note named there
# is settled: answered, ruled no-reply or acked.
SEEN_REL = Path("ops/loop/control/inbox_seen.jsonl")


def answered_in_outbox(name, outbox):
    """True when an EW ANSWER in outbox answers note `name`: its file name ends
    `-re-<full stem>.md`, OR its title line is exactly `# From EW - ANSWER re
    <name>`, OR (a batched answer) it has a `## Re <name>` heading. 2026-11-01
    fix: the kit v24 / v25 answers went out under shortened file names with
    no seen line, the stem match missed them and the 24 h bound sent false
    BLOCKED notes (Nba8669, Nb25a6f). A BLOCKED note's title carries
    `: BLOCKED` after the name, so it never matches."""
    stem = Path(name).stem
    title = f"# From {CODE} - ANSWER re {name}"
    heading = f"## Re {name}"
    for p in Path(outbox).iterdir():
        if p.name.endswith(f"-re-{stem}.md"):
            return True
        if not p.is_file() or f"-from-{CODE}-ANSWER-" not in p.name:
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        if lines and lines[0].rstrip() == title:
            return True
        if any(line.rstrip() == heading for line in lines):
            return True
    return False


def settled_notes(root):
    return {d["note"] for d in read_jsonl(Path(root) / SEEN_REL) if d.get("note")}


def order_settled(order, rec, settled):
    """2026-10-12 fix: a queued order is closed by its session_done mark OR by
    a seen-ledger line for its note (a session that answered the note by hand
    and never ran `session-done` left N9138b6 / N97fbd7 open forever)."""
    return bool((rec or {}).get("session_done")) or order.get("note") in settled


def session_orders(root):
    """Plan 091: queued orders routed to the session and not yet marked done,
    each with its "needs" targets."""
    items = Items(root)
    settled = settled_notes(root)
    out = []
    for o in queued_orders(root):
        rec = items.get(o["id"])
        hits = session_needs(o, rec)
        if hits and not order_settled(o, rec, settled):
            out.append(dict(o, needs=hits))
    return out


def roster_paths(cfg, env_roster):
    """Fleet rosters to look a code up in: loop.roster, FLEET_ROSTER, then
    (Order Nd11eb1 item 1) MAIN's own ops/fleet_roster.json, found from MAIN's
    loop.dest_inboxes row, so one known inbox resolves every code with no
    machine path in a tracked file."""
    out = [Path(p) for p in (cfg.get("roster"), env_roster) if p]
    main = cfg["dest_inboxes"].get("MAIN")
    if main:
        out += [up / ROSTER_REL for up in list(Path(main).parents)[:ROSTER_UP]]
    return out


# Order Nd11eb1 item 3 (EW-1): plan 164 tells MAIN after 24 h, the status shows it.
PARKED_WARN_S = 48 * 3600
PARKED_SHOWN = 5


def parked_items(root, inbox_dir, now):
    """What waits on an interactive session, oldest first: session-routed orders
    and items the loop will not self-accept (state adjudicate, CLAUDE.md loop
    rule 4). [{"id", "why", "age_h"}]; an unknown start is left out, never age 0."""
    rows = []
    for o in session_orders(root):
        note = Path(inbox_dir) / str(o.get("note") or "") if inbox_dir else None
        since = order_wait_start(o, note) if note else o.get("queued_ts")
        if isinstance(since, (int, float)) and not isinstance(since, bool):
            rows.append((since, o["id"], ", ".join(o["needs"])))
    for rec in Items(root).all().values():
        if rec.get("state") == "adjudicate":
            since = epoch_of(rec.get("finished") or rec.get("dispatched"))
            if since is not None:
                rows.append((since, rec.get("id"), "adjudicate"))
    return [{"id": ascii_text(i, 40), "why": ascii_text(w, 80),
             "age_h": round(max(now - s, 0) / 3600, 1)} for s, i, w in sorted(rows, key=lambda r: r[0])]


def parked_status(rows):
    """The fields beside the kit's inbox_status.json schema; {} when nothing is
    parked. A warning line only from 48 h, naming the oldest item."""
    if not rows:
        return {}
    doc = {"parked": rows[:PARKED_SHOWN], "parked_count": len(rows),
           "parked_oldest_age_h": rows[0]["age_h"]}
    if rows[0]["age_h"] * 3600 >= PARKED_WARN_S:
        doc["parked_warning"] = (f"stale session: {rows[0]['id']} parked "
                                 f"{int(rows[0]['age_h'])} h, needs {rows[0]['why']}")
    return doc


def session_done(root, oid, commit=None, clock=time.time):
    """Plan 091: the session marks a routed order done; the next tick answers
    it. None for an id that is not a queued order. A second call keeps the
    first record (idempotent)."""
    order = next((o for o in queued_orders(root) if o["id"] == oid), None)
    if order is None:
        return None
    items = Items(root)
    rec = items.get(oid) or {}
    if rec.get("session_done"):
        return rec
    rec.update(id=oid, kind="order", title=order.get("title", ""), note=order.get("note"),
               state="merged", verdict="session", session_done=True,
               commit=ascii_text(commit or "none", 80), finished=iso(clock()))
    return items.put(rec)


# Kit v11 ruling R1 + EW adjudication D3 (2026-10-08): EW's safety floors (Game
# ToS) live in prompts and code, not hooks, so triage runs bare. Reverses if a
# floor moves into a hook.
FLOORS_IN_HOOKS = False


def triage_spawn_kwargs(fi):
    """spawn() keywords for ONE triage run (kit v11+ fleet_inbox)."""
    return fi.triage_spawn_kwargs(FLOORS_IN_HOOKS)


class InboxMixin:
    """Plan 107: mixed into ew_loop.Tick. The Tick's inbox pass (b.): notes
    in, answers and orders out."""

    # -- b. inbox
    def inbox(self):
        inbox, outbox = self.cfg["inbox_dir"], self.cfg["outbox_dir"]
        if not inbox or not Path(inbox).is_dir():
            self.step("inbox unconfigured")
            return
        if not outbox:
            self.step("outbox unconfigured")
            return
        inbox, outbox = Path(inbox), Path(outbox)

        def fetch():
            return inbox_names(inbox)

        state = self.d.watch.WatchState(self.root / WATCH_REL)
        if self.dry:
            seen = set(state.seen("inbox"))
            new = [n for n in fetch() if n not in seen]
            self.step(f"inbox: {len(new)} new (dry run)")
            return
        self.redeliver(outbox)
        left = self.close_settled_work()  # kit v27: pending orders first
        if left:
            self.step(f"inbox: {len(left)} pending order(s): "
                      f"{', '.join(r.get('note') or '?' for r in left)}"[:200])

        def deliver(names):
            batch = {}  # destination -> [(note, answer text, incoming hop)]
            pending = [n for n in names if not self.answer(inbox / n, outbox, batch)]
            pending += self.send_batches(batch, outbox)
            if pending:  # left unseen: run_source re-offers them next tick
                return {"delivered": False, "detail": f"{len(pending)} pending"}
            return {"delivered": True}

        res = self.d.watch.run_source(state, "inbox", fetch, deliver,
                                      lambda s, n, d: {"delivered": True})
        outcome, detail = res["outcome"], res["detail"]
        if outcome == "deliver-failed":
            # Pending by design is not a delivery failure (2026-10-05 loop.json
            # read "deliver-failed 2 2 pending": two ORDERs awaiting lanes).
            n = int(detail.split()[0]) if detail[:1].isdigit() else -1
            failed = n - self.awaiting - self.capped - self.paused
            if n >= 0 and failed <= 0:
                outcome = "pending"
            detail = (f"pending: {self.awaiting} order(s) awaiting lane, {self.capped} "
                      f"capped, {self.paused} paused, {max(failed, 0)} failed")
        self.step(f"inbox: {outcome} {len(res['new'])} new; {detail}"[:200])

    def handled(self, name, outbox):
        """Already settled: in the kit seen ledger, or answered by a pre-v8 tick."""
        if name in self.fi.seen(self.root):
            return True
        legacy = read_jsonl(self.root / LEGACY_LEDGER_REL)  # plan 015 deviation 14e
        if not (any(d.get("note") == name for d in legacy)
                or outbox.is_dir() and answered_in_outbox(name, outbox)):
            return False
        # Backfill the kit seen ledger (2026-10-09: the 10-04/10-05 notes were
        # settled before inbox_seen.jsonl existed and were absent from it).
        path = Path(self.cfg["inbox_dir"]) / name
        head = path.read_text(encoding="utf-8", errors="replace")[:NOTE_HEAD] \
            if path.is_file() else ""
        self.fi.mark_seen(self.root, path, self.fi.classify(name, CODE, head),
                          verdict="LEGACY", clock=self.d.clock)
        self.close_settled_work()
        return True

    def close_settled_work(self):
        """Kit v27 (KIT-INBOX-PENDING-ORDER): mark_seen of an ORDER / FIX /
        RULING also queues it in inbox_work.jsonl. EW works orders through its
        own queue (queue_order) and answers them before the note is marked
        seen, so a kit row whose note the seen ledger already settled (ANSWER
        or LEGACY) is closed here with mark_work_done; the rest stay pending
        (inbox_pending_orders.json) and are reported first."""
        rows = self.fi.pending_work(self.root)
        if not rows:
            return []
        settled = {d["note"] for d in read_jsonl(self.root / SEEN_REL)
                   if d.get("note") and d.get("verdict") in ("ANSWER", "LEGACY")}
        left = []
        for row in rows:
            if row.get("note") in settled:
                self.fi.mark_work_done(self.root, row, outcome="answered",
                                       clock=self.d.clock)
            else:
                left.append(row)
        return left

    def answer(self, path, outbox, batch):
        """True when the note needs nothing more (handled now or before); False =
        pending (re-offered next tick). FLEET item 14: skip / ack are ledger
        lines, ORDER / FIX / RULING escalate, anything else is triaged once."""
        name = path.name
        if self.handled(name, outbox):
            return True
        if is_attachment_name(name):  # plan 161: never a note of its own
            note = path.with_suffix(NOTE_SUFFIX).name
            owned = (path.parent / note).is_file()
            dec = self.fi.classify(name, CODE, "")
            self.fi.mark_seen(self.root, path, dec, clock=self.d.clock,
                              verdict="ATTACHMENT" if owned else "ORPHAN-ATTACHMENT")
            self.step(f"inbox attachment of {note if owned else 'no note'}: {name}"[:200])
            return True
        text = path.read_text(encoding="utf-8", errors="replace")
        head = text[:NOTE_HEAD]
        dec = self.fi.classify(name, CODE, head)
        skip = self.d.should_skip(name, CODE, head)
        # classify() decides escalation (class ORDER / FIX / RULING by the
        # note's own sender-class token); a filename that merely QUOTES an
        # order's name (an ACK or ANSWER re- it) is never escalated.
        if dec.action == self.fi.WORK:
            return self.answer_order(name, text, dec, outbox, batch)
        if skip or dec.action in (self.fi.SKIP, self.fi.ACK):
            self.fi.mark_seen(self.root, name, dec, clock=self.d.clock)
            self.step(f"inbox {dec.action} ({skip or dec.reason}): {name}")
            return True
        to = dec.sender or "MAIN"
        if to not in batch and self.cap.used() + len(batch) >= self.cap.cap:
            self.capped += 1
            self.step(f"inbox: daily note cap {self.cap.cap} reached")
            return False
        if self.blocked():
            self.paused += 1
            return False
        line = self.spawn(self.fi.triage_prompt(name, text[:NOTE_MAX]), note=name,
                          writes_code=False, kind="triage", **triage_spawn_kwargs(self.fi))
        if not line or line.get("rc") != 0 or line.get("result") is None:
            return False
        verdict, body = self.fi.parse_verdict(ascii_text(line["result"]))
        if verdict != "ANSWER":
            self.fi.mark_seen(self.root, name, dec, verdict=verdict, clock=self.d.clock)
            self.step(f"inbox triage {verdict} (ledger, no note): {name}")
            return True
        batch.setdefault(to, []).append((name, body, dec))
        return True

    def send_batches(self, batch, outbox):
        """ONE note per destination (kit batch_note); returns notes left pending."""
        pending = []
        stamp = _dt.datetime.fromtimestamp(self.d.clock()).strftime(NOTE_STAMP)
        for to, parts in batch.items():
            hop_n = self.fi.next_hop(max(dec.hop for _, _, dec in parts))
            fname, body, names = self.fi.batch_note(CODE, to, [(n, b) for n, b, _ in parts],
                                                    hop_n=hop_n, stamp=stamp)
            if not self.cap.allow("ANSWER"):
                self.capped += len(names)
                pending += names
                continue
            if not self.write_note(outbox / fname, body):
                pending += names
                continue
            self.cap.record(fname, "ANSWER", to, parts=len(parts))
            for n, _, dec in parts:
                self.fi.mark_seen(self.root, n, dec, verdict="ANSWER", clock=self.d.clock)
            n_ok = int(self.deliver_note(outbox / fname, to))
            self.step(f"inbox answered: {', '.join(names)} -> {to} "
                      f"({n_ok}/1 reached)"[:200])
        return pending

    # -- plan 093: destination copies (FLEET-COMMON 7: re-hash, N/M reached)
    def dest_inbox(self, to):
        """The destination tree's inbox dir for code `to`, or None: config
        loop.dest_inboxes first, then the first fleet roster (roster_paths)
        naming it: its inbox, else its root/moon_sync_inbox."""
        to = str(to or "").upper()
        if self.cfg["dest_inboxes"].get(to):
            return Path(self.cfg["dest_inboxes"][to])
        for roster in roster_paths(self.cfg, self.d.roster_path):
            doc = read_json(roster, {})
            repos = doc.get("repos") if isinstance(doc, dict) else None  # plan 149 TOOLS-03
            for r in repos if isinstance(repos, list) else []:
                if isinstance(r, dict) and str(r.get("code", "")).upper() == to:
                    if r.get("inbox"):
                        return Path(r["inbox"])
                    if r.get("root"):
                        return Path(r["root"]) / INBOX_REL
        return None

    def deliver_note(self, src, to, record_failure=True):
        """Byte-copy an outbox note into `to`'s inbox, re-hash the copy against
        the outbox copy and append a delivery ledger line. True = reached.
        An existing copy with the same bytes counts as reached; one with other
        bytes is never overwritten."""
        src = Path(src)
        data = src.read_bytes()
        want = hashlib.sha256(data).hexdigest()
        inbox = self.dest_inbox(to)
        dest, reached, detail = None, False, ""
        own = Path(self.cfg["inbox_dir"]).resolve() if self.cfg["inbox_dir"] else None
        if inbox is None:
            detail = f"no inbox known for {to}"
        elif not inbox.is_dir():
            detail = "destination inbox missing"
        elif own is not None and inbox.resolve() == own:
            detail = "destination is EW's own inbox"
        else:
            dest = inbox / src.name
            try:
                if not dest.exists():
                    tmp = inbox / f".{src.name}.{os.getpid()}.tmp"  # dot: never scanned
                    tmp.write_bytes(data)
                    tmp.replace(dest)
                got = hashlib.sha256(dest.read_bytes()).hexdigest()
                reached = got == want
                detail = "" if reached else "destination copy hash differs"
            except OSError as exc:
                detail = ascii_text(f"copy failed: {exc}", 200)
        if reached or record_failure:
            line = {"ts": iso(self.d.clock()), "note": src.name, "to": to,
                    "sha256": want, "reached": reached, "count": f"{int(reached)}/1"}
            if dest is not None:
                line["dest_name"] = dest.name
            if detail:
                line["detail"] = detail
            path = self.root / DELIVERY_REL
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="ascii", newline="\n") as fh:
                fh.write(json.dumps(line, sort_keys=True) + "\n")
        if not reached:
            self.step(f"delivery {src.name} -> {to}: {detail}"[:200])
        return reached

    def redeliver(self, outbox):
        """Retry every outbox note whose latest ledger line is not reached
        (idempotent: a reached note is never copied again)."""
        last = {}
        for line in read_jsonl(self.root / DELIVERY_REL):
            if line.get("note"):
                last[line["note"]] = line
        todo = [d for d in last.values() if not d.get("reached")
                and (outbox / d["note"]).is_file()]
        if not todo:
            return
        ok = sum(self.deliver_note(outbox / d["note"], d.get("to"), record_failure=False)
                 for d in todo)
        self.step(f"inbox: redelivered {ok}/{len(todo)} reached")

    def write_note(self, dest, body):
        body = ascii_text(body).rstrip("\n") + "\n"
        atomic_write(dest, body)
        return hashlib.sha256(dest.read_bytes()).hexdigest() == \
            hashlib.sha256(body.encode("ascii")).hexdigest()

    def answer_order(self, name, text, dec, outbox, batch):
        """An escalated ORDER / FIX / RULING: queued as a lane item, answered
        (one note, HOP incoming + 1, counted by OutboundCap) once it is done."""
        oid = order_id(name)
        rec = self.items.get(oid)
        # plan 091: a session-routed order closes only on the session's mark
        done = (bool(rec) and bool(rec.get("session_done"))) \
            if session_needs({"note": name, "text": text}, rec) \
            else bool(rec) and rec.get("state") in DONE_STATES + ("adjudicate",)
        roadmap = self.root / ROADMAP_REL
        if done and not rec.get("session_done") and roadmap.is_file() and all_blocked(
                roadmap.read_text(encoding="utf-8", errors="replace"), oid):
            # plan 161: the lane did nothing (every item BLOCKED, 2319 re
            # Nc266c6); the session carries it, then the loop answers
            self.items.put(dict(rec, session_route="all-blocked"))
            self.step(f"inbox: order {oid} {ALL_BLOCKED} -> session")
            done = False
        if not done:
            self.queue_order(oid, name, text,
                             note_attachments(Path(self.cfg["inbox_dir"]) / name))
            self.bound_session_wait(oid, name, dec, outbox, batch)
            self.awaiting += 1
            return False  # answered after the lane item is done
        outcomes = item_outcomes(roadmap.read_text(encoding="utf-8", errors="replace")
                                 if roadmap.is_file() else "", oid)
        context = answer_context(dict(rec, id=oid), outcomes)
        if self.cap.used() + len(batch) >= self.cap.cap:  # batches hold their slots
            self.capped += 1
            self.step(f"inbox: daily note cap {self.cap.cap} reached")
            return False
        if self.blocked():
            self.paused += 1
            return False
        line = self.spawn(inbox_prompt(name, text, context), note=name, writes_code=False,
                          **self.route("inbox", name), timeout=1800,
                          kind="inbox")
        reply = (line or {}).get("result")
        if not line or line.get("rc") != 0 or not reply:
            return False
        stamp = _dt.datetime.fromtimestamp(self.d.clock()).strftime(NOTE_STAMP)
        dest = outbox / f"{stamp}-from-{CODE}-ANSWER-re-{Path(name).stem}.md"
        reply = (ascii_text(reply).rstrip("\n") + "\n\n"
                 + outcome_block(outcomes, rec.get("commit")))
        if not self.write_note(dest, with_hop(reply, self.fi.next_hop(dec.hop))):
            return False
        to = dec.sender or "MAIN"
        self.cap.record(dest.name, "ANSWER", to)
        self.fi.mark_seen(self.root, name, dec, verdict="ANSWER", clock=self.d.clock)
        n_ok = int(self.deliver_note(dest, to))
        self.step(f"inbox answered: {name} -> {to} ({n_ok}/1 reached)"[:200])
        return True

    def bound_session_wait(self, oid, name, dec, outbox, batch):
        """Plan 164: one BLOCKED ANSWER (no spawn) for a session-routed order
        unsettled after SESSION_WAIT_S. The order stays open for the session;
        its name has no -re-<stem> and its title ends `: BLOCKED`, so handled()
        does not read it as settled.
        A capped or paused tick sends nothing and is retried next tick."""
        orders = self.orders()
        order = next((o for o in orders if o["id"] == oid), None)
        if order is None or order.get("blocked_answer"):
            return
        needs = session_needs(order, self.items.get(oid))
        since = order_wait_start(order, Path(self.cfg["inbox_dir"]) / name)
        now = self.d.clock()
        if not needs or since is None or now - since < SESSION_WAIT_S:
            return
        if self.blocked():
            return
        if self.cap.used() + len(batch) >= self.cap.cap:
            self.step(f"inbox: daily note cap {self.cap.cap} reached")
            return
        stamp = _dt.datetime.fromtimestamp(now).strftime(NOTE_STAMP)
        dest = outbox / f"{stamp}-from-{CODE}-ANSWER-blocked-{Path(name).stem}.md"
        body = session_wait_note(name, oid, needs, (now - since) // 3600)
        if not self.write_note(dest, with_hop(body, self.fi.next_hop(dec.hop))):
            return
        order["blocked_answer"] = dest.name
        atomic_write(self.root / ORDERS_REL, json.dumps({"orders": orders}, indent=1))
        to = dec.sender or "MAIN"
        self.cap.record(dest.name, "ANSWER", to)
        n_ok = int(self.deliver_note(dest, to))
        self.step(f"inbox: order {oid} BLOCKED answer -> {to} ({n_ok}/1 reached)"[:200])

    def orders(self):
        return queued_orders(self.root)

    def queue_order(self, oid, name, text, attachments=()):
        if self.dry:
            return
        orders = self.orders()
        old = next((o for o in orders if o["id"] == oid), None)
        if old is not None:
            # plan 161: an attachment landing after its note joins the order
            if attachments and list(attachments) != old.get("attachments", []) \
                    and not self.items.get(oid):
                old["attachments"] = list(attachments)
                atomic_write(self.root / ORDERS_REL, json.dumps({"orders": orders}, indent=1))
            return
        entry = {"id": oid, "note": name, "text": text, "title": ascii_text(name, 120),
                 "queued_ts": self.d.clock()}
        if attachments:
            entry["attachments"] = list(attachments)
        atomic_write(self.root / ORDERS_REL, json.dumps({"orders": orders + [entry]},
                                                        indent=1))
        self.step(f"inbox escalated: {name} -> lane item {oid}")
