# Plan 165 - Fleet Insights W44 batch

Status: code built (lane, 2026-11-01); session half open, rows 165-167. Source: MAIN
ORDER Nd11eb1. Per-item verdicts: ROADMAP section `Order Nd11eb1 - blocked items`.

## Built

1. Delivery: `roster_paths` in `tools/loop_inbox.py` looks a code up in
   `loop.roster`, `FLEET_ROSTER`, then `ops/fleet_roster.json` at MAIN's root, found
   from the MAIN row of `loop.dest_inboxes`.
2. Runs cap: `usage_ledger.gate_budget` wraps kit `tree_budget`; `last_reset` reads
   the kit's `headless_budget.reset-<date>.json`, and a usage row started at or
   before that stamp does not count. `python tools/usage_ledger.py gate` reads back
   the count and cap.
3. Stale session: `parked_items` / `parked_status` in `tools/loop_inbox.py`;
   `Tick.status_parked` adds `parked`, `parked_count`, `parked_oldest_age_h` and, from
   48 h, `parked_warning` to `inbox_status.json`.
4. Overlay QA: the three checks are in `docs/handoff-ledger.txt`.
5. Spend: `python tools/usage_ledger.py spend` prints one line.
6. Samples: `tools/lane_samples.py`. State, ledger, cap and samples all sit under
   `<sidecar>/EW/Scratch/lane-samples/`. `python tools/lane_samples.py status` reads it.
7. FLEET-9: a test fails any raw timing assert in `tests/test_*.py`.

## Session half (row 165)

Paste into the hand-off's OPERATOR QA bullet:

    AND QA overlay change 88d99c0: hide off-focus (alt-tab hides, focus shows), second
    display (shows there, follows a reorder, falls back to primary when unplugged),
    capture guard opt-in (overlay.content_protection true = absent from a capture).

Add to the /done command, hand-off section, the line printed by
`python tools/usage_ledger.py spend` as one hand-off line.

Read back: delivery ledger 2/2 for the two SS notes; `python tools/usage_ledger.py gate`;
the parked fields in the live status file. Name these in the ORDER's end state.

## As-built deviations

- D1 Roster lookup. Decision: derive MAIN's roster from its existing dest_inboxes row
  (up to 3 levels above that inbox). Alternatives: more dest_inboxes rows or
  `loop.roster` in the local config (rejected: gitignored in the main checkout, a lane
  cannot write it, and it would need a session). Why: it works from the merge with no
  machine path in a tracked file. Not verified: the roster's location and SS entry could
  not be read from a lane. Reverses if: redelivery still reads 0/2; then set `loop.roster`.
- D2 Recorded reset. Decision: the kit's reset archive is the only record honoured.
  Alternatives: also the machine ledger's `cap-reset` lines (rejected: a machine file
  read by every test's budget, not hermetic). Why: `budget_reset` always writes the
  archive. A reset done by emptying the file by hand leaves no record and ages out in
  24 h. Reverses if: the live archive is absent while MAIN reports a recorded reset.
- D3 Status fields. Decision: merge the fields after the kit's `write_status`, per tick.
  Alternatives: a separate file (rejected: the order names inbox_status.json); a kit edit
  (forbidden, FLEET item 11). Why: the kit owns the schema. Cost: a kit status write
  between ticks drops them until the next tick, at most one tick interval. Reverses if:
  the kit gains an extra-fields argument.
- D4 Parked scope. Decision: session-routed orders and items in state adjudicate.
  Alternatives: orders only. Why: both wait on a session (CLAUDE.md loop rule 4).
  Reverses if: MAIN wants orders only.
- D5 Product line. Decision: EW's spend lines are the lane roster plus note classes (build,
  data, review, inbox, triage, other), over a rolling 7 days. Alternatives: feature areas
  (rejected: usage rows carry no feature label). Why: those are the labels the kit records.
  Reverses if: MAIN defines product lines differently.
- D6 Hand-off. Decision: this lane left EW-NEXT-SESSION.txt and the /done command alone and
  reports those halves BLOCKED. Alternatives: edit them (rejected: the lane's orders forbid
  the first, and the second is outside what a lane may write). Reverses if: a session does row 165.
- D7 Sampling. Decision: a fix round counts as a retry after a failure; a verifier run does
  not; retries do not advance the 1 in 20 count; the first lane after merge is sampled, so the
  ACCEPT does not wait 20 lanes. Sampled runs use a preset `--session-id`, so a timed-out run's
  transcript is still findable. Alternatives: the kit's `persist=True` and the id from the
  usage line (rejected: a timeout has none). Reverses if: MAIN rules fix rounds out.
- D8 Size cap. Decision: set automatically at 2 x the total of the first 20 samples, written
  once to `cap.json`. Alternatives: a session sets it by hand (rejected: the order's rule is
  measure then set, and row 166 still records it). Why: room for about 40 samples. Reverses
  if: the measured size is out of line with the sidecar's space.
- D9 Untested paths. The real PowerShell Recycle Bin call and a real transcript copy are not run
  by the tests (fakes, by the hermetic rule). Row 166 reads the real copy; the Recycle Bin path
  first runs when the cap is passed, and a failure keeps the file and logs `recycle-failed`.
