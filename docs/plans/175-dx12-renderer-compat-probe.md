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
