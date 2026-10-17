# 0029 - Targeted deep-dive: autonomy, efficiency, player features

Operator order 2026-10-17 (plan 134). Read 2026-10-17 from the EW tree at the
plan 134 base commit; line numbers are that commit. Dedupe base: plans
001-134. Nothing here reaches the game client (Game ToS floor, CLAUDE.md).

Evidence limit: the lane runs in a linked worktree whose permission set does
not reach the main checkout, so the runtime ledgers there
(`timings.jsonl`, `headless_usage.jsonl`, `loop_items/*.json`, live
`progress/*.json`) were not read. Findings cite code paths and constants
instead of measured spend; plan 138 and plan 136 each start with a slice that
measures on the main checkout. See plan 134 "As-built deviations".

Severity: H = unattended operation fails or silently degrades; M = cost or
waste that grows; L = polish. Verdict: PLAN (new plan below), NOTE (record
only, no plan now), NO (rejected, reason given).

## A. Autonomy

| # | Finding | Evidence | Sev | Verdict |
|---|---|---|---|---|
| A1 | No supervisor for the EW server. The server is started only by `tools/launch.py` (logon task, `--server-only`) or the manual tray / pill "Restart server". A crash at 03:00 stays down until the operator acts; the overlay and every dashboard tab go blank. | `tools/launch.py:54-62` starts only when `healthy()` fails and only when launch runs; `app/main.js:252-272` `restartServer()` is reached only from the tray (`:283`) and IPC `ew:restart-server` (`:289`); `tools/logon_task.py:25` logon trigger only; `tools/loop_task.py:30` ticks the loop, not the server | H | PLAN 135 |
| A2 | Loop state is invisible on the dashboard. The operator (mostly away, QA from a phone or a glance) reads loop health only from `progress/loop.json` by hand; HALT, usage backoff, `adjudicate` / `gave-up` items and a tick that stopped firing never show in the app. | `tools/ew_loop.py:1242-1247` writes loop.json only; `server/ew/app.py` has no loop route (its only "loop" hits are "loopback"); `app/dashboard/dashboard.js:242` Signal health card covers game signals only | H | PLAN 136 |
| A3 | A hung lane (pid alive, no progress) is detected only by the 5400 s lane timeout. FLEET item 12 says a progress file silent for 2x its ETA "is treated as a failure and investigated"; the tick checks pid liveness only. | `tools/ew_loop.py:518-531` `reap_lost` (pid only); `tools/loop_base.py:63` `LANE_TIMEOUT_S = 5400`; the loop already reads `p<id>-build.json` for blocked markers (`tools/ew_loop.py:717`) | M | PLAN 137 |
| A4 | Dead lane locks are reclaimed by pid (kit), never by age. Correct as is. | `ops/fleet_kit/fleet_lanes.py:47`, `:686` | L | NO (kit-owned, works) |
| A5 | Lane failures retry on the next tick without backoff; only usage limits back off (`BACKOFF_BASE_S = 1800`, cap 6 h). Bounded anyway by `MAX_ATTEMPTS = 2`. | `tools/loop_base.py:58-63`; `tools/ew_loop.py:424`, `:532-541` | L | NOTE (bounded; revisit if a flapping item is seen twice) |
| A6 | An idle tick still runs every phase (reap, inbox, finished, retry, settle, recover, work_list, dispatch). The tick is timed (`loop-tick` kind) and warned above 60 s, so cost is visible already. | `tools/ew_loop.py:1259-1272`, `:1321`, `:1240` | L | NOTE (measure via the plan 136 card first) |
| A7 | A headless lane in a linked worktree could not write its FLEET item 12 progress file into the main checkout (the permission prompt denied it in this very run); it wrote the worktree copy, which `blocked_marker` already reads first. The stall check in A3 must read both trees the same way and treat a missing file as unknown, never stalled. | this run; `tools/ew_loop.py:717-720` reads `(wt, main_tree)` | M | PLAN 137 (folded in) |

## B. Efficiency

| # | Finding | Evidence | Sev | Verdict |
|---|---|---|---|---|
| B1 | Control ledgers grow without bound and are re-read whole. Every tick parses every row of `headless_usage.jsonl` (`backfill_kind`) and every ETA estimate parses all of `timings.jsonl`; `claims.jsonl` (hook decision log) and finished `progress/*.json` pile up (plan 102 hand-moved 33 stale progress files). | `tools/ew_loop.py:1256`; `tools/usage_ledger.py:129-141`; `tools/eta.py:68`; no rotate / max_bytes anywhere in `tools/` or `server/`; `docs/plans/ROADMAP.md` row 103 | M | PLAN 138 |
| B2 | Upstream fetches never send validators. `httpcache` keeps `{fetched_at, data}` only, so every TTL expiry is a full GET; a 429 / 503 is backed off by the generic `min(30 * 2**n, 1800)` and ignores `Retry-After`. | `server/ew/httpcache.py:1-9`, `:21-23`, `:42-45`; `server/ew/market.py:23` TTLs; `server/ew/progress.py:36,40` | M | PLAN 139 |
| B3 | Market batching already exists (`search(ids)` one GET for many ids). | `server/ew/market.py:92-124` (plan 071) | L | NO (done) |
| B4 | No per-item headless cost cap: worst path is 1 build + 3 fix + 4 verifier runs, times `MAX_ATTEMPTS = 2`; only the global runs cap binds. | `tools/ew_loop.py:631-693`, `:446` `HEADROOM = 3`; `tools/loop_base.py:58-63` | M | NOTE (needs the usage-per-item numbers B1's measure slice produces; refute rounds already cap at 3) |
| B5 | Prompts reference docs by path and cap findings (`[:8000]`, `[-6000:]`); no-change runs are recorded `no-change`. | `tools/loop_prompts.py:45,52,62,92`; `tools/ew_loop.py:628,672` | L | NO (already lean) |
| B6 | Server imports 56 modules eagerly at start. | `server/ew/app.py:47-56` | L | NOTE (start is once per logon; measure before any lazy-import work) |
| B7 | Test tiers and xdist exist (`-n 4 --dist loadfile`, slow / server / git markers, 100 test files). | `tools/ew_loop.py:253`; `tools/ew_tests.py:8-23`; `pytest.ini` | L | NO (plans 096 / 097 cover) |
| B8 | `itemnames` keeps an unbounded in-memory dict; bounded in practice by the game's item count. | `server/ew/itemnames.py:131` | L | NOTE |

## C. Player features (single Deadeye, zero-touch)

Keyword sweep over `docs/plans/*.md` (read 2026-10-17): zero hits for
silver goal / weekly silver, black stone price trend, costume, family
inventory, node war, khan, magnus, succession, skill add-on preset. Most are
not for a single PvE Deadeye (node war, khan) or need client data the floor
forbids (skill presets live in the client).

| # | Finding | Evidence | Sev | Verdict |
|---|---|---|---|---|
| C1 | No silver goal. EW measures silver (grind log silver/h, silver-OCR deltas, sold-items ledger) but never answers "am I on pace for this week's target" - the question that sizes a grind session. | `server/ew/grind.py:70` `silver_per_hour`, `:1351` `_silver_delta`; `server/ew/ocrinfer.py:772` `silver_rate`, `:814` `silver_delta`; plans 039, 112, 123 | M | PLAN 140 |
| C2 | Black stone / mats price trend: plan 052 price bands and plan 071 auto-watch cover it. | plans 052, 071 | L | NO (duplicate) |
| C3 | Node war, Khan, Magnus, succession / skill add-on presets. | single-character PvE scope (one Deadeye, no alts); skill presets are client-side only | L | NO (scope / ToS floor) |

## Ranking

Value / cost, highest first. Each fits one lane run (`lane_timeout_s` 5400).

| Rank | Plan | Title | Value | Cost |
|---|---|---|---|---|
| 1 | 135 | Server watchdog | H: unattended outage becomes a 1-2 min blip | S: pure-JS state machine + main.js wiring |
| 2 | 136 | Loop status card | H: the away operator sees halt / stuck / stale tick at a glance | M: one read-only route + one card |
| 3 | 137 | Stalled-lane flag | M: hung lanes show in 2x ETA, not 90 min | S: one tick phase, no kill |
| 4 | 138 | Control ledger rotation | M: tick and ETA cost stop growing with age | M: one tool + tick hook + archive |
| 5 | 140 | Weekly silver goal | M: player-facing pace answer | M: one module + card |
| 6 | 139 | Upstream conditional GET + Retry-After | M/L: fewer bytes, politer to arsha.io | S: httpcache only |

Plan 139 ranks last: its validator half is worth little if the upstream sends
no ETag / Last-Modified (its slice 1 measures that first); the Retry-After half
is still cheap and correct.
