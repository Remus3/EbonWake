"""Plan 153 (SERVER-A-05): GET and SSE answer Access-Control-Allow-Origin only
for the dashboard origins - `null` (the Electron dashboard / overlay load from
file://) and the server's own loopback origins - never `*` to any web page."""

import http.client
import threading

import pytest

from server.ew import app as ewapp
from server.ew import market

pytestmark = pytest.mark.server


def _no_network(url, timeout):
    raise AssertionError("test touched the network")


@pytest.fixture()
def srv(tmp_path):
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", commit="a" * 40,
                          sse_interval=0.05, market_seed=[],
                          market_client=market.ArshaClient(fetch=_no_network,
                                                           cache_dir=tmp_path / "cache"),
                          profile_cfg={}, config_path=tmp_path / "local.json")
    t = threading.Thread(target=s.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()
    yield s
    s.shutdown()
    s.server_close()


def _get(s, path, origin=None):
    c = http.client.HTTPConnection("127.0.0.1", s.server_address[1], timeout=5)
    headers = {"Origin": origin} if origin is not None else {}
    c.request("GET", path, headers=headers)
    r = c.getresponse()
    if path != "/api/events":
        r.read()
    out = r.status, r.getheader("Access-Control-Allow-Origin"), r.getheader("Vary")
    c.close()
    return out


def test_foreign_origin_gets_no_allow_origin(srv):
    st, acao, vary = _get(srv, "/api/health", "https://example.com")
    assert st == 200 and acao is None and vary == "Origin"


def test_null_origin_echoed_for_file_dashboard(srv):
    st, acao, vary = _get(srv, "/api/health", "null")
    assert st == 200 and acao == "null" and vary == "Origin"


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
def test_own_loopback_origin_echoed(srv, host):
    own = "http://%s:%d" % (host, srv.server_address[1])
    st, acao, _ = _get(srv, "/api/state", own)
    assert st == 200 and acao == own


def test_loopback_origin_on_other_port_refused(srv):
    other = "http://127.0.0.1:%d" % (srv.server_address[1] + 1)
    assert _get(srv, "/api/health", other)[1] is None


def test_no_origin_header_unchanged(srv):
    st, acao, _ = _get(srv, "/api/health")
    assert st == 200 and acao == "*"


def test_sse_follows_same_rule(srv):
    st, acao, vary = _get(srv, "/api/events", "https://example.com")
    assert st == 200 and acao is None and vary == "Origin"
    st, acao, _ = _get(srv, "/api/events", "null")
    assert st == 200 and acao == "null"
