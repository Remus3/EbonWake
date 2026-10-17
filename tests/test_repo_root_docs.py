"""Plan 152 (audit ops-ci-config): root docs and config must match the code."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _readme():
    # Whitespace-normalised so a claim cannot hide behind a line wrap.
    return " ".join((ROOT / "README.md").read_text(encoding="ascii").split())


def test_readme_never_claims_the_public_profile_api_is_called():
    """OPS-CI-CONFIG-01: plan 061 never calls the robots-disallowed public
    BDO-REST-API host; the family name goes only to a self-hosted instance."""
    text = _readme()
    assert "public profile API" not in text
    assert "public BDO-REST-API profile endpoint" not in text
    assert "optional public profile card" not in text
    assert "self-hosted BDO-REST-API" in text


def test_readme_does_not_put_the_watchlist_in_local_json():
    """OPS-CI-CONFIG-02: the market watchlist is runtime state edited from the
    Market tab; config/local.json has no watchlist key."""
    import json
    doc = json.loads((ROOT / "config" / "local.example.json").read_text(encoding="ascii"))
    assert "watchlist" not in json.dumps(doc)
    assert "market watchlist" not in _readme()


def test_readme_status_does_not_call_the_loop_unread():
    """OPS-CI-CONFIG-03: the loop task is installed and read back (CLAUDE.md
    Loop item 1); the README status still said read-back pending."""
    assert "read-back pending" not in _readme()


def test_gitignore_covers_local_virtualenvs():
    """OPS-CI-CONFIG-04: a venv in the checkout (pyvenv.cfg carries an
    absolute machine path) must never be staged by a broad git add."""
    lines = (ROOT / ".gitignore").read_text(encoding="ascii").splitlines()
    assert ".venv/" in lines
    assert "venv/" in lines
