# Research 0021 - Remaining operator-typed fields survey (plan 120)

Date: 2026-10-10. Scope: every operator write route the EW server still
accepts (`server/ew/app.py` `Handler.POST_ROUTES`, read on the tree after plans
108-119 merged), each typed field behind it, whether a live source already
fills it, and - where none does - a candidate live source inside the Game ToS
floor (CLAUDE.md): operator-saved screenshots + OCR (plan 063 pipeline), the
BDO-REST-API profile (plan 004, self-hosted base plan 119), the arsha.io
market cache (plan 002), the session log (game running / login only), the
official notice pages (plan 059 / 064) and tracked sourced data files. No
input ever reaches the game window; nothing here reads memory, packets or
client files.

Method: the POST route table and each domain module's write ops
(`server/ew/*.py`) were read; the auto sources were taken from
`ocrauto.KINDS` (silver, buff, level, gear, book_use, weight, slots, cp, fame,
mastery, zone_xp, loot, currency_balance, enh_fs, enh_crons, enh_agris), the
profile reader (`progress.py`: characters, specLevels, energy,
contributionPoints, gs) and the notice parsers (`eventnotices.py`: events, hot
times, maintenance, coupon codes, claim windows, deadlines).

Verdict key: AUTO = a live source already fills it (typed is an override or
fallback only); INTENT = the operator's own goal or note, no source can know
it, stays typed by design; VIABLE = a live source exists, plan proposed;
NO SOURCE = nothing ToS-safe shows it.

## 1. Route inventory

| Route | Typed fields / ops | Live source today | Verdict |
|---|---|---|---|
| `/api/pets` | add / edit: name, species, tier, talents, alpha, out | none (plan 043 roster is all typed) | VIABLE - plan 121 (pet window OCR) |
| `/api/pets` | feed (fed_at stamp) | none | NO SOURCE worth a plan: hunger shows only in the pet window; low value |
| `/api/pets` | goals | - | INTENT |
| `/api/mounts` | add / edit: name, kind, tier, level, gender, skills | none (plan 044) | VIABLE - plan 122 (horse information OCR) |
| `/api/mounts` | materials (T10 breed material counts), fern_rate | none | VIABLE - plan 122 (material counts from the same reads; fern rate derived from count deltas) |
| `/api/mounts` | failures (T10 breed failures since success) | none | NO SOURCE: no verified in-game counter display; stays typed |
| `/api/inventory` | set: base_lt, slots, slots_used | AUTO (plan 081 weight / slots OCR) | AUTO |
| `/api/inventory` | set: fame_vt, vp_cost | VP state AUTO (plan 109 buff), fame AUTO (plan 108) | AUTO / INTENT (vp_cost is a price the operator pays) |
| `/api/inventory` | source: lt, next_lt, next_cost, note per LT source | none | NO SOURCE: the game shows only the total LT (read by 081), not a per-source breakdown; next_lt / next_cost belong in `data/weight_sources.json` |
| `/api/inventory` | town_add / town_edit / town_del: used, total, note | none | VIABLE - plan 123 (warehouse window OCR) |
| `/api/inventory` | sale / sale_del (sale price log) | none | VIABLE - plan 123 (Central Market sales list OCR; the authenticated web market stays forbidden) |
| `/api/crafting` | add / edit / delete: recipe inputs, outputs, procs | prices AUTO (plan 002 cache) | VIABLE - plan 125 (tracked sourced recipe catalog: pick, not type) |
| `/api/imperial` | cp, mastery | AUTO (plan 042 profile, plan 117 OCR) | AUTO |
| `/api/imperial` | deliver (boxes delivered today) | none | VIABLE - plan 124 (delivery window remaining-count OCR) |
| `/api/imperial` | box_add / box_del | seed boxes in `data/imperial_boxes.json` | INTENT (extra rows beyond the seed) |
| `/api/leveling` | sample / sample_del | AUTO (plan 116 OCR + profile) | AUTO |
| `/api/leveling` | hot_add / hot_del | AUTO (notice `parse_hot`) | AUTO (typed for a window the notices miss) |
| `/api/leveling` | deadline_set / deadline_accept | AUTO (plan 116 notices) | AUTO |
| `/api/leveling` | book_use | AUTO (plan 111 book-use apply) | AUTO |
| `/api/leveling` | book_add (XP book stock) | none | VIABLE - plan 124 (loot / catalog reads naming an XP book) |
| `/api/leveling` | milestones, epoch_add / epoch_del | - | INTENT (goals) / data (`xp_epochs.json`) |
| `/api/deadeye` | fs_use, agris_set, crons_set | AUTO (plan 118 enhancement window OCR: current FS, crons, Agris) | AUTO |
| `/api/deadeye` | fs_add (stored failstack bank rows) | none (118 reads the current FS only) | VIABLE - plan 126 (stored failstack list OCR) |
| `/api/deadeye` | step_done (enhancement step reached) | none | VIABLE - plan 126 (item tooltip / enhance result grade read) |
| `/api/deadeye` | note, add_step, edit_step, delete_step, move_step, rate_set, shop_set | - | INTENT (build notes, plan, gear family) |
| `/api/progress` | character: name, cls, level, gs | AUTO (plan 004 profile characters, plan 066 level / gear OCR) | AUTO |
| `/api/progress` | step, claim | AUTO in part (plan 086 claim windows) | INTENT for quest steps |
| `/api/progress` | add_track, remove_track, obj_*, brackets_set, track_seed | - | INTENT |
| `/api/today` | tick / untick | AUTO (plans 013 / 114 auto rules, shot cues) | AUTO (event rows manual by plan 114 ruling) |
| `/api/today` | add / remove / move, weekly_*, event_* | - | INTENT (the operator's own checklist) |
| `/api/events` | add / edit / done / delete | AUTO (notices auto_add, plan 064) | AUTO (typed for what the notices miss) |
| `/api/events` | currency_balance | AUTO (plan 115 OCR) | AUTO |
| `/api/events` | login_mark | AUTO (plan 075 session log) | AUTO (typed only for days before tracking began) |
| `/api/events` | wish, claimed, dismiss_notice / undo_notice | - | INTENT |
| `/api/grind` | log, loot_item, buff | AUTO (plans 112 / 113 / 063) | AUTO |
| `/api/grind` | start / stop, add_spot, drop_*, keep, edit | AUTO in part (plan 062 play session) | INTENT |
| `/api/bosses` | tick / untick (weekly boss loot) | AUTO (plan 111 boss loot) | AUTO |
| `/api/market/watch` | add / remove | - | INTENT (watchlist) |
| `/api/settings` | market.vp, market.fame_pct | AUTO (plans 109 / 108) | AUTO |
| `/api/settings` | bdo.install_dir, bdo.documents_dir | AUTO (plan 065 detection) | AUTO |
| `/api/settings` | profile.family, profile.base_url | - | INTENT (identity, set once in onboarding; plan 119 base) |
| `/api/settings` | overlay.*, ui.*, notify.mute_until | - | INTENT (preferences) |
| `/api/ocr` | review / undo / read | - | the OCR review queue itself (not a typed field) |
| `/api/onboarding` | dismiss / restore | - | INTENT |
| `/api/maint/digest` | ack | - | INTENT |
| `/api/portraits` | pick | - | INTENT |

## 2. Viable automations (deduped against plans 001-120)

Ranked by typed-field count removed per unit of work; every OCR plan follows
the plan 063 / 111 shape (confidence, auto-commit gate, review queue below it,
undo, `auto_applied` audit, a typed value stays a newer-wins override), a
title row in `data/ocr_regions.json` `titles` (unverified until a real shot is
measured) and synthetic-text tests (no screenshots in tests).

| Plan | Title | Fields removed | Source | Rank note |
|---|---|---|---|---|
| 121 | Pet window OCR -> pets roster | name, species, tier, talents (x up to 5 pets) | pet list / pet info shots | most typed fields left in one card |
| 122 | Horse information OCR -> mounts + breed materials | tier, level, gender, skills; T10 material counts; fern rate | stable / horse info shots; item count reads | second-largest typed card |
| 123 | Warehouse storage and sold-items ledger from OCR | per-town used / total; sale price log | warehouse window; in-game market sales list | sales log is the most repetitive typing left |
| 124 | XP book stock + Imperial delivered count from reads | book_add; deliver | plan 113 loot / catalog reads; delivery window | small, reuses existing readers |
| 125 | Crafting recipe catalog data file | recipe inputs / outputs / procs | tracked sourced data (public wiki / guide, robots.txt checked) | no OCR; pick instead of type |
| 126 | Stored failstacks + enhance step done from OCR | fs_add rows; step_done | stored FS list; item tooltip grade | closes the plan 118 gap |

Dedup check: each title was run through the loop's own
`loop_roadmap.is_duplicate` against every existing plan title and the other
new titles (test `tests/test_typed_fields_survey.py`). Overlaps reviewed by
hand: 118 reads the current FS / crons / Agris (126 adds the stored bank and
step completion); 117 reads CP / mastery (124 adds delivered count only); 081
reads total weight / slots (123 adds per-town storage); 054 is the calculator
(125 adds the catalog only).

## 3. Not proposed (and what would reverse it)

- Per-source LT breakdown: the game shows only the total (081 reads it).
  Reverses if a measured screenshot shows a per-source list.
- T10 breed failure counter: no verified in-game display. Reverses if a
  stable-window shot shows the count.
- Pet feeding stamp: hunger readable only in the pet window; feeding is a
  routine in-game act with low planning value. Reverses if plan 121's pet list
  read shows hunger reliably (then a one-line add to 121).
- profile.family: identity, set once; no unauthenticated source names the
  operator's family. Never automatable inside the ToS floor.
- Every INTENT row: the operator's goals, notes and preferences.

## 4. ToS check

All six plans read operator-saved screenshots (the game's own screenshot key,
read after the file is written), tracked data files or public pages with
robots.txt respected. None sends input, reads memory, packets or client
files, or calls an authenticated market action (the market sales list is read
from a screenshot of the in-game window, never from the web market).
