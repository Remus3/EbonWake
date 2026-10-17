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
