"""Plan 109 slice 5: zero-touch guard.

Every plan 079 override key either has a live signal (read, not typed), a
plan 080 fixed default, or a named exemption with its reason. The keys left
over still need an operator value; after plans 108 + 109 that list is exactly
`profile.multi_character`. A new key that needs typing fails this test until it
gets a live signal, a fixed default or an exemption with a reason.
"""

import pytest

from server.ew import app as ewapp
from server.ew import market, overrides, settings

pytestmark = pytest.mark.server

EXEMPT = {
    "ui.scale": "pure preference (dashboard zoom)",
    "overlay.mode.*": "pure preference (plan 078 widget pin / block)",
    "notify.mute_until": "pure preference (operator mutes alerts on purpose)",
    "portrait.*": "pure preference (plan 083 gallery pick)",
    "bdo.install_dir": "auto-detected (plan 065); typed only to point elsewhere",
    "bdo.documents_dir": "auto-detected (plan 065); typed only to point elsewhere",
    "profile.family": "the identity key every profile read starts from",
}
NEEDS_OPERATOR = ["profile.multi_character"]


def _no_network(url, timeout):
    raise AssertionError(f"network: {url}")


@pytest.fixture()
def srv(tmp_path):
    s = ewapp.make_server(port=0, store_root=tmp_path / "store", commit="a" * 40,
                          sse_interval=0.05, market_seed=[],
                          market_client=market.ArshaClient(fetch=_no_network,
                                                           cache_dir=tmp_path / "cache"),
                          config_path=tmp_path / "local.json", profile_cfg={})
    yield s
    s.server_close()


def _needs_operator(policy, live, partial):
    full = set(live) - set(partial)
    return sorted(k for k in policy
                  if k not in full and k not in settings.FIXED and k not in EXEMPT)


def test_only_multi_character_still_needs_an_operator_value(srv):
    policy = overrides.load_policy()
    assert _needs_operator(policy, srv.live_signals(), srv.LIVE_PARTIAL) == NEEDS_OPERATOR


def test_value_pack_and_fame_are_read_not_typed(srv):
    live = srv.live_signals()
    for key in ("market.vp", "market.fame_pct"):
        assert key in live and key not in srv.LIVE_PARTIAL


def test_every_exemption_and_partial_signal_names_a_real_key_with_a_reason(srv):
    policy = overrides.load_policy()
    for key, why in list(EXEMPT.items()) + list(srv.LIVE_PARTIAL.items()):
        assert key in policy, f"stale entry: {key}"
        assert isinstance(why, str) and len(why) >= 10, key
    assert set(srv.LIVE_PARTIAL) <= set(srv.live_signals())
    assert set(srv.live_signals()) <= set(policy)
    assert not set(EXEMPT) & set(srv.live_signals())


def test_incident_switches_are_fixed_keys():
    policy = overrides.load_policy()
    first_sight = {k for k, row in policy.items() if row.get("first_sight") is True}
    assert first_sight and first_sight <= set(settings.FIXED)


def test_guard_catches_a_new_typed_key(srv):
    policy = dict(overrides.load_policy(), **{"market.new_input": {"expiry": "days:30"}})
    assert _needs_operator(policy, srv.live_signals(), srv.LIVE_PARTIAL) == [
        "market.new_input", "profile.multi_character"]
