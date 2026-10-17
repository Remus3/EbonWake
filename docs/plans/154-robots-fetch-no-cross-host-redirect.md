# Plan 154 - Robots-gated fetchers refuse cross-host redirects

Status: open (follow-on of the 20261017 hardening audit, session 36). Source:
SERVER-A-06 (docs/audit/20261017-server-a.md). Lane hint: `build`.

## Problem

`default_fetch` in bossdrift, coupons and eventnotices uses plain `urlopen`, which follows 3xx redirects to any host; robots.txt is checked only for the configured host, so an off-host redirect would GET a page no robots verdict covered.

## Slices

1. Tests first (@pytest.mark.server, loopback HTTP server): a 302 to another host is refused (no request reaches the second host, the fetch returns the module's normal failure); a same-host redirect still works.
2. Fix: one shared no-cross-host redirect handler (server/ew/httpcache.py or a small helper) used by every robots-gated default_fetch; sweep server/ew for other urlopen users and apply it where robots gating applies.

## Acceptance

Each slice's test failed before the fix and passes after; ruff, touched tests
and (if app/ changed) npm test green; ASCII / LF; the audit doc row for each
source ID is updated to FIXED with this plan number.

Depends on: 141, 139.
