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
