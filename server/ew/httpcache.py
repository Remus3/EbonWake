"""Shared read-only HTTP cache + backoff (factored from plan 002 for plan 004).

One JSON file per key holding `{fetched_at, data}`, atomic writes, and a
persisted `backoff.json` beside it so restarts honour a running backoff. A
failure backs off `min(30 * 2**n, 1800)` s; a `Pending` answer ("being fetched,
retry later") is transient and retries after a flat PENDING_RETRY_S without
growing n. During backoff or failure the last cache is served `stale: true`
with `error`; no cache -> `data: null`. Read-only GET only (ToS floor).

Plan 139 politeness: a 200's `ETag` / `Last-Modified` are kept in the entry and
sent back as `If-None-Match` / `If-Modified-Since` on the next fetch of that
key; a 304 refreshes `fetched_at`, keeps `data` and clears the backoff. A 429 /
503 `Retry-After` (seconds or HTTP date) stretches the backoff to
`min(max(generic, retry_after), BACKOFF_MAX_S)`. Only `default_fetch` speaks
this; an injected or module-own fetch never takes the path. The cache hands
validators to the fetch through a per-thread context, so every caller's
`fetch(url, timeout) -> bytes` shape is unchanged.
"""

import datetime as _dt
import email.utils
import json
import math
import threading
import time
import urllib.error
import urllib.request
from collections import namedtuple
from pathlib import Path

from . import __version__
from .store import atomic_write_json

BACKOFF_BASE_S = 30
BACKOFF_MAX_S = 1800
PENDING_RETRY_S = 60
BACKOFF_N_MAX = 16  # 30 * 2 ** 6 already passes BACKOFF_MAX_S; caps the bigint (plan 142)


def backoff_wait(n):
    """Generic backoff after the n-th consecutive failure (n clamped to
    0..BACKOFF_N_MAX, so a corrupt huge n never builds a giant int)."""
    n = max(0, min(int(n), BACKOFF_N_MAX))
    return min(BACKOFF_BASE_S * 2 ** n, BACKOFF_MAX_S)


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


class UpstreamError(Exception):
    pass


class Pending(UpstreamError):
    """Upstream accepted the request but has no data yet (HTTP 202)."""


def iso(epoch):
    if epoch is None:
        return None
    return _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc).replace(microsecond=0).isoformat()


class NotModified(UpstreamError):
    """HTTP 304 to a conditional GET: the cached data is still current."""


FetchResult = namedtuple("FetchResult", "status headers body")
RETRY_AFTER_STATUS = (429, 503)
_ctx = threading.local()  # .cond = _Cond while a cached_get download runs


class _Cond:
    """Validators in, response facts out, for the first default_fetch of one
    download (a second GET to another URL in the same download is plain)."""

    def __init__(self, etag=None, last_modified=None):
        self.etag = etag
        self.last_modified = last_modified
        self.url = None
        self.not_modified = False
        self.etag_out = None
        self.last_modified_out = None
        self.retry_after = None


def _lower(headers):
    try:
        return {str(k).lower(): v for k, v in (headers or {}).items()}
    except AttributeError:
        return {}


def _str_or_none(v):
    return v if isinstance(v, str) and v else None


def fetch_result(url, timeout, headers=None, opener=None):
    """Plain GET -> FetchResult(status, lower-cased headers, body). A 304 is a
    result, not an error; any other HTTP error raises. `opener` stands in for
    urlopen (tests, no socket)."""
    h = {"User-Agent": f"Ebonwake/{__version__}", "Accept": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, method="GET", headers=h)
    try:
        with (opener or urllib.request.urlopen)(req, timeout=timeout) as r:  # noqa: S310 (fixed https bases)
            return FetchResult(r.status, _lower(r.headers), r.read())
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return FetchResult(304, _lower(e.headers), b"")
        raise


def default_fetch(url, timeout, opener=None):
    """Plain GET -> body bytes; raises on HTTP error or timeout, Pending on
    HTTP 202, NotModified on 304. Inside cached_get the first call sends the
    key's stored validators and reports the response validators / Retry-After."""
    cond = getattr(_ctx, "cond", None)
    if cond is not None and cond.url is None:
        cond.url = url
    mine = cond is not None and cond.url == url
    headers = {}
    if mine and cond.etag:
        headers["If-None-Match"] = cond.etag
    if mine and cond.last_modified:
        headers["If-Modified-Since"] = cond.last_modified
    try:
        res = fetch_result(url, timeout, headers, opener)
    except urllib.error.HTTPError as e:
        if mine and e.code in RETRY_AFTER_STATUS:
            cond.retry_after = _lower(e.headers).get("retry-after")
        raise
    if res.status == 304:
        if mine:
            cond.not_modified = True
        raise NotModified("304 not modified")
    if res.status == 202:
        raise Pending("being fetched, retry later")
    if mine:
        cond.etag_out = _str_or_none(res.headers.get("etag"))
        cond.last_modified_out = _str_or_none(res.headers.get("last-modified"))
    return res.body


def retry_after_s(value, now):
    """Seconds to wait from a Retry-After value (delta seconds or HTTP date; a
    past date = 0), or None when missing or garbage."""
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip()
    if v.isascii() and v.isdigit():  # plan 142: "\xb2" (latin-1) isdigit() but int() raises
        return int(v)
    try:
        when = email.utils.parsedate_to_datetime(v)
    except (TypeError, ValueError, IndexError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=_dt.timezone.utc)
    return max(0, int(when.timestamp() - now))


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def freshness(res):
    return {k: res[k] for k in ("fetched_at", "age_s", "ttl_s", "stale", "error")}


def _daemon(fn):
    threading.Thread(target=fn, name="ew-refresh", daemon=True).start()


class CachedClient:
    # Plan 142: the longest backoff this client ever sets; a stored `until`
    # further out than this from now was written before the clock moved back.
    backoff_horizon_s = max(BACKOFF_MAX_S, PENDING_RETRY_S)

    def __init__(self, fetch=None, clock=time.time, cache_dir=None):
        if cache_dir is None:
            raise ValueError("cache_dir is required")
        self.fetch = fetch or default_fetch
        self.clock = clock
        self.cache_dir = Path(cache_dir)
        self._lock = threading.Lock()      # guards _keylocks
        self._bo_lock = threading.Lock()   # guards backoff.json read-modify-write
        self._keylocks = {}
        self._inflight = set()             # keys with a background refresh running
        # Plan 139: since-start counters for /api/health.
        self.stats = {"hits_304": 0, "retry_after_honoured": 0}

    def _count(self, name):
        with self._lock:
            self.stats[name] += 1

    def _keylock(self, key):
        with self._lock:
            return self._keylocks.setdefault(key, threading.Lock())

    # -- paths / state ----------------------------------------------------
    def _cache_path(self, key):
        return self.cache_dir / f"{key}.json"

    def _backoff_path(self):
        return self.cache_dir / "backoff.json"

    def _backoffs(self):
        with self._bo_lock:
            doc = read_json(self._backoff_path())
        return doc if isinstance(doc, dict) else {}

    def key_backoff(self, key):
        bo = self._backoffs().get(key, {})
        if not (isinstance(bo, dict) and isinstance(bo.get("n", 0), int)
                and not isinstance(bo.get("n", 0), bool) and _finite(bo.get("until", 0))):
            return {}  # corrupt entry = no backoff, never a 500
        if bo:
            bo = dict(bo, n=max(0, min(bo.get("n", 0), BACKOFF_N_MAX)))
            if bo.get("until", 0) > self.clock() + self.backoff_horizon_s:
                bo["until"] = 0  # set before the clock moved back: expired (plan 142)
        return bo

    def _set_backoff(self, key, entry):
        with self._bo_lock:
            doc = read_json(self._backoff_path())
            doc = doc if isinstance(doc, dict) else {}
            if entry:
                doc[key] = entry
            else:
                doc.pop(key, None)
            atomic_write_json(self._backoff_path(), doc)

    def _cached(self, key):
        cached = read_json(self._cache_path(key))
        if not (isinstance(cached, dict) and "data" in cached
                and _finite(cached.get("fetched_at"))):
            return None  # corrupt cache = no cache
        return cached

    @staticmethod
    def _fresh(cached, now, ttl):
        """A stamp from the future (the clock moved back) is stale, not fresh
        until the clock catches up (plan 142)."""
        return bool(cached) and 0 <= now - cached["fetched_at"] < ttl

    # -- core -------------------------------------------------------------
    def cached_get(self, key, ttl, download):
        """`download()` returns the data or raises UpstreamError / Pending."""
        # Per-key lock: one in-flight fetch per key (dedupe); other keys and
        # fresh-cache reads never wait behind a slow upstream.
        with self._keylock(key):
            now = self.clock()
            cached = self._cached(key)
            if self._fresh(cached, now, ttl):
                return self._result(cached, now, ttl, False, None)
            bo = self.key_backoff(key)
            if bo and now < bo.get("until", 0):
                return self._result(cached, now, ttl, True, bo.get("error") or "backoff")
            n = int(bo.get("n", 0)) if bo else 0
            cond = _Cond(_str_or_none(cached.get("etag")),
                         _str_or_none(cached.get("last_modified"))) if cached else _Cond()
            prev, _ctx.cond = getattr(_ctx, "cond", None), cond
            try:
                data = download()
            except Pending as e:
                err = str(e)
                self._set_backoff(key, {"n": n, "until": now + PENDING_RETRY_S, "error": err,
                                        "pending": True})
                return self._result(cached, now, ttl, True, err)
            except UpstreamError as e:
                # A 304 arrives wrapped by the caller's download; the flag says it.
                if cond.not_modified and cached:
                    entry = dict(cached, fetched_at=now)
                    atomic_write_json(self._cache_path(key), entry)
                    if bo:
                        self._set_backoff(key, None)
                    self._count("hits_304")
                    return self._result(entry, now, ttl, False, None)
                wait = backoff_wait(n)
                ra = retry_after_s(cond.retry_after, now)
                if ra is not None:
                    wait = max(wait, ra)
                    self._count("retry_after_honoured")
                wait = min(wait, BACKOFF_MAX_S)
                err = str(e)
                self._set_backoff(key, {"n": n + 1, "until": now + wait, "error": err})
                return self._result(cached, now, ttl, True, err)
            finally:
                _ctx.cond = prev
            entry = {"fetched_at": now, "data": data}
            if cond.etag_out:
                entry["etag"] = cond.etag_out
            if cond.last_modified_out:
                entry["last_modified"] = cond.last_modified_out
            atomic_write_json(self._cache_path(key), entry)
            if bo:
                self._set_backoff(key, None)
            return self._result(entry, now, ttl, False, None)

    def refreshing(self, key):
        with self._lock:
            return key in self._inflight

    def refresh_async(self, key, ttl, download, spawn=None):
        """Start `cached_get` off the caller's thread unless one is already in
        flight for `key` or the cache is fresh. Returns True when one started.
        `spawn(fn)` is injectable (tests); default is a daemon thread."""
        cached = self._cached(key)
        if self._fresh(cached, self.clock(), ttl):
            return False
        with self._lock:
            if key in self._inflight:
                return False
            self._inflight.add(key)

        def run():
            try:
                self.cached_get(key, ttl, download)
            except Exception:  # noqa: BLE001 - a refresh failure never kills the server
                pass
            finally:
                with self._lock:
                    self._inflight.discard(key)

        try:
            (spawn or _daemon)(run)
        except Exception:  # noqa: BLE001 - no thread = serve the cache, never a 500
            with self._lock:
                self._inflight.discard(key)
            return False
        return True

    def pending(self, key):
        """True while a refresh is running or upstream said "being fetched"."""
        if self.refreshing(key):
            return True
        bo = self.key_backoff(key)
        return bool(bo.get("pending")) and self.clock() < bo.get("until", 0)

    def peek(self, key, ttl):
        """Cache/backoff view without fetching, or None when nothing is known."""
        now = self.clock()
        cached = self._cached(key)
        bo = self.key_backoff(key)
        if not cached and not bo:
            return None
        stale = not self._fresh(cached, now, ttl)
        return self._result(cached, now, ttl, stale, bo.get("error") if bo else None)

    @staticmethod
    def _result(entry, now, ttl, stale, error):
        if not entry:
            return {"data": None, "fetched_at": None, "age_s": None, "ttl_s": ttl,
                    "stale": True, "error": error}
        return {"data": entry["data"], "fetched_at": iso(entry["fetched_at"]),
                "age_s": max(0, int(now - entry["fetched_at"])), "ttl_s": ttl, "stale": stale,
                "error": error}
