"""Plan 173: plan doc / ROADMAP consistency lint.

Fixture docs in tmp_path pin each check (bad first-line number, duplicate
number, doc without a row, row citing a missing doc, legacy allow-list), then
one run over the real tree must come back clean.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import plan_lint  # noqa: E402

HEAD = "# Ebonwake roadmap\n\n| # | Plan | Status |\n|---|---|---|\n"


def _tree(tmp_path, docs, rows, history_rows=()):
    plans = tmp_path / "docs" / "plans"
    plans.mkdir(parents=True)
    for name, first in docs.items():
        (plans / name).write_text(first + "\n\nbody\n", encoding="utf-8")
    (plans / "ROADMAP.md").write_text(HEAD + "".join(r + "\n" for r in rows),
                                      encoding="utf-8")
    if history_rows:
        (plans / "ROADMAP-history.md").write_text(
            HEAD + "".join(r + "\n" for r in history_rows), encoding="utf-8")
    return tmp_path


def _kinds(findings):
    return sorted((f.kind, f.number) for f in findings)


def test_clean_tree_has_no_findings(tmp_path):
    root = _tree(tmp_path, {"001-a.md": "# Plan 001 - A",
                            "002-b.md": "# Plan 002 - B"},
                 ["| 001 | A | [x] done |",
                  "| 002 | B (docs/plans/002-b.md) | [ ] open |",
                  "| 003 | order row, no doc | [ ] open |"])
    assert plan_lint.lint(root, allow=()) == []


def test_first_line_number_mismatch(tmp_path):
    root = _tree(tmp_path, {"004-a.md": "# Plan 040 - A",
                            "005-b.md": "Plan 005 - B",
                            "006-c.md": "# Plan 006 -"},
                 ["| 004 | A | x |", "| 005 | B | x |", "| 006 | C | x |"])
    found = plan_lint.lint(root, allow=())
    assert _kinds(found) == [("first-line", "004"), ("first-line", "005"),
                             ("first-line", "006")]
    msg = [f.message for f in found if f.number == "004"][0]
    assert "004" in msg and msg.isascii()


def test_duplicate_number(tmp_path):
    root = _tree(tmp_path, {"007-a.md": "# Plan 007 - A",
                            "007-b.md": "# Plan 007 - B"},
                 ["| 007 | A | x |"])
    found = plan_lint.lint(root, allow=())
    assert _kinds(found) == [("duplicate", "007")]
    assert "007-a.md" in found[0].message and "007-b.md" in found[0].message


def test_doc_without_row(tmp_path):
    root = _tree(tmp_path, {"008-a.md": "# Plan 008 - A",
                            "009-b.md": "# Plan 009 - B"},
                 ["| 008 | A | x |"])
    assert _kinds(plan_lint.lint(root, allow=())) == [("no-row", "009")]


def test_row_in_history_counts(tmp_path):
    root = _tree(tmp_path, {"010-a.md": "# Plan 010 - A"}, [],
                 history_rows=["| 010 | A | [x] done |"])
    assert plan_lint.lint(root, allow=()) == []


def test_row_cites_missing_doc(tmp_path):
    root = _tree(tmp_path, {"011-a.md": "# Plan 011 - A"},
                 ["| 011 | A (docs/plans/011-a.md) | x |",
                  "| 012 | B; plan doc docs/plans/012-gone.md. | x |"])
    found = plan_lint.lint(root, allow=())
    assert _kinds(found) == [("missing-doc", "012")]
    assert "docs/plans/012-gone.md" in found[0].message


def test_non_plan_files_ignored(tmp_path):
    root = _tree(tmp_path, {"013-a.md": "# Plan 013 - A"}, ["| 013 | A | x |"])
    (root / "docs" / "plans" / "notes.md").write_text("# x\n", encoding="utf-8")
    assert plan_lint.lint(root, allow=()) == []


def test_allow_list_suppresses_only_listed(tmp_path):
    root = _tree(tmp_path, {"014-a.md": "# Plan 41 - A",
                            "015-b.md": "# Plan 015 - B"}, [])
    found = plan_lint.lint(root, allow={("first-line", "014"),
                                        ("no-row", "014")})
    assert _kinds(found) == [("no-row", "015")]


def test_stale_allow_entries_reported(tmp_path):
    root = _tree(tmp_path, {"016-a.md": "# Plan 016 - A"}, ["| 016 | A | x |"])
    stale = plan_lint.stale_allow(root, allow={("no-row", "016"),
                                               ("no-row", "999")})
    assert stale == [("no-row", "016"), ("no-row", "999")]


def test_main_exit_codes(tmp_path, capsys):
    root = _tree(tmp_path, {"017-a.md": "# Plan 017 - A"}, [])
    assert plan_lint.main(["--root", str(root), "--no-legacy"]) == 1
    out = capsys.readouterr().out
    assert "017" in out and out.isascii()
    root2 = _tree(tmp_path / "ok", {"018-a.md": "# Plan 018 - A"},
                  ["| 018 | A | x |"])
    assert plan_lint.main(["--root", str(root2), "--no-legacy"]) == 0


def test_real_tree_is_clean():
    found = plan_lint.lint(ROOT)
    assert found == [], "\n".join(f.message for f in found)


def test_real_tree_legacy_list_not_stale():
    # Once a legacy exception is fixed, its entry must go, so the list only
    # ever shrinks.
    assert plan_lint.stale_allow(ROOT, plan_lint.LEGACY) == []
