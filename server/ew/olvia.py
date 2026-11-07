"""Olvia Academy semester epoch (plan 170).

The tracked `data/olvia_semesters.json` rows {number, start_utc, end_utc,
weekly_quests_end_utc, needs_level, graduation_reset, source, verified[,
note]} are sourced data (Global Lab / official notice), never read from the
game. Three consumers:

1. Plan 024: each semester is one level-gated deadline row
   (`olvia-semester-<n>`: needs_level by the weekly-quest end), so the
   existing enrolment check runs per semester.
2. Plan 079: typed lecture progress is the override key LECTURE_KEY. At a
   semester boundary that resets progress (`graduation_reset`), an entry set
   before the semester start is retired `retired_by: "semester_reset"`
   (stale-marked, kept in the ledger history) instead of carried over.
3. Plan 074: one before-maintenance digest row when a semester boundary
   falls on that maintenance (graduation reset + the weekly-quest end).

Pure functions over the rows; `OlviaService` binds them to the ledger.
"""

import datetime as _dt
import json
import time
from pathlib import Path

from .levels import LEVEL_RANGE
from .today import _iso, _parse_iso

DATA_FILE = Path(__file__).resolve().parent / "data" / "olvia_semesters.json"
FIELDS = ("number", "start_utc", "end_utc", "weekly_quests_end_utc", "needs_level",
          "graduation_reset", "source", "verified")
OPTIONAL = ("note",)
MAX_TEXT = 200
MAX_SEMESTERS = 40
LECTURE_KEY = "olvia.lecture"
LECTURE_MAX = 100  # lectures done; the course count is not sourced, so a loose cap
RESET_BY = "semester_reset"
NEAR_S = 3600  # = maintdigest.ENDING_NEAR_S: a boundary "at" a maintenance
TITLE_MAX = 80  # = the dashboard's validTitle cap (today.part.js TITLE_MAX)
DEADLINE_PREFIX = "olvia-semester-"
_UTC = _dt.timezone.utc


def _ok_int(v, lo, hi):
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def _ok_text(v, most):
    return isinstance(v, str) and bool(v.strip()) and len(v) <= most and v.isascii() \
        and v.isprintable()


def _utc(v, n, name):
    when = _parse_iso(v)
    if when is None:
        raise ValueError(f"semester {n}: {name} must be an ISO time with a UTC offset")
    try:
        return _iso(when)
    except (OverflowError, ValueError, OSError):
        raise ValueError(f"semester {n}: {name} out of range") from None


def validate(row):
    """Normalised copy of one semester row, or ValueError."""
    if not isinstance(row, dict) or not set(FIELDS) <= set(row) <= set(FIELDS) | set(OPTIONAL):
        raise ValueError(f"semester must be {{{', '.join(FIELDS)}}} (+ optional note)")
    n = row["number"]
    if not _ok_int(n, 1, 999):
        raise ValueError("semester number must be an int 1..999")
    start = _utc(row["start_utc"], n, "start_utc")
    end = _utc(row["end_utc"], n, "end_utc")
    quests = _utc(row["weekly_quests_end_utc"], n, "weekly_quests_end_utc")
    if not _parse_iso(start) < _parse_iso(quests) <= _parse_iso(end):
        raise ValueError(f"semester {n}: start < weekly_quests_end <= end")
    if not _ok_int(row["needs_level"], *LEVEL_RANGE):
        raise ValueError(f"semester {n}: needs_level must be an int "
                         f"{LEVEL_RANGE[0]}..{LEVEL_RANGE[1]}")
    for k in ("graduation_reset", "verified"):
        if not isinstance(row[k], bool):
            raise ValueError(f"semester {n}: {k} must be true or false")
    if not _ok_text(row["source"], MAX_TEXT):
        raise ValueError(f"semester {n}: source must be 1..{MAX_TEXT} printable ASCII")
    out = {"number": n, "start_utc": start, "end_utc": end, "weekly_quests_end_utc": quests,
           "needs_level": row["needs_level"], "graduation_reset": row["graduation_reset"],
           "source": row["source"].strip(), "verified": row["verified"]}
    if "note" in row:
        if not _ok_text(row["note"], MAX_TEXT):
            raise ValueError(f"semester {n}: note must be 1..{MAX_TEXT} printable ASCII")
        out["note"] = row["note"].strip()
    return out


def check(rows):
    """Validated rows, oldest first; numbers unique, windows not overlapping."""
    if not isinstance(rows, list) or len(rows) > MAX_SEMESTERS:
        raise ValueError(f"semester table must be a list of at most {MAX_SEMESTERS}")
    out = sorted((validate(r) for r in rows), key=lambda r: _parse_iso(r["start_utc"]))
    if len({r["number"] for r in out}) != len(out):
        raise ValueError("duplicate semester number")
    for a, b in zip(out, out[1:]):
        if _parse_iso(b["start_utc"]) < _parse_iso(a["end_utc"]) or b["number"] <= a["number"]:
            raise ValueError(f"semester {b['number']} overlaps or is out of order")
    return out


def load(path=DATA_FILE):
    try:
        doc = json.loads(Path(path).read_text(encoding="ascii"))
    except (OSError, ValueError) as e:
        raise ValueError(f"olvia semester table unreadable: {type(e).__name__}") from e
    return check(doc)


def active(rows, now):
    """The semester running at `now` (start <= now < end), or None."""
    return next((r for r in rows if _parse_iso(r["start_utc"]) <= now
                 < _parse_iso(r["end_utc"])), None)


def upcoming(rows, now):
    return next((r for r in rows if _parse_iso(r["start_utc"]) > now), None)


def brief(rows, now):
    """View row of the running semester (else the next one), or None:
    {number, state: running|upcoming, start_utc, end_utc, weekly_quests_end_utc,
    starts_in_s, quests_end_in_s, ends_in_s, needs_level, source, verified}."""
    r = active(rows, now)
    state = "running"
    if r is None:
        r, state = upcoming(rows, now), "upcoming"
    if r is None:
        return None

    def secs(k):
        return int((_parse_iso(r[k]) - now).total_seconds())

    return {"number": r["number"], "state": state, "start_utc": r["start_utc"],
            "end_utc": r["end_utc"], "weekly_quests_end_utc": r["weekly_quests_end_utc"],
            "starts_in_s": secs("start_utc"), "quests_end_in_s": secs("weekly_quests_end_utc"),
            "ends_in_s": secs("end_utc"), "needs_level": r["needs_level"],
            "source": r["source"], "verified": r["verified"]}


def deadline_rows(rows):
    """Plan 024 rows: one per semester, needs_level by the weekly-quest end."""
    out = []
    for r in rows:
        out.append({"id": f"{DEADLINE_PREFIX}{r['number']}",
                    "label": f"Olvia Academy S{r['number']}",
                    "needs_level": r["needs_level"],
                    "enrol_by_utc": r["weekly_quests_end_utc"],
                    "quests_by_utc": r["weekly_quests_end_utc"],
                    "source": r["source"][:MAX_TEXT], "verified": r["verified"],
                    "note": f"semester {r['number']} ends {r['end_utc'][:10]}; weekly quests end "
                            f"{r['weekly_quests_end_utc'][:16].replace('T', ' ')} UTC"})
    return out


def reset_start(rows, now):
    """Start (utc datetime) of the newest started semester that resets lecture
    progress, or None."""
    started = [r for r in rows if r["graduation_reset"] and _parse_iso(r["start_utc"]) <= now]
    return _parse_iso(started[-1]["start_utc"]) if started else None


def is_stale(entry, rows, now):
    """True when a ledger entry was set before the newest reset boundary."""
    at = _parse_iso(entry.get("set_at")) if isinstance(entry, dict) else None
    cut = reset_start(rows, now)
    return at is not None and cut is not None and at < cut


def digest_rows(rows, now, start):
    """Plan 074 `ending` rows for the maintenance starting at `start`: one per
    semester boundary within NEAR_S of it (a reset start or a semester end),
    each {kind: "olvia", title, ends}."""
    out = []
    for r in rows:
        st, en = _parse_iso(r["start_utc"]), _parse_iso(r["end_utc"])
        qe = r["weekly_quests_end_utc"][:16].replace("T", " ")
        if r["graduation_reset"] and st >= now and abs((st - start).total_seconds()) <= NEAR_S:
            out.append({"kind": "olvia", "ends": _iso(st),
                        "title": f"Olvia: cohort graduates, lectures reset; S{r['number']} "
                                 f"quests end {qe} UTC"})
        elif en >= now and abs((en - start).total_seconds()) <= NEAR_S:
            out.append({"kind": "olvia", "ends": _iso(en),
                        "title": f"Olvia S{r['number']} ends (weekly quests ended {qe} UTC)"})
    return out


class OlviaService:
    """Semester rows (tracked file, injected for tests; a bad file degrades to
    none with `error`) bound to the plan 079 ledger for typed lecture progress."""

    def __init__(self, ledger, rows=None, clock=time.time):
        self.ledger = ledger
        self.clock = clock
        self.error = None
        if rows is None:
            try:
                rows = load()
            except ValueError as e:
                rows, self.error = [], str(e)
        self.rows = check(rows)

    def _now(self):
        return _dt.datetime.fromtimestamp(self.clock(), _UTC)

    def sweep(self, now=None):
        """Stale-mark: retire a live lecture entry set before the newest reset
        boundary (retired_by RESET_BY). Returns the retired entry or None."""
        now = now or self._now()
        e = self.ledger.doc()["live"].get(LECTURE_KEY)
        if e is None or not is_stale(e, self.rows, now):
            return None
        return self.ledger.clear(LECTURE_KEY, by=RESET_BY, now=now.timestamp())

    def lecture(self):
        """{value, set_at, expires_at, stale: {value, set_at, retired_at} | None}:
        the typed progress in force (after the boundary sweep) and the last
        progress the newest reset retired."""
        now = self._now()
        self.sweep(now)
        e = self.ledger.doc()["live"].get(LECTURE_KEY)
        cut = reset_start(self.rows, now)
        old = next((h for h in self.ledger.history() if h["key"] == LECTURE_KEY
                    and h["retired_by"] == RESET_BY and cut is not None
                    and _parse_iso(h["retired_at"]) >= cut), None)
        return {"value": None if e is None else e["value"],
                "set_at": None if e is None else e["set_at"],
                "expires_at": None if e is None else e["expires_at"],
                "stale": None if old is None or e is not None else
                {"value": old["value"], "set_at": old["set_at"], "retired_at": old["retired_at"]}}

    def set_lecture(self, value):
        """Typed lectures done (int 0..LECTURE_MAX), or None to clear."""
        if value is None:
            self.ledger.clear(LECTURE_KEY)
            return self.lecture()
        if not _ok_int(value, 0, LECTURE_MAX):
            raise ValueError(f"lecture must be null or an int 0..{LECTURE_MAX}")
        self.sweep()
        self.ledger.set(LECTURE_KEY, value, reason="typed lecture progress")
        return self.lecture()

    def view(self):
        now = self._now()
        return {"semester": brief(self.rows, now), "lecture": self.lecture(),
                "error": self.error}
