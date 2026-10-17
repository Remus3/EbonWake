"""Plan 150 (TESTS-A-01): no test reads the host's gitignored config/local.json,
the live market cache under ops/runtime, or the internet through a default
client. tests/ew_hermetic.py (installed from conftest) points every default at
a per-test tmp host dir and refuses non-loopback urlopen."""

import urllib.error
import urllib.request
from pathlib import Path

import pytest

from server.ew import app as ewapp
from server.ew import market, progress

REAL_ROOT = Path(ewapp.__file__).resolve().parents[2]


def _under_repo(p):
    try:
        Path(p).resolve().relative_to(REAL_ROOT)
    except ValueError:
        return False
    return True


def test_default_config_path_is_not_the_host_config():
    assert not _under_repo(ewapp.CONFIG_PATH)


def test_default_market_cache_is_not_the_live_cache():
    assert not _under_repo(market._DEFAULT_CACHE)
    assert not _under_repo(market.ArshaClient().cache_dir)


def test_repo_rooted_config_readers_read_the_tmp_host():
    assert not _under_repo(ewapp.CONFIG_PATH)  # never write the real file
    assert ewapp.CONFIG_PATH.parent.is_dir()
    ewapp.CONFIG_PATH.write_text('{"market": {"vp": true}, "profile": {"family": "X"},'
                                 ' "market_watch": [5]}', encoding="utf-8")
    assert ewapp.config_market() == {"vp": True, "fame_pct": 0}
    assert ewapp.config_market_watch() == [5]
    assert ewapp.config_hash() is not None
    assert progress.config_profile(ewapp.REPO_ROOT) == {"family": "X"}


def test_explicit_roots_still_read_their_own_file(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "local.json").write_text('{"market": {"fame_pct": 0.5}}',
                                                    encoding="utf-8")
    assert ewapp.config_market(tmp_path) == {"vp": False, "fame_pct": 0.5}
    assert progress.config_profile(tmp_path) == {}


def test_server_defaults_are_isolated(tmp_path):
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", market_seed=[],
                          profile_cfg={})
    try:
        assert not _under_repo(s.settings.path)
        assert not _under_repo(s.market.client.cache_dir)
        assert s.market.settings == {"vp": False, "fame_pct": 0}
    finally:
        s.server_close()


def test_internet_urlopen_is_refused_without_a_socket():
    with pytest.raises(urllib.error.URLError, match="no network in tests"):
        urllib.request.urlopen("https://ew-p150.invalid/x", timeout=1)
    req = urllib.request.Request("http://example.com/")
    with pytest.raises(urllib.error.URLError, match="no network in tests"):
        urllib.request.urlopen(req, timeout=1)
