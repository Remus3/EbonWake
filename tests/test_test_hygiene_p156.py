"""Plan 156: test hygiene follow-ups from the 20261017 audit (tests-a slice)."""

import ast
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def test_no_test_module_imports_another_test_module():
    """TESTS-A-17: shared helpers live in tests/ew_testkit.py, never in a test_*.py."""
    pat = re.compile(r"^\s*(from\s+tests\.test_\w+\s+import|import\s+tests\.test_\w+|"
                     r"from\s+test_\w+\s+import|import\s+test_\w+)", re.M)
    hits = [f"{p.name}: {m.group(0).strip()}" for p in sorted(TESTS.glob("*.py"))
            for m in pat.finditer(p.read_text(encoding="utf-8"))]
    assert hits == []


def test_ew_loop_git_mark_is_per_test_not_module_wide():
    """TESTS-A-18: a module-wide `pytestmark = git` hid the pure tests from the
    fast tier; the tier guard fails any git-spawning test left unmarked."""
    tree = ast.parse((TESTS / "test_ew_loop.py").read_text(encoding="utf-8"))
    module_marks = [n for n in tree.body if isinstance(n, ast.Assign)
                    and any(getattr(t, "id", "") == "pytestmark" for t in n.targets)]
    assert module_marks == []
    tests = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    unmarked = [n for n in tests if not any("git" in ast.unparse(d) for d in n.decorator_list)]
    assert len(unmarked) >= 40  # the pure-function tests now run in the fast tier
