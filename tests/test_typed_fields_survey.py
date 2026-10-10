"""Plan 120: the typed-fields survey (research 0021) covers every operator
write route, and the automation plans it proposes exist, are well-formed and
duplicate neither an earlier plan nor each other (the loop's own dedup rule)."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import loop_roadmap  # noqa: E402

from server.ew import app as ewapp  # noqa: E402

SURVEY = ROOT / "docs" / "research" / "0021-typed-fields-survey.md"
PLAN = ROOT / "docs" / "plans" / "120-typed-fields-survey.md"
ROW_RX = re.compile(r"^\| (\d{3}) \| (.+) \| \[ \] open \|$", re.M)


def _survey():
    return SURVEY.read_text(encoding="utf-8")


def _proposed():
    """Proposed ROADMAP rows in the plan 120 doc -> {id: title}."""
    text = PLAN.read_text(encoding="utf-8")
    block = text.split("## Proposed ROADMAP rows", 1)[1].split("\n## ", 1)[0]
    return dict(ROW_RX.findall(block))


def test_survey_lists_every_post_route():
    text = _survey()
    missing = [p for p in ewapp.Handler.POST_ROUTES if f"`{p}`" not in text]
    assert not missing, f"survey does not cover {missing}"


def test_survey_names_the_plan_scope_domains():
    text = _survey().lower()
    for word in ("pets", "mounts", "inventory", "crafting", "verdict"):
        assert word in text


def test_plan_doc_has_deviations_and_rows():
    text = PLAN.read_text(encoding="utf-8")
    assert text.startswith("# Plan 120 - ")
    assert "## As-built deviations" in text
    assert len(_proposed()) >= 3


def test_proposed_plans_exist_and_match_rows():
    for pid, title in _proposed().items():
        docs = list((ROOT / "docs" / "plans").glob(f"{pid}-*.md"))
        assert len(docs) == 1, pid
        first = docs[0].read_text(encoding="utf-8").split("\n", 1)[0]
        assert first.startswith(f"# Plan {pid} - "), docs[0].name
        assert pid in _survey(), f"survey does not reference plan {pid}"
        assert title.strip()


def test_proposed_plans_are_not_duplicates():
    titles = loop_roadmap.plan_titles(ROOT)
    new = _proposed()
    earlier = [t for k, t in titles.items() if k <= "120"]
    for pid in new:
        assert loop_roadmap.is_duplicate(titles[pid], earlier) is None, pid
        others = [titles[k] for k in new if k != pid]
        assert loop_roadmap.is_duplicate(titles[pid], others) is None, pid


def test_proposed_plans_depend_and_accept():
    for pid in _proposed():
        doc = next((ROOT / "docs" / "plans").glob(f"{pid}-*.md")).read_text(encoding="utf-8")
        assert "## Acceptance" in doc, pid
        assert "Game ToS" in doc, pid
