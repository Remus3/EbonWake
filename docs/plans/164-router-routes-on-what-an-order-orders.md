# Plan 164 - Loop: route an order on what it orders, and bound the session wait

Status: built (lane, 2026-11-01). Source: MAIN FIX N489d76.

## Problem

Plan 091's router ran the kit version word and the protected path patterns over
a note's name and full body, so a passing mention parked the whole order on the
session: MAIN's ORDER 2026-10-31-2215 (seven repo items) never ran because its
lead-in pointed at another order by kit version. A session-routed order also had
no bound: EW has few interactive sessions, so it sat on the step line (oldest
2026-10-24) and the sender heard nothing.

## Design

1. `session_paths(name, text)` in `tools/loop_inbox.py`:
   - NAME: any target pattern counts, the version word included (every fleet kit
     note carries it there).
   - BODY: the version word never counts. A protected path counts only where a
     sentence orders it changed: the nearest change verb before the mention, else
     any after it (`CLAUDE.md: add a rule`), un-negated, or a passive form
     (`CLAUDE.md must be ...`). A cited mention (`per`, `see`, `under`,
     `following`, `according to`) does not count.
   - Sentences split on `.!?;` + space, blank lines, list starts and headings, so
     a verb and a path on two wrapped lines still pair up.
   - `SESSION_TARGETS` keeps its meaning for `ordered_files` (plan 163).
2. `Tick.bound_session_wait`: a session-routed order unsettled for
   `SESSION_WAIT_S` (24 h) gets one deterministic ANSWER (no spawn) to its sender
   naming it BLOCKED and what it needs. `blocked_answer` on the queued order entry
   holds the note's name, so it is never repeated. The order stays open:
   `session-done` still produces its one real ANSWER.
   - The wait starts at the entry's new `queued_ts`; an entry queued before this
     plan falls back to the note's mtime.
   - The note counts against the daily cap. A capped or paused tick sends nothing
     and the next tick retries.
3. Backlog: routing is stateless (read from the queued note each tick), so on the
   first tick after merge a backlog order that only mentioned a target becomes an
   ordinary lane item, and one still routed and older than 24 h gets its one
   BLOCKED ANSWER.

## Acceptance

- `tests/test_loop_inbox_p164.py`: ORDER 2215's shape and this FIX note are not
  routed; a fleet kit note and an ordered edit of a protected path still are; with
  a fake clock the BLOCKED ANSWER goes once, a later `session-done` still answers
  once, a capped or halted tick retries.
- Plan 091 tests stay green (`tests/test_ew_loop.py`).

## As-built deviations

1. Decision: sentence-level detection, whole order routed; no per-item routing.
   - Alternatives: route per item and let a lane do the rest.
   - Why: plan 091 deviation 1 still holds (orders are not machine-split reliably
     and a partial lane merge produced the N94ff08 mess). A false negative now
     costs little: a lane brief forbids the path, the lane marks it BLOCKED, and
     plan 161 carries an all-BLOCKED result to the session.
   - Reverses if: orders arrive pre-split into lane and session items.
   - This supersedes plan 091 deviation 2 (any mention routes); its reversal
     trigger fired.
2. Decision: the BLOCKED note is named `-ANSWER-blocked-<stem>.md` and written
   without a spawn.
   - Alternatives: `-ANSWER-re-<stem>.md`; a sonnet-written reply.
   - Why: `handled()` reads an outbox `-re-<stem>.md` as settled, which would close
     the order and lose its real ANSWER. The content is fixed, so a spawn buys
     nothing.
   - Reverses if: `handled()` stops reading the outbox by name.
3. Decision: the ORDER 2215 test uses a reconstruction, not the note's bytes.
   - Alternatives: fail the item; read the inbox.
   - Why: this lane's permissions deny the main checkout inbox. The fixture keeps
     what MAIN reported (seven repo items, one lead-in naming kit ORDER 2200 by
     version). The byte pin is reported BLOCKED in the order section.
   - Reverses if: a session copies the real bytes into the test's constant.
4. Decision: `CLAUDE.md` at a sentence's end now matches (`(?!\w|\.\w)`, was
   `(?![\w.])`).
   - Alternatives: leave it; strip the full stop before matching.
   - Why: found by the red test: `Edit CLAUDE.md.` was a silent false negative, in
     the old router too.
   - Reverses if: never expected; `CLAUDE.md.bak` and `CLAUDE.mdx` stay excluded.
5. Decision: backlog item 3 is reported BLOCKED, not marked by this lane.
   - Alternatives: mark ids from tracked evidence alone.
   - Why: `session-done` and the records live in the main checkout, which this
     lane's permissions deny, and two of the four ids appear in no tracked file.
   - Reverses if: lanes get a main-checkout grant. A session runs the commands
     listed in the ROADMAP order section.
