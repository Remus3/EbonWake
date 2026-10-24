"""MAIN ORDER N38ca97 section 2.2 / 3: the post-merge bot-PR check flags a
synthetic bad commit (tmp repo, never live history)."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bot_pr_check  # noqa: E402

OP_NAME = "Op Erator"
AT = "@"
OP_MAIL = "op" + AT + "example.invalid"
BOT_NAME = "dependabot[bot]"
BOT_MAIL = "49699333+dependabot[bot]" + AT + "users.noreply.example.invalid"


def _git(cwd, *args, env=None):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=env)


def _commit(repo, fname, msg, name=OP_NAME, mail=OP_MAIL):
    (repo / fname).write_text(fname + "\n", encoding="ascii")
    _git(repo, "add", fname)
    env = dict(__import__("os").environ, GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=mail,
               GIT_COMMITTER_NAME=name, GIT_COMMITTER_EMAIL=mail)
    _git(repo, "commit", "-q", "-m", msg, env=env)


def _setup(tmp_path):
    hooks = tmp_path / "nohooks"
    hooks.mkdir()
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    clones = []
    for name in ("local", "web"):
        c = tmp_path / name
        _git(tmp_path, "clone", "-q", str(remote), str(c))
        _git(c, "config", "core.hooksPath", str(hooks))
        _git(c, "config", "fleet.operatorIdent", f"{OP_NAME} <{OP_MAIL}>")
        _git(c, "checkout", "-q", "-B", "main")
        clones.append(c)
    local, web = clones
    _commit(local, "a.txt", "chore: base")
    _git(local, "push", "-q", "origin", "main")
    _git(local, "fetch", "-q", "origin")
    _git(web, "pull", "-q", "origin", "main")
    return local, web


@pytest.mark.git
def test_flags_bot_author_and_coauthor_trailer(tmp_path, capsys):
    local, web = _setup(tmp_path)
    msg = f"chore(deps): bump x\n\nCo-authored-by: {BOT_NAME} <{BOT_MAIL}>\n"
    _commit(web, "b.txt", msg, name=BOT_NAME, mail=BOT_MAIL)
    _git(web, "push", "-q", "origin", "main")
    rc = bot_pr_check.main(["--repo", str(local)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "ai-or-bot-author" in out
    assert "co-authored-by" in out
    assert OP_MAIL not in out and BOT_MAIL not in out
    assert (local / bot_pr_check.LOG_REL).exists()


@pytest.mark.git
def test_flags_squash_with_human_coauthor_only(tmp_path, capsys):
    """Operator-authored squash that kept a non-bot Co-authored-by line."""
    local, web = _setup(tmp_path)
    msg = "chore: squash\n\nCo-authored-by: Someone <s" + AT + "example.invalid>\n"
    _commit(web, "b.txt", msg)
    _git(web, "push", "-q", "origin", "main")
    assert bot_pr_check.main(["--repo", str(local)]) == 1
    assert "co-authored-by" in capsys.readouterr().out


@pytest.mark.git
def test_clean_operator_squash_passes(tmp_path, capsys):
    local, web = _setup(tmp_path)
    _commit(web, "b.txt", "chore(deps): bump x (path A squash)")
    _git(web, "push", "-q", "origin", "main")
    assert bot_pr_check.main(["--repo", str(local)]) == 0
    assert "1 commit(s) clean" in capsys.readouterr().out


@pytest.mark.git
def test_no_operator_ident_refuses(tmp_path):
    local, _ = _setup(tmp_path)
    _git(local, "config", "--unset-all", "fleet.operatorIdent")
    assert bot_pr_check.main(["--repo", str(local), "--no-fetch"]) == 2


def test_coauthor_hits_any_name():
    rows = [{"sha": "a" * 40, "msg": "x\n\nco-authored-by: Anyone <a@b>\n"},
            {"sha": "b" * 40, "msg": "clean\n"}]
    assert bot_pr_check.coauthor_hits(rows) == [("a" * 10, "co-authored-by")]
