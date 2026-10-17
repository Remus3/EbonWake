# Plan 139 - Upstream fetch politeness: conditional GET (ETag / Last-Modified) and Retry-After backoff

Status: open. Source: research 0029 finding B2 (plan 134). Lane hint:
`data`.

Problem: `server/ew/httpcache.py` stores `{fetched_at, data}` only, so every
TTL expiry (`server/ew/market.py:23`, `server/ew/progress.py:40`) is a full
GET, and a 429 / 503 gets the generic `min(30 * 2**n, 1800)` backoff that
ignores the server's `Retry-After`.

## Slices

0. Measure (one read-only GET each, robots.txt respected, recorded here with
   the date): does arsha.io v2 (`na`) and the configured BDO-REST-API base
   send `ETag` and / or `Last-Modified`, and do they answer a conditional GET
   with 304? If neither validator is sent, slice 2 ships dormant (code path
   tested, never taken live) and the doc says so.
1. Tests first in `tests/test_httpcache.py` with a fake fetch (no socket):
   - cache entry gains optional `etag` and `last_modified`; old entries
     without them still load.
   - with a validator stored, the request carries `If-None-Match` /
     `If-Modified-Since`; a 304 refreshes `fetched_at`, keeps `data`, resets
     the backoff and counts as a hit.
   - 429 / 503 with `Retry-After` (seconds or HTTP date) -> backoff until
     `max(generic, retry_after)`, capped at `BACKOFF_MAX_S`; a missing or
     garbage header falls back to the generic rule.
   - a 200 with a new validator replaces the stored one.
2. `default_fetch` returns status, headers and body through a small result
   object; the existing callers keep their return shape (wrapper), so
   `market.py` and `progress.py` need no logic change.
3. `GET /api/health` (or the Signal health card source) reports per-cache
   `hits_304` and `retry_after_honoured` counters since start.

## Acceptance

- `tests/test_httpcache.py` and the market / progress tests green; ruff green.
- Read-only GET only; no new host; User-Agent unchanged.

## Game ToS

Read-only public GETs to the already allowed arsha.io and BDO-REST-API
sources; nothing reaches the game client.

Depends on: none.

## As-built (2026-10-17)

- `server/ew/httpcache.py`: `fetch_result(url, timeout, headers, opener)` ->
  `FetchResult(status, headers, body)` (a 304 is a result, not an error);
  `default_fetch(url, timeout, opener=None)` keeps the bytes return shape and
  adds `NotModified` (an `UpstreamError`) on 304. `cached_get` hands the stored
  `etag` / `last_modified` to the fetch through a per-thread context; the first
  `default_fetch` of a download sends `If-None-Match` / `If-Modified-Since` and
  reports back the response validators, a 304, or a 429 / 503 `Retry-After`.
  A 304 (even wrapped by the caller's own `UpstreamError`) refreshes
  `fetched_at`, keeps `data` and the validators, clears the backoff and counts
  `hits_304`. A failure backs off `min(max(30 * 2**n, retry_after),
  BACKOFF_MAX_S)`; a valid header counts `retry_after_honoured`. A 200 replaces
  both validators (a missing one is dropped). Old entries load unchanged.
- `market.py` / `progress.py`: no change.
- `GET /api/health` gains `upstream: {market, profile}`, each
  `{hits_304, retry_after_honoured}` since start, or null when that client is
  not configured.
- Tests: `tests/test_httpcache.py` (fake `opener`, no socket),
  `tests/test_server.py::test_health_upstream_counters`.

## As-built deviations

1. Slice 0 measurement not taken in the build lane.
   Decision: ship the conditional-GET path generically; whether arsha.io v2 /
   the BDO-REST-API base send `ETag` / `Last-Modified` stays unmeasured, and
   the path is dormant for any host that sends neither (the
   `upstream.*.hits_304` health counter staying 0 is the live measurement).
   Alternatives: block the plan on a measurement; hard-code per-host
   behaviour. Why: the headless lane has no outbound network grant (the
   read-only GET was refused by the permission layer), the code is correct
   either way and costs nothing when no validator is sent. Reverses if: a
   session measures a host that answers a conditional GET wrongly (e.g. a 304
   to a changed resource), then that host's validators are not stored.
2. Validators flow through a thread-local context, not a new `fetch`
   signature. Decision: `cached_get` sets the context; only the module
   `default_fetch` reads it, and only for the first URL a download fetches.
   Alternatives: change every `fetch(url, timeout)` caller and fake to accept
   headers and return a result object. Why: the plan requires callers keep
   their shape; about 10 modules and many test fakes use the two-argument
   fetch. Module-own fetches (coupons, eventnotices, bossdrift) never take the
   path. Reverses if: a download needs validators on more than one URL.
