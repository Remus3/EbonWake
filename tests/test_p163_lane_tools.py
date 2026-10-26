"""Plan 163: dependency-bump / alert-reading tools in code lanes, and a FIX
order whose ordered files are missing from the lane diff never passes.
Pure: no git, no socket (git is a fake callable)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ew_lane  # noqa: E402
import ew_loop  # noqa: E402
import loop_inbox  # noqa: E402

from ew_loopkit import deps, make_root  # noqa: E402

FIX_NOTE = "2026-10-25-2100-from-MAIN-FIX-to-EW-bump-electron.md"
ORDER_NOTE = "2026-10-25-2100-from-MAIN-ORDER-to-EW-bump-electron.md"
FIX_TEXT = ("# From MAIN - FIX\n\nBump electron in app/package.json and regenerate "
            "app/package-lock.json, then close the Dependabot alert. See "
            "https://github.com/x/y/blob/main/app/notes.md and ops/fleet_kit/fleet_x.py.\n")


def _tools(extra):
    return extra[extra.index("--allowedTools") + 1].split(",")


# ---------------------------------------------------------------- allow list

def test_code_lanes_may_bump_dependencies_and_read_dependabot_alerts():
    tools = _tools(ew_lane.CODE_EXTRA)
    for t in ("Bash(npm install:*)", "Bash(npm ci:*)", "Bash(npm test:*)",
              "Bash(git add:*)", "Bash(git diff:*)",
              "Bash(gh api repos/{owner}/{repo}/dependabot/alerts:*)"):
        assert t in tools, t
    assert "Bash(python tools/ew_tests.py:*)" in tools  # the old gate list stays


def test_lane_tools_never_grant_a_bare_gh_or_git_or_commit():
    tools = _tools(ew_lane.CODE_EXTRA)
    for bad in ("Bash(gh:*)", "Bash(gh api:*)", "Bash(git:*)", "Bash(git commit:*)",
                "Bash(git push:*)", "Bash(npm:*)", "Bash(npm publish:*)"):
        assert bad not in tools, bad
    assert not any("dependabot/alerts" in t and "PATCH" in t for t in tools)


def test_deep_dive_gets_no_dependency_tools():
    tools = _tools(ew_loop.DEEP_EXTRA)
    assert "WebFetch" in tools and "Bash(python -m pytest:*)" in tools
    assert "Bash(npm install:*)" not in tools and "Bash(git add:*)" not in tools


def test_order_prompt_allows_the_bump_and_get_only_gh():
    p = ew_loop.order_prompt({"id": "N1", "note": FIX_NOTE, "text": FIX_TEXT})
    assert "npm install" in p and "GET" in p


def test_verify_prompt_for_an_order_requires_ordered_files_in_the_diff():
    p = ew_loop.verify_prompt({"label": "order N1: x", "kind": "order"}, 1)
    assert "ordered" in p and "missing from the diff" in p
    plan = ew_loop.verify_prompt({"label": "plan 012", "kind": "plan"}, 1)
    assert "missing from the diff" not in plan


# ---------------------------------------------------------------- ordered files

def test_ordered_files_are_repo_paths_not_urls_or_session_targets():
    assert loop_inbox.ordered_files(FIX_TEXT) == ["app/package-lock.json",
                                                   "app/package.json"]
    assert loop_inbox.ordered_files("edit `server/ew/app.py`, CLAUDE.md, .claude/x.md") \
        == ["server/ew/app.py"]
    assert loop_inbox.ordered_files("") == []


def _exists(paths):
    return lambda p: p in paths


ROADMAP_BLOCKED = ("| 001 | x | [x] done |\n\n## Order N1 - blocked items\n\n"
                   "- app/package-lock.json: BLOCKED (registry down)\n"
                   "- app/package.json: DONE\n")


def test_missing_ordered_lists_files_absent_from_the_diff():
    ex = _exists({"app/package.json", "app/package-lock.json", "app"})
    assert loop_inbox.missing_ordered(FIX_TEXT, set(), "", "N1", ex) == [
        "app/package-lock.json", "app/package.json"]
    assert loop_inbox.missing_ordered(FIX_TEXT, {"app/package.json"}, "", "N1", ex) == [
        "app/package-lock.json"]
    both = {"app/package.json", "app/package-lock.json"}
    assert loop_inbox.missing_ordered(FIX_TEXT, both, "", "N1", ex) == []


def test_missing_ordered_exempts_blocked_bullets_and_foreign_paths():
    ex = _exists({"app/package.json", "app/package-lock.json", "app"})
    assert loop_inbox.missing_ordered(FIX_TEXT, {"app/package.json"}, ROADMAP_BLOCKED,
                                      "N1", ex) == []
    # a DONE bullet is no exemption; another order's section is none either
    assert loop_inbox.missing_ordered(FIX_TEXT, set(), ROADMAP_BLOCKED, "N1", ex) == [
        "app/package.json"]
    assert loop_inbox.missing_ordered(FIX_TEXT, set(), ROADMAP_BLOCKED, "N2", ex) == [
        "app/package-lock.json", "app/package.json"]
    # a path in neither this tree nor a directory of it (another tree's) is skipped
    assert loop_inbox.missing_ordered("fix lib/other/thing.py", set(), "", "N1",
                                      _exists(set())) == []


# ---------------------------------------------------------------- Tick.extra_checks

class NameGit:
    def __init__(self, diff=(), untracked=()):
        self.diff, self.untracked = list(diff), list(untracked)

    def __call__(self, args, cwd, input=None):
        out = ""
        if args[:2] == ["diff", "HEAD"]:
            out = "\0".join(self.diff)
        elif args[:1] == ["ls-files"]:
            out = "\0".join(self.untracked)
        return subprocess.CompletedProcess(args, 0, out, "")


def _order_world(tmp_path, note, diff=(), untracked=()):
    root = make_root(tmp_path)
    oid = ew_loop.order_id(note)
    orders = root / ew_loop.ORDERS_REL
    orders.parent.mkdir(parents=True, exist_ok=True)
    orders.write_text(json.dumps({"orders": [{"id": oid, "note": note, "text": FIX_TEXT,
                                              "title": note}]}))
    wt = tmp_path / "wt"
    (wt / "app").mkdir(parents=True)
    (wt / "app/package.json").write_text("{}\n")
    (wt / "app/package-lock.json").write_text("{}\n")
    t = ew_loop.Tick(deps(root, git=NameGit(diff, untracked)))
    return t, {"id": oid, "kind": "order", "note": note}, wt


def test_fix_order_with_empty_app_diff_fails_extra_checks(tmp_path):
    t, rec, wt = _order_world(tmp_path, FIX_NOTE, diff=["docs/plans/ROADMAP.md"])
    out = t.extra_checks(rec, wt)
    assert len(out) == 1 and "app/package.json" in out[0] \
        and "app/package-lock.json" in out[0] and "missing from the diff" in out[0]


def test_fix_order_with_every_ordered_file_changed_passes_extra_checks(tmp_path):
    t, rec, wt = _order_world(tmp_path, FIX_NOTE, diff=["app/package.json"],
                              untracked=["app/package-lock.json"])
    assert t.extra_checks(rec, wt) == []


def test_non_fix_order_is_left_to_the_verifier(tmp_path):
    t, rec, wt = _order_world(tmp_path, ORDER_NOTE)
    assert t.extra_checks(rec, wt) == []
