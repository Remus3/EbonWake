# Ebonwake roadmap

Markers: `[x]` done, `[>]` in progress, `[ ]` open. `[>] session` = a
session carries it (the loop dispatches only `[ ]` rows). One plan = one
batch = one push. Spec: `docs/design/0001-ebonwake-spec.md`. History:
`docs/plans/ROADMAP-history.md`.

| # | Plan | Status |
|---|---|---|
| 001 | Skeleton: server (health/version/state, SSE), dashboard shell (tabs), overlay shell (click-through + hotkey), ETA log, lane driver, tests + CI | [x] done 2026-10-04 (desktop self-test green: 7 tabs fit 1264x761 content, overlay alpha 0 + WS_EX_TRANSPARENT, hotkeys registered) |
| 002 | Market tab: arsha.io v2 client with disk cache + TTL + backoff, watchlist, sparkline, order book, alert thresholds | [x] done 2026-10-04 (live arsha data on the desktop, self-test 7/7) |
| 003 | Today tab: daily/weekly checklist with NA reset clocks, login events, dice; overlay reset countdown | [x] done 2026-10-04 (refute 2/3 PASS; self-test 7/7) |
| 004 | Progress tab: quest / season-pass / gear tracker, BDO-REST-API profile card | [x] done 2026-10-04 (refute 2/3 PASS; profile API base verified vs upstream openapi) |
| 005 | Grind tab: grind session log, silver/h, buff timers (overlay widget) | [x] done 2026-10-04 (refute 2/3 PASS; self-test 7/7) |
| 006 | Events tab: coupon + event + Twitch-drop tracker with expiries (seed from official pages) | [x] done 2026-10-04 (refute 1/3 PASS) |
| 007 | Deadeye tab: build notes (markdown), enhancement plan | [x] done 2026-10-05 (refute 1/3 PASS; self-test 7/7) |
| 008 | Session-log tail (game running / logged in) + ScreenShot watcher | [x] done 2026-10-05 (refute 2/3 PASS; operator log check pending) |
| 009 | OCR of operator-taken screenshots (buff icons, silver) - adjudicate engine first | [x] done 2026-10-05 (refute 2/3 PASS; follow-up: Tesseract chain primary, Windows OCR fallback, synthetic bench 284/288 vs 159/288) |
| 010 | Packaging: start-on-login task, single-instance, tray | [x] done 2026-10-05 (logon task read back: exists, delay PT1M, enabled; server second instance exits 0; self-test 7/7 painted) |
| 011 | Leveling tracker: XP rate + next-level ETA, recurring Hot Time windows, XP bonus stack (Progress card + overlay widget) | [x] done 2026-10-05 (refute 1/3 PASS; self-test 7/7; OCR word-gap fix also landed, refute 2/3 PASS: 1-2 spaces after silver 66/120 -> 120/120 on renders) |
| 012 | Grind spot recommender by AP/DP/level from a sourced community table | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 013 | Season pass tracker by objective, auto-tick level objectives | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 014 | Coupon auto-check vs the official news page (robots.txt-gated, suggest only) | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 015 | EW loop tick: inbox answers, lane dispatch, review + merge + push, idle deep-dive, 15-min scheduled task | [x] done (built in lane 2026-10-05; task LaneLoop installed, read back 2026-10-09: Ready, PT15M, IgnoreNew, last result 0) |
| 016 | OCR comma-drop regression: a vanished comma must not cut a digit group (old bench 141 -> 142/144) | [x] done 2026-10-05 (loop; refute 1/3 PASS) |
| 017 | Supply-chain hardening (MAIN order Nfa7953): dependabot, SHA pins, hashed CI pip, CodeQL, read-only token, ruff gate, fuzzing ruled out | [x] done 2026-10-05 (loop; refute 1/3 PASS; Scorecard before/after blocked) |
| 018 | Level cap 75 readiness: one level range, patch epoch for XP rates, re-seeded milestones, XP buff presets | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 019 | Loop dependency gate: skip a ROADMAP row until its Depends-on plans are done | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 020 | Server health + version-skew guard, System freshness card, honest 404 copy, / redirect | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 021 | Multi-cadence resets: per-item reset rule (Sunday weeklies, non-midnight dailies) | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 022 | Overlay placement off the minimap, content-sized height, legibility | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 023 | AP/DP bracket calculator: bonus AP, DR %, next-bracket gain on the Progress card | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 024 | Olvia Academy deadline vs level ETA: red pill when Lv 60 lands after enrolment closes | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 025 | Home / Now tab: one glance screen for resets, dailies left, buffs, session, ETA, alerts | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 026 | Toasts + opt-in Windows notifications (alert hit, buff ending, Hot Time, reset, coupon, game exit) | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 027 | Market net proceeds after tax (VP / fame) + pre-order-queue badge | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 028 | Market item-name search (local name index) + exact silver in detail | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 029 | Overlay market ticker: up to 5 watched prices, alert hits first | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 030 | Settings tab + allowlisted POST /api/settings (overlay, hotkeys, profile, theme, scale, notifications) | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 031 | World boss schedule: NA table as sourced data, DST-correct next-spawn API | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 032 | World boss overlay widget + Today card + 5/15-min notification | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 033 | Weekly content planner gated by level and gear (Black Shrine, Atoraxxion, Jetina, LoML, Garmoth, Edania) | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 034 | Post-graduation gear roadmap track + graduation readiness + adventure-log seeds | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 035 | Enhancement EV calculator: per-step chance tables, expected attempts and cost, Agris pity cap | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 036 | Failstack bank + Agris pity tracker + cron budget | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 037 | Shopping list from the enhancement plan: materials x arsha prices, can-afford-by | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 038 | Drop-buff cap calculator (300/400/500 % caps, rate vs amount) + Blessing of Agris ROI | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 039 | Loot-valued grind log: per-spot loot tables, tax-correct silver/h, sell-vs-vendor | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 040 | OCR loot-window import: operator screenshot -> item counts for the grind log | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 041 | Profile history: hourly BDO-REST-API snapshots, trend sparklines, auto level sample | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 042 | Lifeskill / energy / contribution card from the profile API | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 043 | Pet roster: 5 slots, tier, talents, special-skill coverage, exchange planner | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 044 | Mount tracker: horses (tier, level, skills), Royal Fern Root counter, T10 breed pity calc | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 045 | Inventory / weight / storage planner + Value Pack ledger | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 046 | Session-end summary: prompt to stop the grind on game exit, nightly and weekly recap | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 047 | Density and accessibility rework: content-sized cards, focus-visible, keyboard tabs, tab badges | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 048 | Quick-entry parsers (1.2b, 30d, 90m) + local time everywhere | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 049 | Shared SSE event bus in the dashboard, hidden-tab poll pause, keyed row updates | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 050 | Command palette (Ctrl+K) with typed commands and cross-tab search | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 051 | First-run checklist: profile family, log path, ScreenShot folder, overlay corner, watch items, dailies | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 052 | Enhancement-mats price bands (p20/p50/p80) with cached-history fallback and below-p20 alert | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 053 | Imperial delivery planner: CP/2 boxes per type, 250 % box value, reset countdown | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 054 | Cooking / alchemy margin calculator: operator recipes, input/output prices, net after tax | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 055 | Jetina boss-crystal planner + Caphras cost calculator | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 056 | Black Spirit's Adventure dice timer from logged-in time (overlay) | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 057 | Deadeye notes autosave + safe open-in-browser for source links | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 058 | Loop resolves its own merge conflicts: re-dispatch a resolve lane | [x] done 2026-10-05 (loop; refute 0/3 PASS) |
| 059 | Official event-notice import: maintenance-relative windows, suggest-only | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 060 | Combat Secret Book ledger: books per activity, observed XP, books-to-level | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 061 | Profile source robots gate: public BDO-REST-API host is robots-disallowed; self-host base, graceful degrade | [x] done 2026-10-06 (session fix; refute 0/3 PASS) |
| 062 | Auto play-session: login opens, exit closes the grind log (no Start/Stop, no exit prompt) | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 063 | Auto-OCR every new screenshot while logged in: confidence-gated auto-commit + review queue | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 064 | Official notice auto-import: maintenance UTC, Hot Time windows, events + coupons auto-add with undo | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 065 | Zero-config first run: Documents / Steam library path auto-detect, self-ticking onboarding | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 066 | Progress inference from screenshot OCR: level, XP %, silver, buffs, AP/DP, book use | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 067 | Context-aware overlay: widgets chosen by state (in game, idle, maint/reset/boss soon), pins and blocks | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 068 | Auto-tick inferable checklist rows: login dailies, dice ready, boss-shot suggestion | [x] done 2026-10-06 (loop; refute 2/3 PASS) |
| 069 | One "What now" card on Home + overlay: next best action ranked by urgency | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 070 | Prompt hygiene: stale-prompt expiry, dedupe, game-closed quiet, 15/5/1 alert ladder | [x] done 2026-10-06 (session merge; refute 1/3 PASS) |
| 071 | Self-curating market watch: seeded from shopping list / loot / recipes, thresholds from price bands | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 072 | World boss schedule drift check against a public NA table (robots-gated, banner only) | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 073 | Signal health digest: per-signal liveness with one-line fix hints | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 074 | Before-maintenance digest: loss warnings from maintenance notices + everything ending at the next maintenance, T-24 h | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 075 | Login-day reward tracker: qualifying login days per event, days left, at-risk alert | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 076 | Home consolidation: full-width What now, one Timers card, quiet line for empty cards, no repeated facts | [x] done 2026-10-06 (loop; refute 1/3 PASS) |
| 077 | One status truth: onboarding, profile card and stale styling derived from the signal digest | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 078 | Settings and formatting consistency: one control per overlay widget, human labels, local-time display (no new entry), palette button | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 079 | Override ledger: source, set-at, expiry, superseded by live signals; override badges + digest list | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 080 | Settings purge: delete automation kill switches, manual overlay layout, per-rule notify toggles, tunables | [x] done 2026-10-07 (session merge; refute 3/3 PASS) |
| 081 | Derive typed planner inputs from live signals: silver, hours/day, inventory weight, CP, fame, loot counts, Hot Time ends | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 082 | Class portrait: FaceTexture archive, characterNo -> class binding from the session log, top-left class chip with empty state | [x] done 2026-10-06 (loop; refute 0/3 PASS) |
| 083 | Deadeye portrait gallery: portrait history + class-attributed screenshots, optional pick as a plan 079 override (depends on 079, 082) | [x] done 2026-10-07 (loop; refute 1/3 PASS) |
| 084 | Larger class portrait card: left-rail character card (156 x 201, 96 x 124 compact) with Lv, class, energy / CP over the image, End Game card style (depends on 082) | [x] done 2026-10-07 (loop; refute 0/3 PASS) |
| 085 | Patch-notes data verifier: hinted unverified data rows checked against official patch notes, runtime verdicts, digest row (depends on 064, 073) | [x] done 2026-10-07 (loop; refute 0/3 PASS) |
| 086 | Reward claim windows: claim-by deadlines that outlive the event, Events row, Timers, What now (depends on 064, 069) | [x] done 2026-10-07 (loop; refute 0/3 PASS) |
| 087 | Patch-notes match fidelity: Unicode fold, name aliases, hints for the official 2026-10-08 numbers (depends on 085) | [x] done 2026-10-08 (loop; refute 0/3 PASS) |
| 088 | Monster Zone Info OCR: per-kill EXP and recommended level per zone, kills-to-level, cap-bound buff flag (depends on 063, 066) | [x] done 2026-10-08 (loop; refute 0/3 PASS) |
| 091 | loop: route ORDER items needing ops/fleet_kit/, CLAUDE.md or .claude/ edits to a session (or grant that lane those paths) - lane briefs block them by construction (N94ff08) | [x] done 2026-10-08 (loop; refute 0/3 PASS) |
| 092 | Fleet kit v11 -> v13 catch-up (Nf0e1ea, N0fcd68, v13 bundle): vendor, anchored + claims hooks, gitlock / suite gate, test guard, identity hooks | [x] done 2026-10-08 (session 20) |
| 093 | loop: reply notes never reach the destination inbox (written only to moon_sync_outbox, undashed 20261008- stamps); copy each reply into the sender's inbox with the dashed stamp, re-hash, record N/M reached; test a reply lands with a matching hash | [x] done 2026-10-08 (loop; refute 0/3 PASS) |
| 095 | Event currency planner: guaranteed currency by event end vs an exchange wishlist, shortfall and buy-by warnings (depends on 064, 075, 021) | [x] done 2026-10-09 (loop; refute 0/3 PASS) |
| 096 | Perf 2.1: one authoritative gate run per tree state - verdict cache keyed by git write-tree (push skips an already-gated tree), verifier drops pytest from VERIFY_EXTRA, producers run touched tests only (MAIN 2246 sec 2) | [x] done 2026-10-09 (loop; refute 0/3 PASS) |
| 097 | Perf 2.2 rest: pytest markers slow / server / git with a fast tier for producer and verifier loops; hash-pinned xdist -n 4 at the loop gate (--dist loadfile for real-git tests), adjudicate a dev-only test dep under the stdlib-only rule; tests only (MAIN 2246 sec 2) | [x] done 2026-10-09 (loop; refute 0/3 PASS) |
| 098 | Perf 2.4: detached review / fix / merge worker (the _launch path); the tick only classifies, dispatches and reaps, target under 60 s; gate independent items in parallel worktrees (MAIN 2246 sec 2) | [x] done 2026-10-09 (loop; refute 0/3 PASS) |
| 099 | Perf 2.5: model / effort routing by item kind - opus for plan implementation, sonnet for fix rounds, data refreshes, resolve-merge and research; effort low for verifier and inbox via pick_effort; choice recorded in loop config (MAIN 2246 sec 2) | [x] done 2026-10-09 (loop; refute 0/3 PASS) |
| 100 | Perf 2.8: governor counts runs from headless_usage.jsonl (or reconciles headless_budget.json at tick start); backfill kind build on the 34 rows lacking kind or exclude pre-v8 rows (MAIN 2246 sec 2) | [x] done 2026-10-09 (loop; refute 0/3 PASS) |
| 101 | Perf 2.9: headless lanes work inline - drop the background agents share one scratchpad clause from headless GATES prompts (MAIN 2246 sec 2); plan docs/plans/101-headless-inline-gates.md | [x] done 2026-10-09 (loop; refute 0/3 PASS) |
| 102 | Repo review and audit repo-review-20261009 (MAIN 2246 sec 8): every file on disk in the main checkout (tracked, untracked, ignored), research 0018, reversible fixes | [x] done 2026-10-09 (session re-run from the reaped lane partial; refute 0/3) |
| 103 | Main-checkout inventory the lanes cannot read: count ops/runtime, ops/loop/control, moon_sync_inbox / outbox, logs, app/node_modules (one folder + file count); list sidecar moves into the one sidecar folder; Recycle Bin only, consumer-checked (research 0018) | [x] done 2026-10-09 (folded into 102: counts in research 0018; 33 stale progress files + 2 budget backups moved to the sidecar archive, duplicate old-drive project dir to the Recycle Bin) |
| 104 | Hand-off prune at the next /done: move the closed NOTE / OPERATOR QA bullets research 0018 lists into a dated hand-off ledger and fix the stale Status block (session 19 under SESSION 20) | [x] done 2026-10-09 (session 22 /done: closed bullets to docs/handoff-ledger.txt, Status block rewritten) |
| 105 | TEMP-1 (MAIN FIX N7416e2): pytest.ini tmp_path_retention_policy = failed, tmp_path_retention_count = 1; behavior test in tests/test_pytest_retention.py. Plan: `docs/plans/105-temp1-pytest-retention.md` | [x] done 2026-10-09 (rebuilt on main from keep ref; refute-rounds 3/3, adjudicated) |
| 106 | Sidecar consolidation, session part (research 0018 F-OUT-2/3): lane worktrees from ../ew-worktrees to the kit v14 sidecar root (<sidecar>/EW/Worktree/lane-<i>, fleet_lanes) with the loop HALTed and lanes idle; archive the superseded kit bundles v6-v13 out of moon_sync_inbox after an inbox_seen check | [x] done 2026-11-08 (session 45: loop HALTed, 0 lane locks, `git worktree move` lane-0 and lane-1 to <sidecar>/EW/Worktree; READ BACK 2026-11-08 16:31 after the move: `git worktree list` = main checkout 8fdd6e8 [main], <sidecar>/EW/Worktree/lane-0 8fdd6e8 (detached), <sidecar>/EW/Worktree/lane-1 ae0a5c2 (detached); fleet_lanes.worktree_path(0..2) = <sidecar>/EW/Worktree/lane-0, lane-1, lane-2; sidecar_root() with FLEET_SIDECAR_ROOT unset (process + HKCU) = SIDECAR_DEFAULT (kit v28); HALT removed; no loop_items held a lane (none ran/committed/failed-dirty), so none repointed; old ../ew-worktrees left in place, empty; earlier history in sections Order Ne1235e, N3ef61f, N2cfb1c) |
| 107 | Split the two monoliths by domain, no behaviour change (research 0018 F-APP-1): app/shared/ewcore.js (7562 lines) into per-feature modules re-exported from ewcore.js, and tools/ew_loop.py (2563 lines) inbox / roadmap / merge helpers into modules; every existing test passes unchanged | [x] done 2026-10-09 (loop; refute 0/3 PASS) |
| 108 | Fame bonus auto: OCR (and profile fame tier) derive market.fame_pct; a config value never beats a read, only a newer typed override wins; plan docs/plans/108-fame-auto.md (depends on 081) | [x] done 2026-10-10 (loop; refute 0/3 PASS) |
| 109 | Value Pack auto: VP armed from the buff OCR with expiry, lapsed timer = no VP, market.vp retires to a fallback; zero-touch guard leaves only profile.multi_character (depends on 108) | [x] done 2026-10-10 (loop; refute 0/3 PASS) |
| 110 | Wire built-but-unused endpoints into the dashboard: /api/events/currency, /api/zones/xp, /api/data/verdicts + a node --test guard that every GET route has a consumer (depends on 088, 085, 095) | [x] done 2026-10-10 (loop; refute 0/3 PASS) |
| 111 | Auto-apply high-confidence OCR suggestions (book use, zone reads, world boss loot ticks): gate 0.95, undo, auto_applied audit log; low confidence still queues (depends on 088) | [x] done 2026-10-10 (loop; refute 0/3 PASS) |
| 112 | Grind silver auto: silver-OCR delta across the play session fills the auto grind row (minutes from the session log), late shots fill once, typed beats derived (depends on 062, 063) | [x] done 2026-10-10 (loop; refute 0/3 PASS) |
| 113 | Grind loot OCR kind: loot-window shot -> item names via itemnames catalog -> counts priced by the arsha cache, applied on auto close (depends on 112) | [x] done 2026-10-10 (loop; refute 0/3 PASS) |
| 114 | More Today auto rules: shot:<cue> OCR cues for Daily Challenges, Barter, Guild mission, BS weeklies, Pearl Shop free item; bosses:N for weekly boss rewards; event rows stay manual (depends on 111) | [x] done 2026-10-10 (loop; refute 0/3 PASS) |
| 115 | Event currency balance OCR kind feeding eventcurrency: exchange / tooltip read replaces the typed balance, drops counted (depends on 095) | [x] done 2026-10-10 (loop; refute 2/3 PASS) |
| 116 | Leveling auto: OCR / profile reads make typed XP samples optional, held reads self-resolve on agreement, deadlines derived from notices (depends on 111) | [x] done 2026-10-10 (loop; refute 0/3 PASS) |
| 117 | Imperial CP + Imperial mastery from OCR: Energy/CP bar and life-skill mastery window shots fill the Imperial delivery planner (053) inputs; typed values become an expiring override (plan doc docs/plans/117-imperial-cp-mastery-ocr.md, write it first; depends on 111) | [x] done 2026-10-10 (loop; refute 0/3 PASS) |
| 118 | Deadeye enhance state from OCR: enhancement window shot reads failstack, cron count and Agris pity into the FS bank / Agris tracker (036) / EV calc (035); typed entry optional (plan doc docs/plans/118-enhance-window-ocr.md, write it first; depends on 111) | [x] done 2026-10-10 (loop; refute 0/3 PASS) |
| 119 | Self-hosted BDO-REST-API for family / gear: adjudicate the install (docker man90/bdo-rest-api, port 8001, robots-clean) first, record the ruling, then wire config/local.json base and verify 004/041/042 profile features light up (plan doc docs/plans/119-self-hosted-profile-api.md, write it first) | [x] done 2026-10-10 (loop; refute 0/3 PASS) |
| 120 | Remaining typed-fields survey: list every operator-typed field left (pets, mounts, inventory LT, crafting, others) with a candidate live source; write deduped automation plans + ROADMAP rows for the viable ones (research doc docs/research/NNNN-typed-fields-survey.md) | [x] done 2026-10-10 (loop; refute 0/3 PASS) |
| 127 | Scheduler window OCR: one Black Spirit's Scheduler shot ticks every pinned daily / weekly (plan doc docs/plans/127-scheduler-window-ocr.md; depends on 114, 111, 021) | [x] done 2026-10-12 (loop; refute 0/3 PASS) |
| 129 | ew_loop round-3 verifier pass: when refute round 3 ends with clean gates + clean extra_checks, run one verifier pass before marking adjudicate; persist per-round findings in the loop item (plan doc docs/plans/129-loop-round3-verifier-pass.md; source: adjudicator DD-20261012 ruling) | [x] done 2026-10-12 (loop; refute 0/3 PASS) |
| 130 | Known-issues advisories: curated official known-issue windows (Trading EXP shortfall, Lv59 stall, Agris Fever 10-15) exclude suspect XP samples and show a chip on Leveling / Enhance / Market (plan doc docs/plans/130-known-issues-advisories.md; depends on 064, 116, 060) | [x] done 2026-10-14 (loop; refute 0/3 PASS) |
| 131 | Night drop-chance clock: calibrated game clock derives the night flag for the drop-buff calculator (plan doc docs/plans/131-night-drop-clock.md; depends on 038, 063) | [x] done 2026-10-15 (loop; refute 0/3 PASS) |
| 132 | My Info (P) exact XP OCR: absolute XP samples for the leveling rate fit (plan doc docs/plans/132-myinfo-exact-xp-ocr.md; depends on 116, 063, 018) | [x] done 2026-10-15 (loop; refute 1/3 PASS) |
| 133 | Adventurer's Note (F2) level-figures OCR: second exact-XP window and cross-check for plan 132 (plan doc docs/plans/133-adventurers-note-f2-ocr.md; depends on 132, 063, 016) | [x] done 2026-10-16 (loop; refute 0/3 PASS) |
| 134 | Targeted deep-dive (operator order 2026-10-17): autonomous operation, efficiency, player features - research doc docs/research/0029-deep-dive-autonomy-efficiency.md + at most 6 deduped plans 135.. with proposed rows (plan doc docs/plans/134-autonomy-efficiency-deep-dive.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 135 | Server watchdog: the app health-polls and auto-restarts a dead EW server (plan doc docs/plans/135-server-watchdog.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 136 | Loop status card: last tick age, lanes, stuck items, halt and backoff on the dashboard (plan doc docs/plans/136-loop-status-card.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 137 | Stalled-lane flag: a lane silent for twice its ETA shows stalled in the loop checklist (plan doc docs/plans/137-stalled-lane-flag.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 138 | Control ledger rotation: cap timings, usage, claims and finished lane status files (plan doc docs/plans/138-control-ledger-rotation.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 139 | Upstream fetch politeness: conditional GET (ETag / Last-Modified) and Retry-After backoff (plan doc docs/plans/139-upstream-fetch-politeness.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 140 | Weekly silver goal: target, pace and projection from session and sales ledgers (plan doc docs/plans/140-weekly-silver-goal.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 141 | Hardening audit server-a: server/ew/ __init__, __main__, app.py through eventcurrency.py (alphabetical; about 7.1k lines) - findings fixed TDD, record docs/audit/20261017-server-a.md (plan doc docs/plans/141-audit-server-a.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 142 | Hardening audit server-b: server/ew/ eventnotices.py through levels.py (about 7.2k lines) - findings fixed TDD, record docs/audit/20261017-server-b.md (plan doc docs/plans/142-audit-server-b.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 143 | Hardening audit server-c: server/ew/ logindays.py through ocrinfer.py (about 5.9k lines) - findings fixed TDD, record docs/audit/20261017-server-c.md (plan doc docs/plans/143-audit-server-c.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 144 | Hardening audit server-d: server/ew/ onboarding.py through zoneinfo.py plus server/ew/data/*.json (about 7.9k lines) - findings fixed TDD, record docs/audit/20261017-server-d.md (plan doc docs/plans/144-audit-server-d.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 145 | Hardening audit app-dash-a: app/dashboard/ bosses.js through grind.js plus their app/test files - findings fixed TDD, record docs/audit/20261017-app-dash-a.md (plan doc docs/plans/145-audit-app-dash-a.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 146 | Hardening audit app-dash-b: app/dashboard/ home.js through today.js plus their app/test files - findings fixed TDD, record docs/audit/20261017-app-dash-b.md (plan doc docs/plans/146-audit-app-dash-b.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 147 | Hardening audit app-core: app/shared/core/*.part.js and app/shared/ewcore.js plus their app/test files - findings fixed TDD, record docs/audit/20261017-app-core.md (plan doc docs/plans/147-audit-app-core.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 148 | Hardening audit app-shell: Electron shell: main.js, preloads, overlay, selftest, tray, ew.css - findings fixed TDD, record docs/audit/20261017-app-shell.md (plan doc docs/plans/148-audit-app-shell.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 149 | Hardening audit tools: tools/*.py (loop, lanes, launch, leak sweep, eta, hooks installers) - findings fixed TDD, record docs/audit/20261017-tools.md (plan doc docs/plans/149-audit-tools.md) | [x] done 2026-10-17 (loop build, session merge after leak-sweep refusal; refute 0/3 PASS) |
| 150 | Hardening audit tests-a: tests/test_[a-l]*.py plus tests/conftest.py (test hygiene and coverage gaps) - findings fixed TDD, record docs/audit/20261017-tests-a.md (plan doc docs/plans/150-audit-tests-a.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 151 | Hardening audit tests-b: tests/test_[m-z]*.py (test hygiene and coverage gaps) - findings fixed TDD, record docs/audit/20261017-tests-b.md (plan doc docs/plans/151-audit-tests-b.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 152 | Hardening audit ops-ci-config: ops/ non-kit files, .github/, config templates, root files - findings fixed TDD, record docs/audit/20261017-ops-ci-config.md (plan doc docs/plans/152-audit-ops-ci-config.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 153 | CORS: answer GET / SSE only for the dashboard origins (audit follow-on SERVER-A-05; plan doc docs/plans/153-cors-dashboard-origins.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 154 | Robots-gated fetchers refuse cross-host redirects (audit follow-on SERVER-A-06; plan doc docs/plans/154-robots-fetch-no-cross-host-redirect.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 155 | Server config readers honour the injected config_path (audit follow-on TESTS-A-01, TESTS-A-15; plan doc docs/plans/155-config-path-injection.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 156 | Test hygiene follow-ups from the 20261017 audit (audit follow-on TESTS-A-16, -17, -18, -19, -25, -26, -27, -28; plan doc docs/plans/156-test-hygiene-followups.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 157 | Extend the test-isolation guard to tests/test_[a-l]*.py (audit follow-on TESTS-B-07; plan doc docs/plans/157-test-isolation-guard-a-l.md) | [x] done 2026-10-17 (loop; refute 0/3 PASS) |
| 158 | Store last-good snapshots: a corrupt operator doc restores from `.good` / 7 daily backups instead of emptying, with a restored signal (research 0030; plan doc docs/plans/158-store-last-good-restore.md) | [x] done 2026-10-18 (loop; refute 0/3 PASS) |
| 159 | GitHub Security findings (MAIN ORDER nc266c6, 2026-10-18-2243): open before = code scanning 1 (alert #4 py/http-response-splitting, error, server/ew/app.py), Dependabot 0, secret scanning 0 (read 2026-10-18 23:4x via gh). Triage #4, fix TDD or dismiss with reason via the alerts API, read back its state, record per kind before -> after in the hand-off, send ONE correction ANSWER (TERMINAL) to MAIN - the loop's 2319 ANSWER left every count blank | [x] done 2026-10-23 (alert #4 real, fixed TDD in 4319eb2 / plan 162; read back via gh: state fixed, fixed_at 2026-10-19T06:35:34Z, dismissed_reason null; code scanning 1 -> 0, Dependabot 0 -> 0, secret scanning 0 -> 0; correction ANSWER 2026-10-23-1918 to MAIN, 1/1 reached, sha256 31638f969421...) |
| 160 | Operator-marked fix: no dependabot[bot] in Contributors (MAIN ORDER na7e421, 2026-10-18-2312) | [x] done 2026-10-18 session 39: no rewrite needed - fleet_rewrite plan f595a4ac5f91 scanned 592 commits, 0 to rewrite, SHA change 0; read-back: contributors API (anon=1) lists only the operator; origin/main 590/590 commits operator author and committer (sidebar lag only). Going forward a Dependabot bump lands as an operator commit and the PR is closed with a reason |
| 161 | Loop inbox: a note's attachment (.png beside its .md, same stem) is part of that note, never a separate order item or ANSWER (2026-10-18: the .png of MAIN ORDER 2312 became item Na7e421 and the loop sent a 2349 ANSWER asking MAIN to resend; session 39 retracted it). Also an order lane that ends with every item BLOCKED (e.g. needs gh) routes the order to the session instead of auto-sending a blank TERMINAL ANSWER (2319 re nc266c6). TDD in tools/loop_inbox.py | [x] done 2026-10-19 (loop; refute 0/3 PASS) |
| 163 | Lane allow-list gap + false PASS: headless lanes deny npm/gh/git add so dependency-bump/alert-closing items can never pass (N82830d failed 3/3); keep-ref commit 9e52b0e carried 'verifier: PASS' with an empty app/ diff. Acceptance: a dependency-bump item can run npm install / npm test --prefix app and gh api dependabot alert reads in its lane; the verifier fails any FIX whose ordered files are missing from the diff | [x] done 2026-10-25 (loop; refute 0/3 PASS) |
| 164 | Loop router routes on what an order orders, not a passing mention; a session-routed order unsettled after 24 h gets one BLOCKED ANSWER (MAIN FIX N489d76; plan doc docs/plans/164-router-routes-on-what-an-order-orders.md) | [x] done 2026-11-01 (order N489d76, lane; backlog settlement open, see the order section) |
| 165 | Fleet Insights W44 session half (MAIN ORDER Nd11eb1; plan doc docs/plans/165-fleet-insights-w44.md): read back SS delivery 2/2 in the delivery ledger, `python tools/usage_ledger.py gate` and the parked fields of the live inbox_status.json; paste the overlay QA checks into the hand-off OPERATOR bullet; add the spend line step to the session's /done command | [x] done 2026-11-08 session 45: overlay QA checks (88d99c0) pasted into the hand-off OPERATOR QA bullet; spend step added to .claude/commands/done.md section 7 step 4; read-backs named in the Nd11eb1 section (SS 2/2, gate used 2 cap 500, parked fields absent = 0 parked) |
| 166 | Lane transcript samples read (MAIN ORDER Nd11eb1 item 6): `python tools/lane_samples.py status` shows one sample after a sampled lane and git ls-files shows none; record the size cap when 20 are measured; one sample survives a Sunday 04:30 retention run (first possible 2026-11-08) | [x] done 2026-11-08 session 45: status = 2 held, 728209 bytes, cap unset (measuring first 20, auto-written to cap.json at 20 per plan 165 D8), 6 lanes counted; git ls-files shows 0 samples; task Maint-ClaudeRetention (weekly Sunday) last ran 2026-11-08 04:30:30 result 0 and both samples (2026-11-03 13:35, 2026-11-08 00:19) survived. The CLI crashed on a circular import; read via `import ew_lane` first; row 171 |
| 167 | FLEET-9 read (MAIN ORDER Nd11eb1 item 7): zero live-state or timing failures in gated suite runs for 7 days; done when read clean on or after 2026-11-08 | [x] done 2026-11-08 session 45: suite-gate durations.jsonl, tree Ebonwake, 2026-11-01 16:42 to 2026-11-08 16:42: 20 gated runs, 19 exit 0, 0 exit 1 (no test failure: live-state guard and timing asserts fail as exit 1), 1 exit 2 (2026-11-08 16:31, `pytest -q -p no:cacheprovider`, held 4.6 s: interrupt or collection error, no tests failed); loop gate_verdicts 8 in window, 0 failed |
| 168 | Loop checklist overflow is silent (EW analogue of SS FIX N44eed9 (a)): tools/ew_loop.py checklist add() drops rows past the kit ROWS_MAX (20) with no count or marker; write the dropped count beside the rows in progress/loop.json ("checklist_dropped": N) and pin it with a test at 25 rows; adopt the kit's own overflow form instead if a kit version ships one first | [x] done 2026-11-03 (loop; refute 0/3 PASS) |
| 169 | Imperial Reward Seal ledger: per-category seals, exchange tables, Golden Seal conversion warning (2026-12-03) | [x] done 2026-11-07 (loop; refute 0/3 PASS) |
| 170 | Olvia Academy semester epoch: 4th Semester window, auto-graduation reset marks typed progress stale | [x] done 2026-11-07 (loop; refute 0/3 PASS) |
| 171 | `python tools/lane_samples.py status` crashes: ImportError cannot import name '_NO_WINDOW' from partially initialized loop_base (lane_samples -> loop_base -> ew_lane -> lane_samples cycle when run as a script; found by the row 166 read 2026-11-08). Acceptance: a test runs `python tools/lane_samples.py status` as a subprocess and gets the one status line, rc 0 | [ ] open |
| 172 | Tools script-mode smoke test: run every tools/*.py entry point as a script and fail on ImportError (sibling sweep of row 171) | [ ] open |
| 173 | Plan doc / ROADMAP consistency lint: first-line number, duplicates, missing rows and cited docs, legacy allow-list | [ ] open |

Ranking rationale per deep dive / audit and the closed channel-order
sections: `docs/plans/ROADMAP-history.md` (moved verbatim 2026-10-09, plan
102).

Ranking 20261015 deep dive: 132 (exact XP sharpens every level ETA at Lv
66-75) above 131 (night flag is a minor drop modifier).

Ranking 20261016 deep dive: 133 (redundant exact-XP read; low urgency, below
any 132 follow-up).

Ranking 20261017 targeted deep-dive (plan 134, research 0029): 135 > 136 >
137 > 138 > 140 > 139 (unattended recovery first, then visibility, then
upkeep and politeness).

Audit 20261017 (operator order, session 36): plans 141-152, one file-by-file
hardening slice each (about 7k lines, lane timeout 5400 s); queued after the
0029 rows merged; findings in docs/audit/20261017-<slice>.md. Result: 67 FIXED, 15 FILED;
the FILED product / test items became rows 153-157 (TESTS-A-01 / -15 and
TESTS-B-06 folded into 155); OPS-CI-CONFIG-07..10 (shared slots.py) went to
MAIN as a kit defect note.

Ranking 20261018 deep dive (research 0030): 158 (silent operator-data loss on a corrupt doc; above polish, below the 0029 unattended-recovery rows).

Ranking 20261107 deep dive (research 0044): 170 (typed progress goes stale at the 2026-11-12 reset, sooner) > 169 (Golden Seal conversion 2026-12-03, rate unannounced).

Ranking 20261110 deep dive (research 0046): 172 (a crash class no test can see; sibling sweep of row 171) > 173 (drift guard, low urgency).

Rules: refute rounds capped at 3 per item; every plan lands via a lane worktree
and one push; ETA log updated by every run.

## Order Nfa7953 - blocked items

- Section 4 Scorecard before/after: BLOCKED - needs the scorecard v5.5.0 Linux binary downloaded into WSL (operator-approved download).

## Order N1af105 - blocked items

Done in repo: tools/launch.py `--hidden` passthrough (`electron_args`), app/main.js
`show: !tray.startHidden(process.argv)` (helper in app/shared/tray.js; tray click,
show-dashboard hotkey, second-instance and overlay hotkeys unchanged), tools/logon_task.py
arguments `"...launch.py" --hidden`; tests/test_launch.py, tests/test_logon_task.py,
app/test/tray.test.js. As-built deviation: the argv check is the pure helper
`tray.startHidden` instead of an inline `process.argv.includes` (alternative: inline;
why: node-testable without Electron; reverses if: the helper is unused elsewhere and a
reviewer prefers inline).

- Step 4 `tools/logon_task.py install` + read-back: DONE session 31 (2026-10-12) from the MAIN checkout; `logon_task.py status` read back arguments `"<root>/tools/launch.py" --hidden`, delay PT1M, enabled.
- Step 5 next-logon read-back (no dashboard window, tray icon present, hotkey opens it): BLOCKED - needs a physical logon by the operator.
- Progress file ops/loop/control/progress/N1af105.json: BLOCKED - write to the main checkout was denied by this run's permissions.

## Order Neba23f - blocked items

GH-HYGIENE ORDER (MAIN 2026-10-18-1215). Section 1 done in this tree: README
Features table gained the missing Home and Settings tabs (server `TABS` in
`server/ew/app.py` serves nine); every other README claim, relative link,
screenshot file, badge target, hotkey default (`Control+Alt+E` /
`Control+Alt+D`) and the Apache-2.0 licence line verified against HEAD.

- Section 2 (About, topics, visibility, default branch, branch protection, wiki / projects / discussions, social preview, releases / tags via gh): BLOCKED - `gh` is outside this lane's allow list.
- Section 3 (outside view via gh repo view / gh API, Actions status of badge workflows, open issues and PRs): BLOCKED - `gh` is outside this lane's allow list.
- Outside-view finding, root tree: three tracked one-off merge-conflict scratch scripts `fix_resolve.py`, `p107-resolve_fix.py`, `p115-resolve_fix.py` sit at the repo root (no consumer found); removal via `git rm`: BLOCKED - `git rm` is outside this lane's allow list. Next session or lane: `git rm` them.
- Section 4 (commit, push, read back): BLOCKED by this lane's own order (no commit); the loop commits and pushes after merge.
- Progress file ops/loop/control/progress/Neba23f.json: BLOCKED - write to the main checkout was denied by this run's permissions.

## Order N7e0676 - contributors (closed)

- [x] done 2026-10-23 session 41 N7e0676 contributors/dependabot: read back via gh: contributors API (anon=1) lists 1 entry, the operator (User), no dependabot[bot]; fetched origin/main census: every commit operator author and committer, 0 Co-authored-by lines; bot PRs #6 #7 #8 closed unmerged (path B, bumps re-applied as operator commit 0e1f9d8, MAIN ORDER N38ca97); #1 #3 #4 #5 closed, #2 merged pre-rewrite. Loop resolve merged as 55bfeed. Status reported inside the N38ca97 ANSWER (0055 already answered N7e0676).

## Order N6e995b - blocked items

- Item 1 (`serve_forever` poll interval in tests/test_redirect_guard.py and every other `serve_forever` under tests/): DONE - the redirect-guard `_serve` helper was the only one on the 0.5 s default (66 others already pass `poll_interval=0.01`); it now passes 0.01 (matches the rest, not the note's 0.05). Same command `python -m pytest -p no:cacheprovider tests/test_redirect_guard.py -o addopts=""`: 15 passed 15.52 s before, 0.95 s after.
- Item 2 (`-n 8 --dist loadfile`, kept only if server-marked tests bind 127.0.0.1:0): DONE - no test binds a fixed port (8940 appears only in fakes / config dicts), so `ew_loop.XDIST_ARGS` is now `-n 8 --dist loadfile` (loop gate and `tools/ew_tests.py fast`); test_tiers expectations and ci/requirements-dev.in comment follow. Fast tier through the suite gate: 4173 passed, 32.65 s at -n 4, 29.66 s at -n 8 (both with item 1). ci stays serial (plan 097 deviation 2).
- Read back (before/after wall of `python -m pytest -q`): BLOCKED - this lane is ordered not to run the whole suite; the loop's authoritative gate run on this tree (now -n 8) is the after figure; before = MAIN's gate median 43 s.
- Reply (ONE ANSWER note): NOT-APPLICABLE - the loop writes it after merge.
- After the work: /done: NOT-APPLICABLE - headless lane; the loop and the next session close it.
- Progress file ops/loop/control/progress/N6e995b.json: BLOCKED - write to the main checkout was denied by this run's permissions.

## Order Ne1235e - blocked items

MAIN ORDER U5 2026-10-26 (row 106 sidecar lane move). Arrived as a headless
build lane running in lane-0 itself (lane lock 0 RUNNING), so the move is a
session act. No repo file needs to change for it: tools/ew_loop.py and
tools/ew_lane.py already take every lane path from kit
`fleet_lanes.worktree_path()`, which is sticky on the old path only while it
exists and the new one does not - after the move the next fire uses
`<sidecar root>/EW/Worktree/lane-<i>` with no code edit.

- Item 1 (HALT the loop, lanes idle, `git worktree move` lane-0..2 under the sidecar root): BLOCKED - this run IS the lane-0 executor (lanes not idle, a worktree cannot move itself mid-run) and `ops/loop/control/HALT` / the main checkout's git worktree metadata are outside this lane's writable tree; next interactive session does it per the hand-off ROADMAP 106 NOTE bullet.
- Item 2a (point every stored worktree_path at the new location): NOT-APPLICABLE as a code change - no tracked file stores a lane path (all derive from fleet_lanes.worktree_path); the runtime lane locks rewrite worktree_path on the next claim. Read back of the three values: BLOCKED with item 1.
- Item 2b (un-HALT, let one lane fire to prove it): BLOCKED - follows item 1; session act.
- Item 3 (mark row 106 [x] with the commit): BLOCKED - follows item 1; row 106 annotated with this order meanwhile.
- Read back (`git worktree list` after the move, three worktree_path values, first lane fire result, row-106 line): BLOCKED - follows items 1-3. Before the move, read now: lane-0..2 at `../ew-worktrees/lane-<i>` (f231188, 9e52b0e, 9c92e2e detached).
- tests/test_ew_lane.py `test_kit_worktree_layout_is_per_lane_index` (asserts the `ew-worktrees` parent): NOT-APPLICABLE - the suite pins FLEET_SIDECAR_ROOT off and the kit skips the v22 default under pytest, so it stays correct after the move.
- Reply (ONE ANSWER note with the read-back): NOT-APPLICABLE - the loop writes it after merge; it should carry this BLOCKED list until the session finishes the move.
- After the work: /done: NOT-APPLICABLE - headless lane; the loop and the next session close it.
- Progress file ops/loop/control/progress/Ne1235e.json: BLOCKED - write to the main checkout was denied by this run's permissions.

### Order Ne1235e - As-built deviations (refute round 1/3)

- Deviation: the worktree move (items 1-3 and read-back) is not done by this run. Decision: leave it a session act, recorded BLOCKED above. Alternatives: (a) move lane-0 from inside lane-0 (git refuses a worktree moving itself while a live lane runs in it; rejected); (b) edit ew_lane.py / ew_loop.py to fake the new path (rejected: paths already come from fleet_lanes.worktree_path(), so there is no file to change and a fake would desync the lane locks). Why: HALT, idle lanes and the move all need the main checkout, which a lane cannot touch. Reverses if: the order note names a repo file this section did not cover (then add it) or a session executes the move (then mark row 106 [x] with the read-back).
- Verified for the round: the NOT-APPLICABLE test claim holds - tests/conftest.py pins FLEET_SIDECAR_ROOT to "" and fleet_lanes skips SIDECAR_DEFAULT under PYTEST_CURRENT_TEST, so tests/test_ew_lane.py stays correct after the move.
- The reviewer could not read the order note (inbox read denied to it and to this run); the file list is the producer's reading of the lane prompt. Adjudicate at round 3 if still open.

## Order N3ef61f - blocked items

MAIN ORDER 2026-10-31-2128 (row 106: the 0334 ANSWER re Ne1235e misreported items 1-3 as DONE; the lane move is still owed, as a session act).

- Section 1 (the misreport, acknowledged): DONE - cause confirmed in tools/loop_inbox.py `answer_order`: its prompt context said "state merged, verdict PASS ... Mark each item DONE in that commit", so the reply copied the merge state; the Order Ne1235e section above records items 1-3 BLOCKED.
- Section 2 (answer writer takes each item's verdict from the merged commit's recorded per-item outcome; none = UNVERIFIED, not DONE): DONE - tools/loop_inbox.py `item_outcomes` / `item_verdict` / `answer_context` / `outcome_block`: verdicts come from the bullets of the order's 'Order <oid> - blocked items' section (the merged commit's record), the prompt states the merge state is not an item verdict, and every order ANSWER now ends with a deterministic authoritative per-item block (UNVERIFIED when nothing is recorded).
- Section 2 test (a merged PASS lane whose body says BLOCKED yields a BLOCKED line): DONE - tests/test_loop_inbox_item_outcomes.py `test_merged_pass_lane_whose_body_says_blocked_yields_blocked_lines` (plus `test_no_recorded_outcome_is_unverified_never_done`, `test_item_verdict_parser`).
- Section 3 item 1 (HALT the loop, lanes FREE, `git worktree move` lane-0..2 to <sidecar root>/EW/Worktree/lane-<i>): BLOCKED - this run is the lane-0 executor (lane lock 0 RUNNING), so lanes are not idle and lane-0 cannot move itself; the note orders it as an interactive SESSION act (hand-off NOTE bullet).
- Section 3 item 2 (point every stored worktree_path at the new location, un-HALT, let one lane fire): BLOCKED - follows item 1; session act (no tracked file stores a lane path: fleet_lanes.worktree_path() supplies it).
- Section 3 item 3 (mark row 106 [x] with the commit): BLOCKED - follows items 1-2; row 106 stays [>].
- Read back (`git worktree list` after the move, three worktree_path values, first lane fire result, row-106 line, answer-writer commit + test name): BLOCKED for the move parts (session act); the answer-writer test name is above, its commit is the loop's merge of this lane.
- Reply (ONE ANSWER note with the read-back): NOT-APPLICABLE - the loop writes it after merge; the session sends it once the move is read back.
- After the work: /done: NOT-APPLICABLE - headless lane; the next interactive session closes it.
- Progress file ops/loop/control/progress/N3ef61f.json: BLOCKED - write to the main checkout was denied by this run's permissions.

### Order N3ef61f - As-built deviations

- Deviation: the "merged commit's recorded per-item outcome" is read from the order's ROADMAP section in the merged tree, not from `git show <commit>` of the commit body. Decision: ROADMAP section. Alternatives: (a) parse the commit body via git (rejected: lane commit bodies carry only refute-rounds / verifier / loop item, no item verdicts - aed89e4 is an example - and a git spawn in the inbox pass needs a git-marked test path); (b) both (rejected: same gap). Why: every order lane is ordered to record each item there, and that section is what the merged commit adds. Reverses if: lane commit bodies start carrying per-item verdict lines.
- Deviation: beyond the prompt change, every order ANSWER gets a deterministic per-item block appended. Decision: append it. Alternative: prompt-only (rejected: the 0334 misreport came from the LLM reply; a prompt cannot guarantee it). Why: the record must not depend on reply wording. Reverses if: MAIN rules the appended block noisy and a prompt-only check is proven sufficient.

## Order N489d76 - blocked items

MAIN FIX 2026-11-01-0825 (the session router parks an order on a passing version mention). Plan doc: docs/plans/164-router-routes-on-what-an-order-orders.md.

- Item 1 (route on what the order orders): DONE - tools/loop_inbox.py `session_paths`: the version word counts only in the name, a body path only where a sentence orders it changed; tests/test_loop_inbox_p164.py pins a kit note and an ordered protected-path edit as routed.
- Item 1 ACCEPT, the byte pin of ORDER 2215: BLOCKED - this lane's permissions deny the inbox, so `test_order_2215_is_not_routed` uses a reconstruction of the shape MAIN reported (plan 164 deviation 3); unblocks when a session pastes the real bytes into `ORDER_2215`.
- Item 2 (bound the wait): DONE - `Tick.bound_session_wait` sends one BLOCKED ANSWER after 24 hours; `test_blocked_answer_sent_once_after_24_hours` uses a fake clock.
- Item 3, Neb5fba: BLOCKED - the work reads closed (hand-off: the kit v23 test guard IGNORE covers it, no EW action), but `session-done` writes the main checkout, denied here; unblocks with a session running `python tools/ew_loop.py session-done Neb5fba`.
- Item 3, N2cfb1c: BLOCKED - row 106 lane move still owed; it needs the loop HALTed and all lanes FREE, so a lane cannot do it; a session does the move, then marks it.
- Item 3, Nba8669: BLOCKED - no tracked file names it and this lane cannot read the note or its record, so whether its work is done is unread; a session reads it with `python tools/ew_loop.py session`.
- Item 3, Nb25a6f: BLOCKED - same as Nba8669.
- Item 3 fallback: after merge routing re-reads each queued note, so a backlog order that only mentioned a target goes to a lane and one still routed gets its one BLOCKED ANSWER naming what it needs on the next tick.
- Whole suite through the suite gate: NOT-APPLICABLE - the lane brief reserves it for the loop's ci gates; this lane ran ruff, the targeted tests and the fast tier.
- ONE ANSWER note: NOT-APPLICABLE - the loop writes it after merge.
- Progress file ops/loop/control/progress/N489d76.json: BLOCKED - the write to the main checkout was denied by this run's permissions.

## Order Neb5fba - blocked items

SS FIX 2026-10-24-1525, addressed to MAIN (kit fleet_test_guard IGNORE misses the two board files). No EW file changed: the kit fix had already shipped.

- Add board/status.json and board/state.json to fleet_test_guard.IGNORE, file by file: NOT-APPLICABLE - already shipped in kit v21; read at ops/fleet_kit/fleet_test_guard.py lines 81-82 of vendored v27, both paths listed by name, and FLEET item 11 forbids a local kit edit. Read, not run: this run's permissions refused a scratch snapshot script.
- SS drops its local conftest entry once the kit ships: NOT-APPLICABLE - SS's own tree; EW's tests/conftest.py passes no ignore, so it has no such entry to drop.
- Reply: NOT-APPLICABLE - the note asks for none beyond a kit version note, and the loop owns any ANSWER after merge.
- Progress file ops/loop/control/progress/Neb5fba.json: BLOCKED - the write to the main checkout was denied by this run's permissions; FLEET item 13 d forbids a worktree copy, so none was written.

## Order N2cfb1c - blocked items

MAIN ORDER 2026-10-25-1950 (row 106 lane move after kit v22; FLEET_SIDECAR_ROOT stays unset). Arrived as a headless build lane running in lane-1 (lane locks 0 and 1 RUNNING). Read 2026-11-01: `git worktree list` names the main checkout, lane-0 and lane-1 only, both still under `../ew-worktrees`; lane-2 is not registered, so the session moves what is registered, then reads worktree_path(2). As-built: no repo file changes the move, because every lane path comes from kit `fleet_lanes.worktree_path()`. Decision: leave the move to a session. Alternative: move from this lane (rejected: lanes are not FREE, a lane cannot move itself, and this run's permissions stop at its own worktree). Reverses if: a session runs the move, or the loop gains a step that does it between lanes.

- Section 1 (ruling, FLEET_SIDECAR_ROOT stays unset): NOT-APPLICABLE - a MAIN ruling, no EW act; this run did not set the variable.
- Section 2 item 1 (SIDECAR_DEFAULT present in the vendored kit): DONE - ops/fleet_kit/fleet_lanes.py defines it (kit v27 then; re-read in v28 by session 45).
- Section 2 item 2 (read back sidecar_root() with the variable unset in process env and HKCU): BLOCKED - the inline python read-back needs approval this run lacks, and the sidecar root is outside its readable tree; a session reads it right before the move.
- Section 2 item 3a (HALT the loop, wait for 3 FREE lanes, `git worktree move` each lane, repoint any held loop_items worktree): BLOCKED - lane-1 is this run and lane-0 is running, HALT and the worktree metadata are in the main checkout, which this run cannot write; session act.
- Section 2 item 3b (read back `git worktree list` and worktree_path(i) for i=0..2 after the move): BLOCKED - follows item 3a.
- Section 2 item 3c (remove HALT, flip row 106 to [x]): BLOCKED - follows item 3a; row 106 stays [>].
- Section 2 item 4 (leave the empty old parent or send it to the Recycle Bin): BLOCKED - follows item 3a; nothing was removed.
- Section 2 item 5 (suite keeps FLEET_SIDECAR_ROOT pinned to ""): DONE - no change needed: tests/conftest.py pins it; tests/test_ew_lane.py::test_suite_pins_fleet_sidecar_root_off passed this run.
- Section 2 item 6 (trigger line in EW-NEXT-SESSION.txt): NOT-APPLICABLE - the hand-off already reads "SIDECAR_DEFAULT present" (a session changed it, lines 5-8 and 66-70); no edit was needed.
- Section 3 (ONE ANSWER HOP 2 with the move commit, list, three values, row 106 [x]): NOT-APPLICABLE - the loop writes it after merge; the move values do not exist until a session runs the move.
- Progress file ops/loop/control/progress/N2cfb1c.json: BLOCKED - the write to the main checkout was denied by this run's permissions.

Session 45 (2026-11-08) closed the session-act items above: Section 2 item 2 DONE (sidecar_root() with the variable unset in process and HKCU = SIDECAR_DEFAULT, kit v28); item 3a DONE (HALT written, 0 lane locks, lane-0 and lane-1 moved; lane-2 was never registered; no loop_items record in a hold state, so none repointed); item 3b DONE (`git worktree list` = main checkout 8fdd6e8 [main], <sidecar>/EW/Worktree/lane-0 8fdd6e8 (detached), <sidecar>/EW/Worktree/lane-1 ae0a5c2 (detached); fleet_lanes.worktree_path(0..2) = <sidecar>/EW/Worktree/lane-0, lane-1, lane-2); item 3c DONE (HALT removed, row 106 [x]); item 4 DONE (old ../ew-worktrees left in place, empty, nothing unlinked); Section 3 DONE (session ANSWER HOP 2 to MAIN). Not read back: the first lane fire from the new path.

## Order Nd11eb1 - blocked items

MAIN ORDER 2026-11-01-1225 (Fleet Insights W44, one batch before a planned reboot). Plan doc docs/plans/165-fleet-insights-w44.md. A lane reads and writes its own worktree only, so every read-back of the main checkout, the sidecar or MAIN's tree is a separate bullet, not claimed. Rows 165-167 carry them.

- Item 1 code: DONE - tools/loop_inbox.py resolves every code from MAIN's roster, found from the existing MAIN row of loop.dest_inboxes; tests pin a 2/2 redelivery with re-hash on a fixture.
- Item 1 ACCEPT (both SS notes reached, 2/2 in the live ledger): DONE 2026-11-08 session 45 - read back in ops/loop/control/delivery.jsonl: both SS notes (the 2026-10-18-1234 and 2026-11-01-0934 ANSWERs) count 1/1 reached True at 2026-11-01T13:34:01, sha256 matching their 0/1 rows = 2/2.
- Paths ops/loop/control/delivery.jsonl and ops/fleet_roster.json: NOT-APPLICABLE - runtime ledger and MAIN's file, cited by the note, not ordered changed here.
- Item 2 code: DONE - tools/usage_ledger.py drops usage rows started before the kit's recorded reset (headless_budget.reset-<date>.json); tools/ew_loop.py builds the gate from kit tree_budget(root, code); tests pin it.
- Item 2 ACCEPT read-back (gate cap and count named): DONE 2026-11-08 session 45 - `python tools/usage_ledger.py gate` printed: used 2 cap 500 (budget file 2, usage log 2, last recorded reset 2026-11-01T12:14:01).
- Item 3 code: DONE - tools/loop_inbox.py parked_items / parked_status, tools/ew_loop.py status_parked: parked, parked_count, parked_oldest_age_h, and parked_warning from 48 h beside the kit fields; tests pin all of them.
- Item 3 ACCEPT live file read-back: DONE 2026-11-08 session 45 - live inbox_status.json (updated 2026-11-08T16:34) carries no parked fields because 0 items are parked (status_parked leaves the file untouched when nothing is parked); session 44 read the fields present at 17:49 while an item was parked.
- Item 4 (EW-2 overlay QA ask): DONE 2026-11-08 session 45 - the three 88d99c0 checks read back in EW-NEXT-SESSION.txt's OPERATOR QA bullet.
- Item 5 tool half (EW-3): DONE - `python tools/usage_ledger.py spend` prints the one line; test pins it on fixture rows. This week's live figures were not read (needs approval this run lacks).
- Item 5 /done half: DONE 2026-11-08 session 45 - .claude/commands/done.md section 7 step 4 runs `python tools/usage_ledger.py spend` and copies its line into the hand-off Status; live line read: Spend 7d to 2026-11-08: $10.78 total; build $5.50, data $3.14, review $0.90, inbox $0.00, triage $0.00, other $1.24; 0 unpriced runs.
- Item 6 code (EW-4): DONE - tools/lane_samples.py, tools/ew_lane.py and the fix round in tools/ew_loop.py: 1 lane in 20 (the first lane after merge is sampled) plus every retry, persistence on for those only, copied to <sidecar>/EW/Scratch/lane-samples, never in the tree; cap measured from the first 20; oldest leave by the Recycle Bin. Fake-tested; the real Recycle Bin path and a real transcript copy were not run.
- Item 6 ACCEPT (one sample in the sidecar after a sampled lane, git ls-files none; Sunday 04:30 survival): DONE 2026-11-08 session 45 - 2 samples held (728209 bytes, 6 lanes counted, cap unset until 20), git ls-files 0, both survived Maint-ClaudeRetention 2026-11-08 04:30:30 (result 0); row 166. CLI import bug filed as row 171.
- Item 7 (FLEET-9): DONE - nothing to fix: the 2 timing lines (tests/test_progress.py) already use fleet_test_guard.budget(); added tests/test_order_nd11eb1.py guard failing any raw timing assert.
- Item 7 7-day read: DONE 2026-11-08 session 45 - 20 gated EW runs 2026-11-01..11-08, 0 exit 1 (0 live-state or timing failures), 1 exit 2 (4.6 s interrupt, no test failed); row 167.
- End state (committed, merged, pushed, worktree list, whole suite through the gate): BLOCKED - this lane does not commit; the loop gates, merges and pushes. A lane worktree is a standing one; the ANSWER must read tip, remote tip and worktree list from a session.
- Progress file ops/loop/control/progress/Nd11eb1.json: BLOCKED - written in this worktree (gitignored), not the main checkout, whose writes are outside this run.

## Order N44eed9 - blocked items

SS FIX 2026-11-03-1324 to MAIN (kit checklist caps, item 13a departure, board displaced row). Every item targets kit files pinned at ops/fleet_kit/ (FLEET item 11) or asks MAIN for a ruling; EW holds none of it. The ONE ANSWER is MAIN's kit version note.

- (a) fleet_checklist.Checklist.rows() cuts at ROWS_MAX 20 with no marker: NOT-APPLICABLE - ops/fleet_kit/fleet_checklist.py is pinned; the fix is MAIN's kit version. EW's own analogue (tools/ew_loop.py checklist add() drops rows past ROWS_MAX silently) is filed as ROADMAP row 168.
- (a) fleet_headless._checklist_rows cuts at CHECKLIST_MAX 20 with no marker: NOT-APPLICABLE - ops/fleet_kit/fleet_headless.py is pinned; MAIN's kit version.
- (a) fleet_headless [:120] task text cut vs fleet_checklist.item() ValueError above TASK_MAX: NOT-APPLICABLE - both kit files pinned; MAIN's kit version. EW's loop clips task text to 70 chars before item(), so it hits neither rule.
- (a) requested kit change (overflow marker or count in both paths, one over-long text rule after fleet_board._clip): NOT-APPLICABLE - asked of MAIN; EW adopts it when a kit version ships it (row 168).
- (b) ruling on SS b82bf05 trailing overflow note vs item 13a: NOT-APPLICABLE - a ruling for MAIN on SS's tree; EW prints no such trailing line and does not edit the byte-pinned common block.
- (c) fleet_board.build() marks a row displaced past the cap done mid-session: NOT-APPLICABLE - ops/fleet_kit/fleet_board.py is pinned; MAIN's kit version. Unreachable in EW today (under 20 rows).
- ONE ANSWER: NOT-APPLICABLE - addressed to MAIN; the loop writes any EW reply after merge.
- Progress file ops/loop/control/progress/N44eed9.json: BLOCKED - this run may not execute the writer script (approval denied) and the progress dir is in the main checkout.

## Order Nbcd29f - blocked items

MAIN ORDER 2026-11-08-1200 to ALL (operator order: "always utilize appropriate claude model and effort for the tasks/runs/commands/etc"). TERMINAL for acknowledgement: no ANSWER note.

- (1) Save feedback_model_and_effort_fit_the_task.md byte for byte in the Claude memory directory: BLOCKED - the memory directory is outside this lane's worktree and the lane run was denied read access to it (permission not granted); an interactive EW session saves it (check for an existing covering memory first).
- (2) Add the MEMORY.md index line for it: BLOCKED - same reason as (1); done together with (1) by an interactive session.
- (3) Apply it: every Agent spawn, workflow agent and fleet_headless spawn sets model and effort deliberately: DONE - already in place via plan 099: tools/loop_base.py ROUTES maps each lane kind to a model + effort (plan/order/handoff opus medium; data/resolve/deep-dive/fix sonnet medium; verify/inbox sonnet low), passed to the kit spawn by tools/ew_loop.py route_kw and tools/ew_lane.py; interactive sessions set model/effort on Agent spawns per the saved memory.
- Progress file ops/loop/control/progress/Nbcd29f.json: BLOCKED - write to the main checkout's progress dir was denied (permission not granted) for this lane run.
