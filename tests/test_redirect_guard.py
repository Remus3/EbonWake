"""Plan 154 (SERVER-A-06): robots-gated fetchers refuse cross-origin redirects.

robots.txt is checked for the configured host only, so a 3xx to another origin
would GET a page no robots verdict covered. Two loopback HTTP servers on
different ports are two origins: a redirect from A to B is refused before any
request reaches B (the fetch raises, the module's normal failure); a redirect
within A still works.
"""

import http.server
import threading
import urllib.error
import urllib.request

import pytest

from server.ew import bossdrift, coupons, eventnotices, httpcache, progress

pytestmark = pytest.mark.server


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib hook name)
        self.server.hits.append(self.path)
        target = self.server.routes.get(self.path)
        if target is not None:
            self.send_response(302)
            self.send_header("Location", target)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = b"page " + self.path.encode("ascii")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _serve():
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    s.hits, s.routes = [], {}
    # A short poll: shutdown() otherwise waits out the 0.5 s default per server.
    threading.Thread(target=s.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
    return s


@pytest.fixture
def pair():
    a, b = _serve(), _serve()
    a.base = f"http://127.0.0.1:{a.server_address[1]}"
    b.base = f"http://127.0.0.1:{b.server_address[1]}"
    a.routes["/off"] = b.base + "/x"
    a.routes["/same"] = "/landed"
    a.routes["/same-abs"] = a.base + "/landed"
    yield a, b
    for s in (a, b):
        s.shutdown()
        s.server_close()


def _profile_fetch(tmp_path):
    return progress.ProfileClient("Fam", base_url="https://example.invalid",
                                  cache_dir=tmp_path).fetch


FETCHERS = {
    "coupons": lambda tmp_path: coupons.default_fetch,
    "bossdrift": lambda tmp_path: bossdrift.default_fetch,
    "eventnotices": lambda tmp_path: eventnotices.default_fetch,
    "profile": _profile_fetch,
}


def _open(url, timeout):
    req = urllib.request.Request(url, method="GET")
    with httpcache.same_origin_open(req, timeout) as r:
        return r.read()


@pytest.mark.parametrize("name", sorted(FETCHERS))
def test_cross_origin_redirect_refused(pair, tmp_path, name):
    a, b = pair
    fetch = FETCHERS[name](tmp_path)
    with pytest.raises(urllib.error.URLError):
        fetch(a.base + "/off", 5)
    assert a.hits == ["/off"] and b.hits == []


@pytest.mark.parametrize("name", sorted(FETCHERS))
@pytest.mark.parametrize("path", ["/same", "/same-abs"])
def test_same_origin_redirect_followed(pair, tmp_path, name, path):
    a, b = pair
    fetch = FETCHERS[name](tmp_path)
    assert fetch(a.base + path, 5) == b"page /landed"
    assert a.hits == [path, "/landed"] and b.hits == []


def test_helper_refuses_other_host_name(pair):
    a, b = pair
    a.routes["/host"] = f"http://localhost:{a.server_address[1]}/x"
    with pytest.raises(urllib.error.HTTPError) as e:
        _open(a.base + "/host", 5)
    assert e.value.code == 302 and "cross-origin redirect refused" in str(e.value)
    assert a.hits == ["/host"]


def test_helper_plain_get(pair):
    a, _ = pair
    assert _open(a.base + "/plain", 5) == b"page /plain"


def test_robots_verdict_unreachable_on_off_origin_redirect(pair):
    a, b = pair
    a.routes["/robots.txt"] = b.base + "/robots.txt"
    verdict = coupons.robots_verdict(coupons.default_fetch, urls=(a.base + "/page",),
                                     robots_url=a.base + "/robots.txt")
    assert verdict == "unreachable" and b.hits == []
