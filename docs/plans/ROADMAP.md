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
| 106 | Sidecar consolidation, session part (research 0018 F-OUT-2/3): lane worktrees from ../ew-worktrees to the kit v14 sidecar root (<sidecar>/EW/Worktree/lane-<i>, fleet_lanes) with the loop HALTed and lanes idle; archive the superseded kit bundles v6-v13 out of moon_sync_inbox after an inbox_seen check | [>] MAIN-gated (bundle archive done 2026-10-09: kit bundles v6-v14 to the Recycle Bin after an inbox_seen check; worktree move waits for MAIN to set FLEET_SIDECAR_ROOT, kit v14 ORDER 3.4, adjudicated; hand-off MAIN bullet) |
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
| 159 | GitHub Security findings (MAIN ORDER nc266c6, 2026-10-18-2243): open before = code scanning 1 (alert #4 py/http-response-splitting, error, server/ew/app.py), Dependabot 0, secret scanning 0 (read 2026-10-18 23:4x via gh). Triage #4, fix TDD or dismiss with reason via the alerts API, read back its state, record per kind before -> after in the hand-off, send ONE correction ANSWER (TERMINAL) to MAIN - the loop's 2319 ANSWER left every count blank | [>] session (needs gh; lanes cannot run gh) |
| 160 | Operator-marked fix: no dependabot[bot] in Contributors (MAIN ORDER na7e421, 2026-10-18-2312) | [x] done 2026-10-18 session 39: no rewrite needed - fleet_rewrite plan f595a4ac5f91 scanned 592 commits, 0 to rewrite, SHA change 0; read-back: contributors API (anon=1) lists only the operator; origin/main 590/590 commits operator author and committer (sidebar lag only). Going forward a Dependabot bump lands as an operator commit and the PR is closed with a reason |
| 161 | Loop inbox: a note's attachment (.png beside its .md, same stem) is part of that note, never a separate order item or ANSWER (2026-10-18: the .png of MAIN ORDER 2312 became item Na7e421 and the loop sent a 2349 ANSWER asking MAIN to resend; session 39 retracted it). Also an order lane that ends with every item BLOCKED (e.g. needs gh) routes the order to the session instead of auto-sending a blank TERMINAL ANSWER (2319 re nc266c6). TDD in tools/loop_inbox.py | [x] done 2026-10-19 (loop; refute 0/3 PASS) |

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

## Order Nc266c6 - blocked items

GITHUB-SECURITY-FINDINGS ORDER (MAIN 2026-10-18-2243). Remote: origin on GitHub
(repo renamed EbonWake 2026-10-18). Repo-file read in this lane: `.github/workflows/ci.yml`
and `codeql.yml` already SHA-pin every action, set top-level `permissions: contents: read`,
`persist-credentials: false`, and CodeQL scans python, javascript-typescript and actions;
`.github/dependabot.yml` present. No alert data was readable, so no finding was fixed or
dismissed in this lane; nothing in repo files was changed for this order.

- Section 1 read of code-scanning / dependabot / secret-scanning alerts (`gh api .../alerts --paginate`): BLOCKED - `gh` is outside this lane's allow list (all three calls denied). Next interactive session: run the three reads.
- Section 2 triage, fixes and dismissals via the alerts API: BLOCKED - depends on section 1 (needs `gh`).
- Section 3 per-kind open before -> open after record: BLOCKED - depends on section 1; next session writes it into the hand-off.
- Commit, push, read-back: BLOCKED by this lane's own order (no commit); the loop commits and pushes after merge.
- Progress file ops/loop/control/progress/Nc266c6.json: BLOCKED - write to the main checkout was denied by this run's permissions.

## Order Na7e421 - blocked items

OPERATOR-MARKED-FIXES ORDER (MAIN 2026-10-18-2312, subject: contributors, dependabot,
ONE ANSWER). The note was delivered as a PNG image; the lane received only its raw bytes
as mangled text, and reading the inbox copy in the main checkout was denied by this run's
permissions, so no item of the order could be read. Repo-file state checked: no tracked
CONTRIBUTORS file; `.github/dependabot.yml` covers github-actions (/), pip (/ci) and npm
(/app), weekly, grouped. Nothing in repo files was changed for this order.

- Every order item: BLOCKED - note body is an image the lane could not render (raw PNG bytes, inbox file outside the allow list). Next interactive session: open the PNG, act on its items, send the ONE ANSWER.
- Contributors fix (likely a GitHub contributors-graph / author-identity item): BLOCKED - needs the order text and probably `gh` or a history rewrite (FLEET 17: MAIN ORDER via fleet_rewrite.py only).
- Dependabot fix (likely open Dependabot PRs or alerts): BLOCKED - needs the order text and `gh`, outside this lane's allow list.
- Commit, push, read-back: BLOCKED by this lane's own order (no commit); the loop commits and pushes after merge.
- Progress file ops/loop/control/progress/Na7e421.json: BLOCKED - main checkout outside this run's read/write permissions.

## Order N7e0676 - blocked items

OPERATOR-MARKED-FIXES ORDER (MAIN 2026-10-18-2312): remove "dependabot[bot]"
from the repo page Contributors. Repo-side scan in this lane (local refs, fetched
origin/main tip bd94d6c): `git log origin/main` author + committer census = one
identity, the operator; zero bot author or committer on the default branch. The
only bot-authored commits in the object store are the three open Dependabot PR
heads (remote-tracking `origin/dependabot/*` only, not ancestors of main):
e07001d (github-actions group), 5f50483 (electron 44.7.0), 288bcb6 (ruff 0.17.0).
All three bumps already landed on main as operator commits (82e97fd, d2bc84a,
48887e0; `git diff HEAD <bot> -- <files>` empty for actions and electron, ruff
pins equal), so the PRs are superseded. History was already rewritten once
(2026-10-09, session 20, plan f3dc20264bb1 3 -> 0, contributors read back 1).
`fleet_rewrite.py plan` scans only refs/heads + refs/tags, so it would flag 0
here (no local branch holds a bot commit): no rewrite is warranted from local
state; not a kit defect on this evidence. Likeliest cause of the sidebar row:
remote main differs from the fetched tip, or GitHub's contributors cache kept
the pre-rewrite count. Going forward (rule, already practised): a Dependabot
bump is applied as an operator commit and its PR closed "superseded by <sha>";
never a GitHub merge/squash that keeps the bot as author. Alerts stay on.

- Contributors read-back `gh api repos/<owner>/<repo>/contributors`: BLOCKED - `gh` is outside this lane's allow list. Next interactive session: run it; if it still lists dependabot[bot], `git fetch` and re-run the author/committer census on origin/main.
- Fresh remote state (`git fetch` / `git ls-remote origin`): BLOCKED - network git is outside this lane's allow list; the census above is against the last fetched origin/main.
- `python ops/fleet_kit/fleet_rewrite.py plan` dry run: BLOCKED - denied in this lane. A `run`, if ever needed, must happen in the main checkout (it refuses while a linked worktree exists) after `plan` and `bundle`, then a gated force push.
- Close the three superseded Dependabot PRs with reason "applied as operator commit 82e97fd / d2bc84a / 48887e0" and delete their branches: BLOCKED - `gh` is outside this lane's allow list.
- Commit, push, read-back: BLOCKED by this lane's own order (no commit); the loop commits and pushes after merge.
- Progress file ops/loop/control/progress/N7e0676.json: BLOCKED - write to the main checkout was denied by this run's permissions.

As-built deviations (refute round 2/3). Decision: the order is NOT closed as done;
it stays an open ROADMAP row for a run that holds `gh` and network git. Alternatives:
(a) claim done from the local census (rejected: census is against a stale fetched
tip `bd94d6c` and the sidebar cause is a guess); (b) run `gh` / network git here
(rejected: tried again in round 2, `gh api .../contributors` and `git fetch` both
need approval this run cannot give; a harness permission denial is not a decision
the adjudicator can lift); (c) a standing OPERATOR bullet (rejected: standing orders
1 and 6 send tool grants to the adjudicator, and this is one). Self-adjudicated:
the `gh` grant is the thing to request, so the row below is a plain open work item,
not an operator task. Why: removal of dependabot[bot] is only verifiable by a
`gh api .../contributors` read-back. Reverses if: a run with `gh` and network git
reads back a contributors list without dependabot[bot] (close the row), or lists it
(then run the census on the fetched tip and `fleet_rewrite.py plan`).
Added in round 2: `tests/test_fix_no_bot_identity.py` guards "no bot author or
committer reachable from HEAD" so the claim is no longer prose only. The
hand-off file is not edited by this run (rule); the loop carries the row below
into `EW-NEXT-SESSION.txt` via /done. Merge state: `docs/plans/ROADMAP.md` has no
conflict markers; `git add` was denied to this run, so the loop stages it to clear
the UU status. No commit.
refute-rounds: 2/3

- [ ] open (priority) N7e0676 contributors/dependabot: with `gh` and network git, `git fetch`, `gh api repos/<owner>/<repo>/contributors --jq '.[].login'`; if dependabot[bot] is listed re-run the origin/main author/committer census and `fleet_rewrite.py plan`; close the three superseded Dependabot PRs ("applied as operator commit"); send MAIN the ONE ANSWER note with the read-back.
