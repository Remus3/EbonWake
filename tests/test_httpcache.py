"""Plan 139: upstream fetch politeness in httpcache - conditional GET (ETag /
Last-Modified -> 304) and Retry-After backoff on 429 / 503.

No socket: `default_fetch` gets a fake `opener` standing in for urlopen, so the
real request / header / status path runs offline.
"""

import email.utils
import functools
import io
import json
import urllib.error

from server.ew import __version__, httpcache, market

URL = "https://api.arsha.io/v2/na/GetWorldMarketHotList?lang=en"


class Clock:
    def __init__(self, t=2_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


class Resp:
    def __init__(self, status, body=b"", headers=None):
        self.status = status
        self.headers = headers or {}
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Opener:
    """Fake urlopen: replies pop in order; each is (status, body, headers)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append({k.lower(): v for k, v in req.header_items()})
        status, body, headers = self.replies.pop(0)
        if status >= 300:
            raise urllib.error.HTTPError(req.full_url, status, "x", headers,
                                         io.BytesIO(body))
        return Resp(status, body, headers)


def _client(tmp_path, opener, clock=None):
    fetch = functools.partial(httpcache.default_fetch, opener=opener)
    return httpcache.CachedClient(fetch=fetch, clock=clock or Clock(), cache_dir=tmp_path)


def _dl(c):
    """Same wrapping as market.py / progress.py: any fetch error -> UpstreamError."""
    def download():
        try:
            raw = c.fetch(URL, 10)
        except httpcache.Pending:
            raise
        except Exception as e:  # noqa: BLE001
            raise httpcache.UpstreamError(f"{type(e).__name__}: {e}") from e
        return json.loads(raw)
    return download


def _cache(tmp_path, key="k"):
    return json.loads((tmp_path / f"{key}.json").read_text(encoding="utf-8"))


# -- validators stored --------------------------------------------------------

def test_200_stores_validators(tmp_path):
    op = Opener((200, b'{"a": 1}', {"ETag": '"v1"', "Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT"}))
    c = _client(tmp_path, op)
    res = c.cached_get("k", 60, _dl(c))
    assert res["data"] == {"a": 1} and res["stale"] is False
    doc = _cache(tmp_path)
    assert doc["etag"] == '"v1"'
    assert doc["last_modified"] == "Wed, 01 Jan 2025 00:00:00 GMT"
    # first request is unconditional; User-Agent unchanged
    assert "if-none-match" not in op.requests[0]
    assert op.requests[0]["user-agent"] == f"Ebonwake/{__version__}"


def test_200_without_validators_stores_none(tmp_path):
    c = _client(tmp_path, Opener((200, b"[1]", {})))
    c.cached_get("k", 60, _dl(c))
    doc = _cache(tmp_path)
    assert "etag" not in doc and "last_modified" not in doc


def test_old_entry_without_validators_loads(tmp_path):
    clk = Clock()
    (tmp_path / "k.json").write_text(json.dumps({"fetched_at": clk.t - 10, "data": [7]}),
                                     encoding="utf-8")
    op = Opener()
    c = _client(tmp_path, op, clk)
    assert c.cached_get("k", 60, _dl(c))["data"] == [7]
    clk.t += 100
    op.replies.append((200, b"[8]", {}))
    assert c.cached_get("k", 60, _dl(c))["data"] == [8]
    assert "if-none-match" not in op.requests[0]
    assert "if-modified-since" not in op.requests[0]


# -- conditional GET -> 304 ---------------------------------------------------

def test_conditional_request_and_304_hit(tmp_path):
    clk = Clock()
    lm = "Wed, 01 Jan 2025 00:00:00 GMT"
    op = Opener((200, b'{"a": 1}', {"ETag": '"v1"', "Last-Modified": lm}),
                (304, b"", {}))
    c = _client(tmp_path, op, clk)
    c.cached_get("k", 60, _dl(c))
    clk.t += 120
    res = c.cached_get("k", 60, _dl(c))
    assert op.requests[1]["if-none-match"] == '"v1"'
    assert op.requests[1]["if-modified-since"] == lm
    assert res["data"] == {"a": 1} and res["stale"] is False and res["error"] is None
    assert res["age_s"] == 0
    doc = _cache(tmp_path)
    assert doc["fetched_at"] == clk.t and doc["etag"] == '"v1"'
    assert c.stats["hits_304"] == 1
    # refreshed: the next call inside the TTL does not fetch
    clk.t += 30
    assert c.cached_get("k", 60, _dl(c))["data"] == {"a": 1}
    assert len(op.requests) == 2


def test_304_resets_backoff(tmp_path):
    clk = Clock()
    op = Opener((200, b"[1]", {"ETag": '"v1"'}), (500, b"", {}), (304, b"", {}))
    c = _client(tmp_path, op, clk)
    c.cached_get("k", 60, _dl(c))
    clk.t += 120
    assert c.cached_get("k", 60, _dl(c))["stale"] is True
    assert c.key_backoff("k")["n"] == 1
    clk.t += httpcache.BACKOFF_BASE_S + 1
    res = c.cached_get("k", 60, _dl(c))
    assert res["stale"] is False and res["data"] == [1]
    assert c.key_backoff("k") == {}


def test_200_new_validator_replaces_old(tmp_path):
    clk = Clock()
    op = Opener((200, b"[1]", {"ETag": '"v1"', "Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT"}),
                (200, b"[2]", {"ETag": '"v2"'}))
    c = _client(tmp_path, op, clk)
    c.cached_get("k", 60, _dl(c))
    clk.t += 120
    assert c.cached_get("k", 60, _dl(c))["data"] == [2]
    doc = _cache(tmp_path)
    assert doc["etag"] == '"v2"' and "last_modified" not in doc
    assert c.stats["hits_304"] == 0


def test_conditional_only_on_first_fetch_of_download(tmp_path):
    """A download doing a second GET (another URL) never sends the stored
    validators there."""
    clk = Clock()
    op = Opener((200, b"[1]", {"ETag": '"v1"'}), (200, b"[2]", {}), (200, b"[3]", {}))
    c = _client(tmp_path, op, clk)
    c.cached_get("k", 60, _dl(c))
    clk.t += 120

    def two():
        c.fetch(URL, 10)
        return json.loads(c.fetch(URL + "&other=1", 10))
    c.cached_get("k", 60, two)
    assert op.requests[1]["if-none-match"] == '"v1"'
    assert "if-none-match" not in op.requests[2]


def test_market_client_304_through_wrapper(tmp_path):
    """market.py's _download wraps every fetch error; a 304 still counts as a hit."""
    clk = Clock()
    hot = [{"id": 1, "sid": 0}]
    op = Opener((200, json.dumps(hot).encode(), {"ETag": '"h"'}), (304, b"", {}))
    c = market.ArshaClient(fetch=functools.partial(httpcache.default_fetch, opener=op),
                           clock=clk, cache_dir=tmp_path)
    assert c.get("hot")["data"] == hot
    clk.t += market.TTL["hot"] + 1
    res = c.get("hot")
    assert res["data"] == hot and res["stale"] is False
    assert c.stats["hits_304"] == 1


# -- Retry-After --------------------------------------------------------------

def _fail_once(tmp_path, status, headers, clk=None):
    clk = clk or Clock()
    c = _client(tmp_path, Opener((status, b"", headers)), clk)
    res = c.cached_get("k", 60, _dl(c))
    return c, clk, res


def test_429_retry_after_seconds(tmp_path):
    c, clk, res = _fail_once(tmp_path, 429, {"Retry-After": "600"})
    assert res["stale"] is True
    assert c.key_backoff("k")["until"] - clk.t == 600
    assert c.stats["retry_after_honoured"] == 1


def test_503_retry_after_http_date(tmp_path):
    clk = Clock()
    when = email.utils.formatdate(clk.t + 900, usegmt=True)
    c, clk, _ = _fail_once(tmp_path, 503, {"Retry-After": when}, clk)
    assert c.key_backoff("k")["until"] - clk.t == 900
    assert c.stats["retry_after_honoured"] == 1


def test_retry_after_below_generic_keeps_generic(tmp_path):
    c, clk, _ = _fail_once(tmp_path, 429, {"Retry-After": "5"})
    assert c.key_backoff("k")["until"] - clk.t == httpcache.BACKOFF_BASE_S


def test_retry_after_capped(tmp_path):
    c, clk, _ = _fail_once(tmp_path, 429, {"Retry-After": "999999"})
    assert c.key_backoff("k")["until"] - clk.t == httpcache.BACKOFF_MAX_S


def test_retry_after_missing_or_garbage_falls_back(tmp_path):
    for i, headers in enumerate(({}, {"Retry-After": "soon"}, {"Retry-After": "-5"})):
        d = tmp_path / str(i)
        c, clk, _ = _fail_once(d, 503, headers)
        assert c.key_backoff("k")["until"] - clk.t == httpcache.BACKOFF_BASE_S
        assert c.stats["retry_after_honoured"] == 0


def test_retry_after_ignored_on_other_status(tmp_path):
    c, clk, _ = _fail_once(tmp_path, 500, {"Retry-After": "600"})
    assert c.key_backoff("k")["until"] - clk.t == httpcache.BACKOFF_BASE_S


def test_parse_retry_after():
    assert httpcache.retry_after_s("120", 0) == 120
    assert httpcache.retry_after_s(" 7 ", 0) == 7
    assert httpcache.retry_after_s(None, 0) is None
    assert httpcache.retry_after_s("", 0) is None
    assert httpcache.retry_after_s("garbage", 0) is None
    past = email.utils.formatdate(1000, usegmt=True)
    assert httpcache.retry_after_s(past, 5000) == 0


def test_default_fetch_plain_shape(tmp_path):
    """Callers keep the bytes return shape; 202 still raises Pending."""
    op = Opener((200, b"raw", {}), (202, b"", {}))
    assert httpcache.default_fetch(URL, 10, opener=op) == b"raw"
    try:
        httpcache.default_fetch(URL, 10, opener=op)
    except httpcache.Pending:
        pass
    else:
        raise AssertionError("202 must raise Pending")


def test_fetch_result_object():
    op = Opener((200, b"x", {"ETag": '"e"'}))
    r = httpcache.fetch_result(URL, 10, opener=op)
    assert r.status == 200 and r.body == b"x" and r.headers["etag"] == '"e"'
