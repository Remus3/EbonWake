"""Plan 150 (TESTS-A-01): host isolation for every test.

EWServer's defaults read the host's gitignored config/local.json
(`Settings(CONFIG_PATH)`, `config_market()`, `config_market_watch()`,
`config_hash()`, `progress.config_profile(REPO_ROOT)`) and build an
`ArshaClient()` over the live market cache under ops/runtime with the real
fetch. A server fixture that left out one argument therefore depended on the
operator's settings (VP on changed tax asserts) and could reach arsha.io.

One autouse fixture points each of those defaults at a fresh per-test tmp
"host" dir (an explicit root or path still reads its own file) and swaps
`urllib.request.urlopen` for one that refuses every non-loopback URL with a
URLError (an offline host, raised before any socket) - the chokepoint of
every default fetch. Installed from tests/conftest.py:
ew_hermetic.install(globals())
"""

import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

LOOPBACK = ("127.0.0.1", "localhost", "::1")


def offline_urlopen(real):
    def urlopen(url, *args, **kwargs):
        full = url.full_url if isinstance(url, urllib.request.Request) else str(url)
        if urllib.parse.urlsplit(full).hostname not in LOOPBACK:
            raise urllib.error.URLError(f"no network in tests (plan 150): {full}")
        return real(url, *args, **kwargs)
    return urlopen


def rooted(fn, real_root, host):
    """fn(root) reading `host` whenever the caller meant the repo root."""
    def wrapped(root=None, path=None):
        if root is None or Path(root) == Path(real_root):
            root = host
        return fn(root, path=path)
    wrapped.__wrapped__ = fn
    return wrapped


def install(ns):
    @pytest.fixture(autouse=True)
    def _ew_hermetic_host(monkeypatch, tmp_path_factory):
        from server.ew import app, market, progress

        host = tmp_path_factory.mktemp("host")
        (host / "config").mkdir()
        monkeypatch.setattr(app, "CONFIG_PATH", host / "config" / "local.json")
        for name in ("config_market", "config_market_watch", "config_hash"):
            monkeypatch.setattr(app, name, rooted(getattr(app, name), app.REPO_ROOT, host))
        monkeypatch.setattr(progress, "config_profile",
                            rooted(progress.config_profile, app.REPO_ROOT, host))
        monkeypatch.setattr(market, "_DEFAULT_CACHE", host / "cache" / "market")
        monkeypatch.setattr(urllib.request, "urlopen", offline_urlopen(urllib.request.urlopen))
        yield host

    ns["_ew_hermetic_host"] = _ew_hermetic_host
    return ns
