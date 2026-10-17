# Plan 153 - CORS: answer GET / SSE only for the dashboard origins

Status: open (follow-on of the 20261017 hardening audit, session 36). Source:
SERVER-A-05 (docs/audit/20261017-server-a.md). Lane hint: `build`.

## Problem

Every GET and the SSE stream answer `Access-Control-Allow-Origin: *`, so any web page open in the operator's browser can read http://127.0.0.1:8940/api/* cross-origin (settings, character, folder paths). The Host check stops DNS rebinding but not this.

## Slices

1. Tests first (tests/test_cors_origins.py, @pytest.mark.server): a GET with `Origin: https://example.com` gets no Allow-Origin header; `Origin: null` (dashboard from file://) and the server's own origin `http://127.0.0.1:<port>` are echoed back; no Origin header stays unchanged; SSE /api/events follows the same rule.
2. Fix in server/ew/app.py: one helper decides the header from the request Origin against an allowlist (null, the server's own 127.0.0.1 / localhost origins); `Vary: Origin` added.
3. Check app/main.js and app/overlay load paths so the Electron dashboard and overlay origins are on the allowlist (node test if any JS changes).

## Acceptance

Each slice's test failed before the fix and passes after; ruff, touched tests
and (if app/ changed) npm test green; ASCII / LF; the audit doc row for each
source ID is updated to FIXED with this plan number.

Depends on: 141.

## As-built deviations

- No Origin header keeps `Access-Control-Allow-Origin: *` (slice 1 "stays
  unchanged"). A header-less request is never a cross-origin browser read, so
  `*` exposes nothing. Alternatives: omit the header. Why: plan text, zero
  change for curl / same-origin / Electron. Reverses if: a browser path is found
  that reads cross-origin without sending Origin.
- Allowlist = `null` plus `http://<h>:<port>` for every LOOPBACK_HOSTS name
  (127.0.0.1, localhost, [::1]) on the server's own bound port; a loopback origin
  on another port is refused. Alternatives: any loopback port. Why: other local
  servers are other apps. Reverses if: the dashboard moves to an http origin on
  another port.
- `Origin: null` is also what a sandboxed iframe on any page sends; accepted
  residual risk because the Electron dashboard and overlay both use loadFile
  (app/main.js) and need it. No app/ change. Reverses if: the dashboard is
  served over http from the EW port (then drop `null`).
- Audit's live-app check not run in this lane (headless, no Electron); covered
  by the `null` echo test.
