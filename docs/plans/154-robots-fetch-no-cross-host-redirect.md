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

## As-built

- `server/ew/httpcache.py`: `same_origin_open(req, timeout)` (an opener with
  `_SameOriginRedirect`) and `same_origin_fetch` (= `default_fetch` through it,
  so plan 139 validators / Retry-After still work).
- coupons, bossdrift, eventnotices `default_fetch` use `same_origin_open`;
  `progress.ProfileClient` defaults to `same_origin_fetch`.
- Tests: `tests/test_redirect_guard.py` (two loopback servers; 7 cases red
  before the fix, all green after).

## As-built deviations

1. Origin, not host. Decision: a redirect must keep scheme, host and port
   (default ports filled in). Alternatives: compare hostname only (the plan's
   wording). Why: robots.txt is per origin (RFC 9309), and two loopback
   servers on different ports are the only socket-level test of "another
   host". Reverses if: a gated source is seen to redirect http -> https or to
   another port on the same host and the feature goes dark.
2. Sweep result: `progress.ProfileClient` (robots-gated self-hosted base) got
   the guard too. Market (arsha.io, `httpcache.default_fetch`) and
   `single.probe` (loopback) are not robots-gated and keep plain urlopen.
   Alternatives: guard every `httpcache.default_fetch`. Why: the plan scopes
   the fix to robots-gated fetchers; an un-gated API following a CDN redirect
   is not a robots question. Reverses if: arsha.io is ever robots-gated.
3. The lane could not write its progress file
   (`ops/loop/control/progress/p154-build.json`): the write outside the
   worktree and running a scratch writer were denied by the run's
   permissions. Alternatives: none inside this run. Why: permission floor.
   Reverses if: the lane permissions allow the kit `write_progress` call.
