# Plan 161 - Loop inbox: attachments belong to their note; an all-BLOCKED order goes to the session

Status: built (lane p161-build). Code: `tools/loop_inbox.py`, `tools/ew_loop.py`
(work_list). Tests: `tests/test_loop_inbox_p161.py`.

## Why

1. 2026-10-18: MAIN ORDER 2312 arrived as `<stem>.md` plus `<stem>.png` (a
   screenshot). The inbox pass treated every file as a note: the `.png`
   classified as ORDER from its filename, became lane item Na7e421, and after
   merge the loop sent a 2349 ANSWER asking MAIN to resend the order. Session
   39 retracted that ANSWER.
2. 2026-10-18: ORDER 2243 (lane item Nc266c6) needed `gh` for every item. The
   lane could do nothing, listed every item BLOCKED, and the loop still
   auto-sent a TERMINAL ANSWER after merge (2319) that carried no work.

## Rules

A. ATTACHMENT. In the inbox, a file whose suffix is not `.md` is never a note.
   When an `.md` with the same stem sits beside it, it is that note's
   attachment: the note's queued order records it (`"attachments": [names]`),
   the lane prompt names it, and the attachment itself gets one seen-ledger
   line (verdict `ATTACHMENT`) and no item, triage spawn or note. A non-`.md`
   file with no `.md` sibling gets one ledger line (verdict
   `ORPHAN-ATTACHMENT`), never an item; if its note arrives later the note
   picks it up by stem.
B. ALL BLOCKED. The order lane prompt now asks for EVERY item of the order,
   one bullet each, marked DONE, NOT-APPLICABLE or BLOCKED (reason), in the
   section `## Order <id> - blocked items` of `docs/plans/ROADMAP.md`. After
   the lane item is done, when that section has at least one bullet and every
   bullet is BLOCKED (none DONE / NOT-APPLICABLE), the loop does NOT answer:
   the item record gets `session_route: "all-blocked"`, the order shows in the
   session checklist (`session: needs all items BLOCKED`) and in
   `ew_loop.py session`, and it is answered only after the session's
   `session-done` mark, exactly like a plan 091 session order.

## Tests (TDD)

- an `.md` + same-stem `.png`: one order queued (for the `.md`), the `.png`
  ledgered `ATTACHMENT`, the order lists the `.png`, the prompt names it.
- an orphan `.png`: ledgered `ORPHAN-ATTACHMENT`, no order, no spawn.
- `all_blocked()` parser: all-BLOCKED true; any DONE / NOT-APPLICABLE false;
  missing / empty section false; other order's section ignored.
- a merged order whose section is all BLOCKED: no inbox spawn, no note,
  `session_route` recorded, listed by `session_orders`; after `session_done`
  it is answered once.
- a merged order with a DONE bullet is answered as before.

## As-built deviations

1. Progress file. Decision: no `ops/loop/control/progress/p161-build.json`
   was written. Alternatives: Write tool, kit `write_progress` via python.
   Why: both writes to the main checkout were denied by this run's
   permissions (same as Neba23f / Nc266c6). Reverses if: lane runs get a
   write grant on the main checkout's progress dir.
2. Plan doc. Decision: this doc was authored by the build lane from the task
   brief; no `docs/plans/161-*.md` existed in the lane's tree. Alternatives:
   wait for the doc. Why: the brief fully states both rules. Reverses if: a
   MAIN-side plan 161 doc says otherwise (merge keeps the stricter rule).
3. All-BLOCKED signal. Decision: parse the ROADMAP blocked-items section,
   with the lane prompt changed to list DONE items too. Alternatives: the
   merged commit's changed-file list (needs git in the inbox pass, and a
   ROADMAP-only diff also fits a docs-only order); an explicit
   `ALL ITEMS BLOCKED` marker line (relies on the lane remembering a magic
   line). Why: the section already exists and is lane-written; asking for one
   line per item makes "every bullet BLOCKED" mean "nothing done". An order
   lane dispatched under the old prompt that did real work and listed only
   its blocked items would route to the session instead of auto-answering;
   that is the safe direction. Reverses if: lanes start writing DONE lines
   elsewhere, or a session finds a done order mis-routed.
4. Fast tier. Decision: `tools/ew_tests.py fast` hit the 10 m tool timeout
   with no output (suite-gate slot wait or the gate refusing a tree with
   uncommitted edits); instead the inbox-adjacent files ran targeted and
   green: test_ew_loop (not slow, git included), test_loop_split,
   test_tools_hardening_p149, test_ew_loop_routes, test_loop_inbox_p161,
   test_ascii_lf (181 passed). Alternatives: retry the gate. Why: the loop
   runs the authoritative whole-suite ci gates on this tree anyway.
   Reverses if: the loop's ci gate goes red on this tree.
5. Attachment that lands AFTER its note was queued joins the queued order
   (`attachments` updated) only while no lane item exists for it yet; once a
   lane ran, the attachment is ledgered only. Why: never rewrite a running
   item's prompt. Reverses if: a late attachment is found to matter.
