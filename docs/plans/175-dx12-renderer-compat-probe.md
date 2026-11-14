# Plan 175 - DX12 renderer compatibility probe: overlay visibility and screenshot format

Status: proposed. Source: research 0048.

## Problem

Patch 2026-10-29 added a DirectX 12 / FSR 3.1 renderer option. EW assumes the
overlay window draws above a borderless client and that ScreenShot files keep
their name and image format. Nothing checks either after a renderer change, so
a silent break (overlay hidden, watcher missing files, OCR on a new format)
would look like "no data".

## Scope

1. A signal-digest (plan 073) line "renderer check": last screenshot seen
   (extension, pixel size, age) from the existing ScreenShot watcher, flagging
   an extension or size not seen before in the watcher's own history.
2. A Settings row (plan 030) "Overlay test pattern": a separate EW overlay
   window shows a labelled border for 10 s so the operator confirms by eye it
   draws above the client in DX11 and DX12. Operator-triggered, no game input.
3. Result stored as an operator-typed override (plan 079) with set-at date;
   expires at the next client patch (plan 174 signal).
4. No client file, memory, packet or window-handle access; only EW's own
   window and the watcher's file metadata.

## Tests

Failing test first: watcher history with png then a new extension -> flag;
same format -> quiet; empty history -> quiet. Node test: test-pattern window
config keeps ignoreMouseEvents true and always-on-top.

## Depends-on

None

## As-built deviations (build lane, self-adjudicated 2026-11-14)

Built: `server/ew/renderer.py` (`image_size`, pure `check` over store domain
`renderer`, `RendererProbe`), plan 073 digest row `renderer` (reasons
`no_shot`, `new_format`, `new_size`, `overlay_hidden`; hints in
`data/signal_hints.json`), `GameWatch.health()["other_shot"]`, override key
`overlay.test_pattern` (policy `days:30`), POST /api/settings
`{"overlay_test": {renderer, seen}}` / `{"clear": "overlay.test_pattern"}`,
GET /api/settings `overlay_test`; app `shared/testpattern.js`,
`overlay/testpattern.html`, IPC `ew:overlay-test`, Settings card "Overlay
test pattern". Tests: `tests/test_renderer_probe.py`,
`app/test/testpattern.test.js`.

1. Pixel size is read from the image header (PNG IHDR, JPEG SOF, BMP DIB;
   at most 256 KiB, read-only) of the newest ScreenShot file, not from stat
   metadata. Alternatives: extension + byte size only (no pixel size).
   Why: the plan asks for pixel size and stat has none; the file is the
   operator's own screenshot that OCR already reads in full; no client file.
   Reverses if: a header read is shown to contend with the game's write
   (then size only after the OCR read).
2. The watcher lists only jpg/jpeg/png/bmp, so a new format would be
   invisible. It now also keeps the newest file of any OTHER extension since
   start (`other_shot`, stat only, never opened unless a known header). The
   probe picks the newer of the two. Alternatives: widen SHOT_EXT (would
   feed unknown formats to OCR / gallery). Why: detect without changing
   OCR inputs. Reverses if: OCR adopts a new format.
3. The flag sticks while the shot that introduced the format is the newest
   (stored per history entry), so re-reads are idempotent and the warn
   clears at the next shot. Size and extension flag independently; a size
   is compared only with known sizes. History capped at 20 formats.
   Reverses if: the operator wants a manual acknowledge instead.
4. Expiry "at the next client patch": policy rule `days:30` as a cap, and
   the probe retires the entry (`retired_by: "patch"`) once plan 174's
   cached notice list (`dataverdicts.newest_patch`, no fetch) shows a patch
   dated after the set day (same day keeps it). Alternatives: a new rule
   `until:next_patch` in overrides.RULE_RE. Why: same pattern as plan 170
   (`olvia.lecture`), no ledger grammar change. Reverses if: a second key
   needs patch expiry (then a shared rule).
5. The result is POSTed on the existing /api/settings route (a Settings
   row, plan 030), not a new route, so the typed-fields survey and the
   bridge allowlist keep one write path. `overlay.test_pattern` is a
   zero-touch exemption (operator eye check; nothing can observe EW's own
   window above the client without reading the game window).
6. Digest priority: overlay hidden > new format > new size > no shot > ok;
   a hidden-overlay answer warns even before any screenshot. The test
   window covers the overlay display's full bounds (a borderless client
   covers the work area too), reuses the overlay's `screen-saver` level and
   is opened at most once at a time.
