"""Plan 134: the targeted autonomy / efficiency deep-dive (research 0029)
proposes at most 6 plans; every proposed row has a well-formed plan doc with a
`Depends on:` line, and no proposed title duplicates an earlier plan or another
proposed one under the loop's own dedup rule (loop_roadmap.is_duplicate)."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import loop_roadmap  # noqa: E402

RESEARCH = ROOT / "docs" / "research" / "0029-deep-dive-autonomy-efficiency.md"
PLAN = ROOT / "docs" / "plans" / "134-autonomy-efficiency-deep-dive.md"
ROW_RX = re.compile(
    r"^\| (\d{3}) \| (.+) \(plan doc (docs/plans/\d{3}-[a-z0-9-]+\.md)\) \| \[ \] open \(priority\) \|$",
    re.M)
MAX_PLANS = 6


def _proposed():
    """Proposed ROADMAP rows in the plan 134 doc -> {id: (title, doc path)}."""
    text = PLAN.read_text(encoding="utf-8")
    block = text.split("## Proposed ROADMAP rows", 1)[1].split("\n## ", 1)[0]
    return {pid: (title, doc) for pid, title, doc in ROW_RX.findall(block)}


def test_research_doc_covers_the_three_scope_areas():
    text = RESEARCH.read_text(encoding="utf-8")
    assert text.startswith("# 0029 - ")
    for head in ("## A. Autonomy", "## B. Efficiency", "## C. Player features"):
        assert head in text, head
    for verdict in ("PLAN", "NOTE", "NO"):
        assert f"| {verdict} " in text, verdict
    assert "## Ranking" in text


def test_at_most_six_proposed_and_numbered_from_135():
    rows = _proposed()
    assert 1 <= len(rows) <= MAX_PLANS
    assert sorted(rows) == [str(135 + i) for i in range(len(rows))]


def test_every_proposed_row_has_a_well_formed_plan_doc():
    research = RESEARCH.read_text(encoding="utf-8")
    for pid, (_title, rel) in _proposed().items():
        docs = list((ROOT / "docs" / "plans").glob(f"{pid}-*.md"))
        assert [d.relative_to(ROOT).as_posix() for d in docs] == [rel], pid
        doc = docs[0].read_text(encoding="utf-8")
        assert doc.startswith(f"# Plan {pid} - "), rel
        assert re.search(r"^Depends on: .+$", doc, re.M), rel
        for head in ("## Slices", "## Acceptance"):
            assert head in doc, (rel, head)
        assert "Game ToS" in doc, rel
        assert f"plan {pid}" in research.lower() or f"| {pid} |" in research, pid


def test_proposed_titles_are_not_duplicates():
    titles = loop_roadmap.plan_titles(ROOT)
    new = _proposed()
    earlier = [t for k, t in titles.items() if k <= "134"]
    for pid in new:
        assert loop_roadmap.is_duplicate(titles[pid], earlier) is None, pid
        others = [titles[k] for k in new if k != pid]
        assert loop_roadmap.is_duplicate(titles[pid], others) is None, pid


def test_row_title_matches_plan_heading():
    titles = loop_roadmap.plan_titles(ROOT)
    for pid, (title, _rel) in _proposed().items():
        assert title == titles[pid], pid
