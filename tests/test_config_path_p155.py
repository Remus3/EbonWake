"""Plan 155 (TESTS-A-01, TESTS-B-06, TESTS-A-15): an injected config_path is
the only config/local.json EWServer reads (market, market_watch, profile and
the /api/version hash), and loopstatus.main_root resolves a relative gitdir."""

import hashlib
import json

from server.ew import app as ewapp
from server.ew import loopstatus as ls
from server.ew import progress

DOC = {"market": {"vp": True, "fame_pct": 1}, "market_watch": [11, 22],
       "profile": {"family": "Tmpfam", "auto_level": False}}


def _cfg(tmp_path):
    p = tmp_path / "alt" / "settings.json"
    p.parent.mkdir()
    p.write_text(json.dumps(DOC), encoding="utf-8")
    return p


def test_readers_take_an_explicit_file(tmp_path):
    p = _cfg(tmp_path)
    assert ewapp.config_market(path=p) == {"vp": True, "fame_pct": 1}
    assert ewapp.config_market_watch(path=p) == [11, 22]
    assert ewapp.config_hash(path=p) == hashlib.sha256(p.read_bytes()).hexdigest()
    assert progress.config_profile(None, path=p) == DOC["profile"]


def test_server_reads_only_the_injected_config_path(tmp_path, _ew_hermetic_host):
    # the default host file says something else; the injected file must win
    (_ew_hermetic_host / "config" / "local.json").write_text(
        json.dumps({"market": {"vp": False}, "market_watch": [99],
                    "profile": {"family": "Hostfam"}}), encoding="utf-8")
    host_before = (_ew_hermetic_host / "config" / "local.json").read_bytes()
    p = _cfg(tmp_path)
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", config_path=p)
    try:
        assert s.market.settings == {"vp": True, "fame_pct": 1}
        assert [w["id"] for w in s.market.watchlist.items()] == [11, 22]
        assert s.progress.profile.family == "Tmpfam"
        assert s.progress.auto_level is False
        assert s.cfg_hash == hashlib.sha256(p.read_bytes()).hexdigest()
    finally:
        s.server_close()
    assert (_ew_hermetic_host / "config" / "local.json").read_bytes() == host_before


def test_server_without_config_path_keeps_the_default_file(tmp_path, _ew_hermetic_host):
    (_ew_hermetic_host / "config" / "local.json").write_text(
        json.dumps({"market": {"fame_pct": 0.5}, "market_watch": [7]}), encoding="utf-8")
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", profile_cfg={})
    try:
        assert s.market.settings == {"vp": False, "fame_pct": 0.5}
        assert [w["id"] for w in s.market.watchlist.items()] == [7]
        assert s.cfg_hash == ewapp.config_hash()
    finally:
        s.server_close()


def test_main_root_resolves_a_relative_gitdir(tmp_path):
    # git worktree.useRelativePaths writes gitdir relative to the .git file's dir
    main = tmp_path / "main"
    (main / ".git" / "worktrees" / "lane-1").mkdir(parents=True)
    wt = tmp_path / "wts" / "lane-1"
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: ../../main/.git/worktrees/lane-1\n")
    assert ls.main_root(wt).resolve() == main.resolve()
