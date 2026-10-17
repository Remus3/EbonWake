"""FLEET item 8: every tracked text file is ASCII and LF (PowerShell included)."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".js", ".css", ".html", ".yml", ".yaml",
                 ".ini", ".toml", ".cfg", ".ps1", ""}


def _tracked(run=subprocess.run):
    # Plan 150 (TESTS-A-02): a failing git used to read as "no files", so the
    # check passed after checking nothing.
    out = run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, timeout=60)
    assert out.returncode == 0, f"git ls-files failed: {out.stderr!r}"
    files = [ROOT / f for f in out.stdout.decode().split("\0") if f]
    assert files, "git ls-files listed no tracked files"
    return files


def _problems(rel, data):
    out = []
    try:
        data.decode("ascii")
    except UnicodeDecodeError:
        out.append(f"{rel}: non-ascii")
    if b"\r" in data:  # CRLF and a bare CR alike
        out.append(f"{rel}: crlf")
    return out


def test_git_failure_is_not_a_pass():
    def run(*a, **k):
        return subprocess.CompletedProcess(a, 128, stdout=b"", stderr=b"fatal: dubious")
    with pytest.raises(AssertionError, match="git ls-files failed"):
        _tracked(run)

    def empty(*a, **k):
        return subprocess.CompletedProcess(a, 0, stdout=b"", stderr=b"")
    with pytest.raises(AssertionError, match="no tracked files"):
        _tracked(empty)


def test_bare_cr_and_ps1_are_checked():
    assert _problems("a.ps1", b"x\ry\n") == ["a.ps1: crlf"]
    assert _problems("a.py", b"ok\n") == []
    assert ".ps1" in TEXT_SUFFIXES


@pytest.mark.git  # plan 097: git ls-files (read-only); run it by name
def test_tracked_text_is_ascii_lf():
    files = [p for p in _tracked() if p.suffix in TEXT_SUFFIXES and p.is_file()
             and p.name not in {"LICENSE"} and "fleet_kit" not in p.parts]
    bad = []
    for p in files:
        data = p.read_bytes()
        if b"\0" in data:
            continue
        bad.extend(_problems(p.relative_to(ROOT), data))
    assert bad == []
