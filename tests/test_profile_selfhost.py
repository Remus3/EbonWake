"""Plan 119: self-hosted BDO-REST-API checker / wirer (tools/profile_selfhost.py).

No network, no socket: fetch and connect are injected fakes.
"""

import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import profile_selfhost as ps  # noqa: E402

from server.ew import progress  # noqa: E402

FAMILY = "Testfam"
PUBLIC = "https://api.example.org/community/v1"
ALLOW = b"User-agent: *\nDisallow: /MyPage/\nDisallow: /CS/QNA/\nDisallow: /InGame/\n"
DENY = b"User-agent: *\nDisallow: /en-US/Adventure\n"
NOW = 2_000_000_000.0


class Net:
    def __init__(self, robots=ALLOW):
        self.robots = robots
        self.calls = []

    def __call__(self, url, timeout):
        self.calls.append(url)
        if isinstance(self.robots, Exception):
            raise self.robots
        return self.robots


class Conn:
    def __init__(self, up=True):
        self.up = up
        self.calls = []

    def __call__(self, addr, timeout):
        self.calls.append(addr)
        if not self.up:
            raise ConnectionRefusedError("refused")
        return self

    def close(self):
        pass


def _root(tmp_path, family=FAMILY, base=PUBLIC, rows=None):
    cfg = {"server": {"port": 8940}, "profile": {}}
    if family is not None:
        cfg["profile"]["family"] = family
    if base is not None:
        cfg["profile"]["base_url"] = base
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "local.json").write_text(json.dumps(cfg, indent=2) + "\n",
                                                   encoding="utf-8")
    if rows is not None:
        rt = tmp_path / "ops" / "runtime"
        rt.mkdir(parents=True)
        (rt / "profile_history.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return tmp_path


def _iso(t):
    import datetime as dt
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(microsecond=0).isoformat()


ROWS = [{"at": _iso(NOW - 600), "name": "Shooty", "main": True, "level": 62,
         "energy": 400, "contribution": 300, "spec_levels": {"fishing": "Skilled 3"}},
        {"at": _iso(NOW - 600), "name": "Alt", "main": False, "level": 20}]


def _run(root, *argv, net=None, conn=None):
    out = io.StringIO()
    code = ps.main(list(argv), root=root, fetch=net or Net(), connect=conn or Conn(),
                   clock=lambda: NOW, out=out)
    return code, out.getvalue()


def _check(root, net=None, conn=None):
    code, text = _run(root, "check", "--json", net=net, conn=conn)
    return code, json.loads(text)


def _base(root):
    return json.loads((root / "config" / "local.json").read_text(encoding="utf-8"))["profile"].get(
        "base_url")


# --- base_state ---------------------------------------------------------------

@pytest.mark.parametrize("v,state", [("", "blank"), (None, "blank"),
                                     (progress.SELF_HOST_EXAMPLE, "loopback"),
                                     ("http://localhost:8001/v1", "loopback"),
                                     (PUBLIC, "remote"), ("http://evil.example.com", "invalid"),
                                     ("ftp://127.0.0.1", "invalid")])
def test_base_state(v, state):
    assert ps.base_state(v) == state


# --- check verdicts -------------------------------------------------------------

def test_robots_disallow_is_blocked(tmp_path):
    code, r = _check(_root(tmp_path), net=Net(DENY))
    assert r["verdict"] == "blocked" and r["upstream_robots"] == "disallow"
    assert code == 2


def test_robots_unreachable_is_blocked(tmp_path):
    _, r = _check(_root(tmp_path), net=Net(OSError("down")))
    assert r["verdict"] == "blocked" and r["upstream_robots"] == "unreachable"


def test_robots_read_from_the_official_site_only(tmp_path):
    net = Net()
    _check(_root(tmp_path), net=net)
    assert net.calls == [ps.UPSTREAM_ROBOTS]
    assert ps.UPSTREAM_ROBOTS.startswith("https://www.naeu.playblackdesert.com/")


def test_no_family(tmp_path):
    _, r = _check(_root(tmp_path, family=None))
    assert r["verdict"] == "no_family" and r["family"] is False
    assert any(n.startswith("OPERATOR:") for n in r["needs"])


def test_instance_down_needs_install(tmp_path):
    conn = Conn(up=False)
    code, r = _check(_root(tmp_path), conn=conn)
    assert r["verdict"] == "needs_install" and r["instance"] == "down"
    assert conn.calls == [("127.0.0.1", 8001)]
    assert any(n.startswith("OPERATOR:") and "man90/bdo-rest-api" in n
               and "127.0.0.1:8001:8001" in n for n in r["needs"])
    assert code == 2


def test_instance_up_public_base_needs_wire(tmp_path):
    _, r = _check(_root(tmp_path))
    assert r["verdict"] == "needs_wire" and r["base"] == "remote" and r["instance"] == "up"
    assert any("wire" in n for n in r["needs"])


def test_wired_without_history(tmp_path):
    code, r = _check(_root(tmp_path, base=progress.SELF_HOST_EXAMPLE))
    assert r["verdict"] == "wired" and code == 0
    assert r["features"]["004"] == "on" and r["features"]["041"] == "waiting"


def test_stale_history_is_not_live(tmp_path):
    old = [dict(row, at=_iso(NOW - 3 * 86400)) for row in ROWS]
    _, r = _check(_root(tmp_path, base=progress.SELF_HOST_EXAMPLE, rows=old))
    assert r["verdict"] == "wired"


def test_live_with_fresh_history(tmp_path):
    code, r = _check(_root(tmp_path, base=progress.SELF_HOST_EXAMPLE, rows=ROWS))
    assert r["verdict"] == "live" and code == 0 and r["needs"] == []
    assert r["features"] == {"004": "on", "041": "on", "042": "on"}
    assert r["characters"] == 2


def test_042_hidden_when_main_has_no_life_fields(tmp_path):
    rows = [{"at": _iso(NOW - 60), "name": "Shooty", "main": True, "level": 62}]
    _, r = _check(_root(tmp_path, base=progress.SELF_HOST_EXAMPLE, rows=rows))
    assert r["features"]["042"] == "hidden"


def test_configured_loopback_base_is_probed(tmp_path):
    conn = Conn()
    _check(_root(tmp_path, base="http://localhost:9001/v1"), conn=conn)
    assert conn.calls == [("localhost", 9001)]


def test_family_never_printed(tmp_path):
    root = _root(tmp_path, base=progress.SELF_HOST_EXAMPLE, rows=ROWS)
    for argv in (("check",), ("check", "--json")):
        _, text = _run(root, *argv)
        assert FAMILY not in text and FAMILY.lower() not in text.lower()


def test_text_output_names_verdict(tmp_path):
    _, text = _run(_root(tmp_path), "check")
    assert "verdict: needs_wire" in text


# --- wire -------------------------------------------------------------------------

def test_wire_sets_loopback_and_keeps_other_keys(tmp_path):
    root = _root(tmp_path)
    code, text = _run(root, "wire")
    assert code == 0, text
    assert _base(root) == progress.SELF_HOST_EXAMPLE
    doc = json.loads((root / "config" / "local.json").read_text(encoding="utf-8"))
    assert doc["server"] == {"port": 8940} and doc["profile"]["family"] == FAMILY
    assert "restart" in text


def test_wire_twice_is_noop(tmp_path):
    root = _root(tmp_path)
    _run(root, "wire")
    before = (root / "config" / "local.json").read_bytes()
    code, text = _run(root, "wire")
    assert code == 0 and "already" in text
    assert (root / "config" / "local.json").read_bytes() == before


def test_wire_refuses_on_robots_even_forced(tmp_path):
    root = _root(tmp_path)
    for argv in (("wire",), ("wire", "--force")):
        code, _ = _run(root, *argv, net=Net(DENY))
        assert code == 2 and _base(root) == PUBLIC


def test_wire_refuses_instance_down_unless_forced(tmp_path):
    root = _root(tmp_path)
    code, _ = _run(root, "wire", conn=Conn(up=False))
    assert code == 2 and _base(root) == PUBLIC
    code, _ = _run(root, "wire", "--force", conn=Conn(up=False))
    assert code == 0 and _base(root) == progress.SELF_HOST_EXAMPLE


def test_wire_refuses_without_family(tmp_path):
    root = _root(tmp_path, family=None)
    code, _ = _run(root, "wire")
    assert code == 2 and _base(root) == PUBLIC


def test_bad_argv(tmp_path):
    code, _ = _run(_root(tmp_path), "nope")
    assert code == 2
