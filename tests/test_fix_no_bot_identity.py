"""No bot author or committer in the history reachable from HEAD (order N7e0676).

A Dependabot bump is applied as an operator commit; a GitHub merge that keeps the
bot as author would put "dependabot[bot]" on the repo page Contributors list.
"""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.git
def test_no_bot_author_or_committer_reachable_from_head():
    out = subprocess.run(
        ["git", "log", "HEAD", "--format=%an|%ae|%cn|%ce"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0 or not out.stdout.strip():
        pytest.skip("no git history available")
    bots = sorted(
        {line for line in out.stdout.splitlines() if "[bot]" in line.lower()}
    )
    assert not bots, bots
