"""Level-gated deadlines read from official notices (plan 116).

Pure. Plan 064 already GETs each notice's Detail page; `deadline_lines` keeps
the sentences of that page matching a tracked pattern
(`data/deadline_patterns.json`, data not code, verified false) that name a
level ("Lv. 61", "Level 61") and hold a date - "reach Lv N by <date>" or an
enrolment cut-off - at most MAX_LINES per notice, each cut to MAX_TEXT ASCII
chars. The date stays raw (plan 086 `claimwindows.points` shape) and is
resolved on every read through plan 064's maintenance notices.

`rows` turns one notice's lines into plan 024 deadline rows (+ conf,
group_no); the leveling service adds a row at or over the plan 111 gate and
keeps a lower one as a suggestion. No new GET, no new host; nothing here
reads or touches the game.
"""

import json
import re
from pathlib import Path

from . import levels
from .claimwindows import _clean_point, _sort_key, points
from .levels import LEVEL_RANGE
from .maintdigest import ascii_clip, sentences
from .today import _iso

PATTERNS_FILE = Path(__file__).resolve().parent / "data" / "deadline_patterns.json"
MAX_LINES = 3
MAX_TEXT = 200
MAX_PATTERNS = 50
KINDS = ("reach", "enrol")
MULTI_LEVEL = 0.8  # x conf: the sentence names two different levels
_LV_RE = re.compile(r"\b(?:Lv\.?|Level)\s*([0-9]{1,2})\b", re.IGNORECASE)
_KEYS = {"text", "level", "kind", "conf", "until"}


def load_patterns(path=None):
    """[(compiled, kind, conf)] of the tracked file; a bad file raises ValueError."""
    try:
        doc = json.loads(Path(path or PATTERNS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"deadline_patterns.json unreadable: {e}") from e
    raw = doc.get("patterns") if isinstance(doc, dict) else None
    if not isinstance(raw, list) or not 0 < len(raw) <= MAX_PATTERNS:
        raise ValueError("deadline_patterns.json: patterns must be a non-empty list")
    out = []
    for p in raw:
        if not (isinstance(p, dict) and set(p) == {"re", "kind", "conf"}
                and isinstance(p["re"], str) and p["re"].strip() and p["re"].isascii()
                and p["kind"] in KINDS and _ok_conf(p["conf"])):
            raise ValueError("deadline_patterns.json: each pattern is {re, kind, conf 0..1}")
        try:
            out.append((re.compile(p["re"], re.IGNORECASE), p["kind"], float(p["conf"])))
        except re.error as e:
            raise ValueError(f"deadline_patterns.json: bad pattern {p['re']!r}: {e}") from e
    return out


def _ok_conf(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1


def _ok_level(v):
    return isinstance(v, int) and not isinstance(v, bool) and LEVEL_RANGE[0] <= v <= LEVEL_RANGE[1]


def _match(s, patterns):
    """(level, kind, conf) of the best pattern matching sentence `s`, or None."""
    best = None
    for rx, kind, conf in patterns:
        m = rx.search(s)
        if m is None:
            continue
        named = m.groupdict().get("level")
        if named is not None:
            level = int(named)
        else:
            found = {int(x) for x in _LV_RE.findall(s)}
            if not found:
                continue
            level = max(found)
            if len(found) > 1:
                conf *= MULTI_LEVEL
        if not _ok_level(level):
            continue
        if best is None or conf > best[2]:
            best = (level, kind, round(conf, 3))
    return best


def extract(lines, ref_year, ref_month, patterns):
    """Sentences of `lines` matching a pattern, naming a level and holding a
    date -> up to MAX_LINES {text, level, kind, conf, until}; `until` is the
    latest date point of the sentence."""
    out = []
    for s in sentences(lines):
        hit = _match(s, patterns)
        if hit is None:
            continue
        pts = points(s, ref_year, ref_month)
        if not pts:
            continue  # a level line without a date has nothing to count down to
        text = ascii_clip(s, MAX_TEXT)
        if not text or any((d["level"], d["kind"]) == hit[:2] for d in out):
            continue
        out.append({"text": text, "level": hit[0], "kind": hit[1], "conf": hit[2],
                    "until": max(pts, key=_sort_key)})
        if len(out) >= MAX_LINES:
            break
    return out


def deadline_lines(lines, ref_year, ref_month=None, path=None):
    """`extract` with the tracked patterns; an unreadable file yields nothing
    (the notice read itself never fails on it - a test pins the file)."""
    try:
        patterns = load_patterns(path)
    except ValueError:
        return []
    return extract(lines, ref_year, ref_month, patterns)


def clean_lines(raw):
    """A cached `deadlines` list re-validated (a corrupt cache never reaches the UI)."""
    out = []
    for d in raw if isinstance(raw, list) else []:
        if not isinstance(d, dict) or set(d) != _KEYS:
            continue
        t, u = d["text"], _clean_point(d["until"])
        if u is None or not _ok_level(d["level"]) or d["kind"] not in KINDS \
                or not _ok_conf(d["conf"]):
            continue
        if not (isinstance(t, str) and 0 < len(t) <= MAX_TEXT and t.isascii() and t.isprintable()):
            continue
        if all((x["level"], x["kind"]) != (d["level"], d["kind"]) for x in out):
            out.append({"text": t, "level": d["level"], "kind": d["kind"], "conf": d["conf"],
                        "until": u})
    return out[:MAX_LINES]


def rows(notice, lines, resolve):
    """Plan 024 deadline rows (+ conf, group_no) of one notice {group_no,
    title, url}: id `notice-<no>-<level>`, label = the notice title, source =
    its url, the line as the note, verified false. `resolve(point)` -> UTC
    datetime; a line whose date cannot be placed is skipped."""
    out = []
    label = ascii_clip(notice["title"], levels.MAX_LABEL) or "Notice"
    for d in clean_lines(lines):
        try:
            when = resolve(d["until"])
        except (ValueError, OverflowError, TypeError):
            continue
        if when is None:
            continue
        rid = f"notice-{notice['group_no']}-{d['level']}"
        if any(r["id"] == rid for r in out):
            continue
        try:
            row = levels.validate_deadline({
                "id": rid, "label": label, "needs_level": d["level"],
                "enrol_by_utc": _iso(when), "quests_by_utc": None, "source": notice["url"],
                "verified": False, "note": d["text"]})
        except ValueError:
            continue
        out.append(dict(row, conf=d["conf"], group_no=notice["group_no"]))
    return out
