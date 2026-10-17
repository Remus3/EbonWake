"""Shared test helpers (plan 156, TESTS-A-17).

Test modules import these from here instead of from another test module: a
`from tests.test_x import ...` loaded that test module a second time under a
second name (no tests/__init__.py), ran its module code twice and coupled the
two test files. tests/ is on sys.path (conftest), so `import ew_testkit`."""

import http.client
import json
import struct

from server.ew import gamewatch

T0 = 1_800_000_000.0
CHAR_A = "12345678901234567"
CHAR_B = "76543210987654321"


def _no_network(url, timeout):
    raise AssertionError("test touched the network")


def offline_market(tmp_path):
    """A market client that never fetches and caches under tmp_path (plan 157:
    a test server never falls back to the live ops/runtime market cache)."""
    from server.ew import market

    return market.ArshaClient(fetch=_no_network, cache_dir=tmp_path / "mcache")


def _get(s, path, host=None):
    port = s.server_address[1]
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Host": host} if host else {}
    c.request("GET", path, headers=headers)
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, r.getheader("Content-Type"), body


def _post(s, path, body, ctype="application/json", host=None, extra=None):
    port = s.server_address[1]
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": ctype} if ctype else {}
    if host:
        headers["Host"] = host
    headers.update(extra or {})
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    c.request("POST", path, body=data, headers=headers)
    r = c.getresponse()
    out = r.read()
    c.close()
    return r.status, (json.loads(out) if out else None)


class Clock:
    def __init__(self, t=T0):
        self.t = float(t)

    def __call__(self):
        return self.t


def bmp(w, h, bpp=32, top_down=False, pixel=lambda x, y: (x * 10 % 256, y * 20 % 256, 77)):
    """Tiny BI_RGB BMP; rows bottom-up unless `top_down`. pixel -> (r, g, b)."""
    stride = ((w * bpp + 31) // 32) * 4
    rows = []
    for y in range(h):
        row = bytearray()
        for x in range(w):
            r, g, b = pixel(x, y)
            row += bytes((b, g, r)) + (b"\xff" if bpp == 32 else b"")
        rows.append(bytes(row) + b"\x00" * (stride - len(row)))
    body = b"".join(rows if top_down else reversed(rows))
    off = 14 + 40
    head = b"BM" + struct.pack("<IHHI", off + len(body), 0, 0, off)
    dib = struct.pack("<IiiHHIIiiII", 40, w, -h if top_down else h, 1, bpp, 0, len(body),
                      2835, 2835, 0, 0)
    return head + dib + body


class FakeWatch(gamewatch.GameWatch):
    """Unconfigured GameWatch whose state is set by the test."""

    def __init__(self, clock):
        super().__init__(None, None, clock=clock, tasklist=lambda: False)
        self.forced = None

    def poll(self):
        now = self.clock()
        with self._lock:
            prev, state = self._state, self.forced
            changed = state != prev
            if changed:
                self._state, self._since = state, now
                self.seq += 1
                self._cond.notify_all()
        if changed:
            for fn in list(self.listeners):
                fn(prev, state, now)
        return state
