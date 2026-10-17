# Plan 135 - Server watchdog: the app health-polls and auto-restarts a dead EW server

Status: open. Source: research 0029 finding A1 (plan 134). Lane hint:
`build`.

Problem: the EW server (port 8940) is started only by `tools/launch.py` at
logon and by the manual tray / pill "Restart server" (`app/main.js:252-289`).
If it dies while the operator is away, the dashboard and overlay stay blank
until a human acts. CLAUDE.md standing order 11 allows restarting the server,
overlay and dashboard at any time.

## Slices

1. Tests first: `app/test/watchdog.test.js` (node --test, no Electron) for a
   pure state machine `app/shared/watchdog.js`:
   `next(state, probe, now) -> {state, action}` where probe is `ok` / `fail`
   and action is `none` / `restart` / `give-up`.
   - 3 consecutive failed probes (poll every 20 s, so about 1 min down) ->
     `restart`; one ok probe resets the count.
   - Restart backoff: 1 min, 2, 4, ... capped at 30 min between restarts;
     the backoff resets after 10 min of ok probes.
   - At most 6 restarts per rolling hour, then `give-up` until an ok probe
     (a crash loop must not spin pythonw forever).
   - While a manual restart (tray / pill) is in flight the watchdog does
     nothing (shared `restarting` flag).
2. `app/main.js`: one `setInterval` (20 s) probes `GET /api/health` via the
   existing `getLocal`, feeds `watchdog.next`, and on `restart` calls the
   existing `restartServer()` (it already kills only an EW-contract server
   via `tray.killablePid`). No new spawn path.
3. Surfacing: the state (`ok` / `restarting` / `gave-up`, restarts in the last
   hour, last restart time) goes to the dashboard over the existing IPC
   bridge (`app/preload.js`) and shows as one line in the System tab Signal
   health card (`app/dashboard/dashboard.js:242`); `gave-up` raises one toast
   (plan 026 path).
4. Each auto-restart appends `{at, reason, n}` to
   `ops/runtime/watchdog.jsonl` (gitignored runtime), capped at 500 rows
   (rewrite tail, atomic).

## Acceptance

- `npm test --prefix app` green including `watchdog.test.js` (thresholds,
  backoff, hourly cap, manual-restart lock, reset after recovery).
- Killing the server process by hand: the app restarts it within about 80 s
  and the System card shows the restart.
- No new port literal (`tests/test_ports.py`), ASCII + LF.

## Game ToS

Touches only the EW server process on 127.0.0.1:8940; never the game
process, its window, memory or files.

Depends on: none.

## As-built deviations

1. Signature `next(state, probe, now, opts)`: the manual-restart lock rides
   in an optional 4th argument `{restarting}` instead of a probe value.
   Alternatives: a third probe value `busy`. Why: probe stays the plain
   health result; main passes its existing `restarting` flag as is.
   Reverses if: a caller needs the lock state inside `state`.
2. Order of checks on a fail: backoff first, then the hourly cap. With the
   cap first, the probe right after the 6th restart (still inside its
   backoff) gave up before the 6th restart had a chance to work. Reverses
   if: the operator wants an immediate give-up at the cap.
3. A recovered-then-crashed server inside the same hour gives up again
   (one `give-up` per outage while 6 restarts are in the rolling hour);
   an ok probe always clears gave-up, as the plan says.
4. Surfacing is a pull, not a push: the dashboard reads the summary through
   a new read-only, payload-free, sender-checked `ew:watchdog` invoke on its
   existing 5 s System repaint (the shell IPC allowlist pins in
   `shell.test.js` grew by this one channel). Alternatives: main pushes
   `webContents.send` events. Why: matches every other bridge call (invoke),
   no listener plumbing in the sandboxed preload, survives a dashboard
   reload. The gave-up toast fires on the dashboard's own transition into
   `gave-up` (EWToast, plan 026 path). Reverses if: a 5 s lag matters.
5. No watchdog under `EW_SELFTEST` (the selftest runs without a server on
   purpose; a watchdog would spawn one mid-run).
6. A hung server that holds the port but does not answer /api/version is
   not killed (tray.killablePid needs the EW contract); the respawn then
   fails to bind and the hourly cap ends in `gave-up`. Kept on purpose: the
   watchdog adds no new kill path.
7. Merge with main (plan 136 Loop card): dashboard.js paintSystem keeps both
   calls, `paintLoop()` then `pullWatchdog()`; both functions and both
   System markup nodes (sys-watchdog, sys-loop) retained. Alternatives: fold
   into one painter. Why: independent features, zero behavior change.
   Reverses if: the two cards are merged in the UI.
