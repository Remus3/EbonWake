"""Plan 130: known-issues advisories.

Hand-curated rows from the official NA Known Issues notice, kept in the
tracked `data/known_issues.json` (ASCII, every row cites the notice and the
read date). Nothing here fetches anything: plan 064's notice import may later
suggest rows, suggest-only.

A `defect` row is live from `from` (inclusive) to `until` (exclusive, null =
open); a `change` row is `pending` before `from` and `applied` after it until
`until`. A combat XP sample taken inside a live `leveling` defect window
(within the row's optional level range, and unless `exclude_samples` is false)
is `suspect`: shown, but kept out of the plan 116 rate fit. Times are UTC.
"""

import json
import re
from pathlib import Path

from .levels import LEVEL_RANGE
from .today import _iso, _parse_iso

FILE = Path(__file__).resolve().parent / "data" / "known_issues.json"
AREAS = ("leveling", "trading", "enhance", "market", "books")
KINDS = ("defect", "change")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
TITLE_MAX = 120
SOURCE_MAX = 200
FIELDS = {"id", "title", "affects", "from", "until", "source", "verified", "kind",
          "exclude_samples", "level_min", "level_max", "note"}


def _text(v, most):
    return (isinstance(v, str) and bool(v.strip()) and len(v) <= most
            and all(32 <= ord(ch) < 127 for ch in v))


def _utc(v, rid, name):
    when = _parse_iso(v)
    if when is None:
        raise ValueError(f"{rid}: {name} must be an ISO time with a UTC offset")
    return _iso(when)


def _level(v, rid, name):
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, int) or not LEVEL_RANGE[0] <= v <= LEVEL_RANGE[1]:
        raise ValueError(f"{rid}: {name} must be a level {LEVEL_RANGE[0]}-{LEVEL_RANGE[1]}")
    return v


def validate(row):
    """One clean row or ValueError. Defaults: kind defect, exclude_samples true,
    no level range."""
    if not isinstance(row, dict):
        raise ValueError("known issue row must be an object")
    rid = row.get("id")
    if not isinstance(rid, str) or not ID_RE.match(rid):
        raise ValueError(f"known issue id {rid!r} must be a lowercase slug")
    extra = set(row) - FIELDS
    if extra:
        raise ValueError(f"{rid}: unknown fields {sorted(extra)}")
    if not _text(row.get("title"), TITLE_MAX):
        raise ValueError(f"{rid}: title must be ASCII text <= {TITLE_MAX}")
    if not _text(row.get("source"), SOURCE_MAX):
        raise ValueError(f"{rid}: source must be ASCII text <= {SOURCE_MAX}")
    if "note" in row and not _text(row["note"], SOURCE_MAX):
        raise ValueError(f"{rid}: note must be ASCII text <= {SOURCE_MAX}")
    aff = row.get("affects")
    if (not isinstance(aff, list) or not aff or len(set(aff)) != len(aff)
            or any(a not in AREAS for a in aff)):
        raise ValueError(f"{rid}: affects must be distinct areas from {AREAS}")
    frm = _utc(row.get("from"), rid, "from")
    until = None if row.get("until") is None else _utc(row["until"], rid, "until")
    if until is not None and _parse_iso(until) <= _parse_iso(frm):
        raise ValueError(f"{rid}: until must be after from")
    if not isinstance(row.get("verified"), bool):
        raise ValueError(f"{rid}: verified must be true or false")
    kind = row.get("kind", "defect")
    if kind not in KINDS:
        raise ValueError(f"{rid}: kind must be one of {KINDS}")
    excl = row.get("exclude_samples", True)
    if not isinstance(excl, bool):
        raise ValueError(f"{rid}: exclude_samples must be true or false")
    lo = _level(row.get("level_min"), rid, "level_min")
    hi = _level(row.get("level_max"), rid, "level_max")
    if lo is not None and hi is not None and lo > hi:
        raise ValueError(f"{rid}: level_min above level_max")
    out = {"id": rid, "title": row["title"], "affects": list(aff), "from": frm, "until": until,
           "source": row["source"], "verified": row["verified"], "kind": kind,
           "exclude_samples": excl, "level_min": lo, "level_max": hi}
    if "note" in row:
        out["note"] = row["note"]
    return out


def load(path=FILE):
    """Validated rows, oldest `from` first; ValueError on any bad row or a
    duplicate id."""
    try:
        raw = json.loads(Path(path).read_text(encoding="ascii"))
    except (OSError, ValueError) as e:
        raise ValueError(f"known issues unreadable: {type(e).__name__}") from e
    if not isinstance(raw, list):
        raise ValueError("known issues must be a list")
    rows = [validate(r) for r in raw]
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("known issues: duplicate id")
    return sorted(rows, key=lambda r: (r["from"], r["id"]))


def state(row, now):
    """pending | active | applied | ended at utc datetime `now`."""
    if now < _parse_iso(row["from"]):
        return "pending"
    if row["until"] is not None and now >= _parse_iso(row["until"]):
        return "ended"
    return "applied" if row["kind"] == "change" else "active"


def active(now, area=None, rows=None):
    """Rows live at `now` (defects in their window; changes pending or
    applied), each with its `state`, filtered to `area` when given."""
    if area is not None and area not in AREAS:
        raise ValueError(f"area must be one of {AREAS}")
    out = []
    for r in load() if rows is None else rows:
        st = state(r, now)
        if st == "ended" or (st == "pending" and r["kind"] != "change"):
            continue
        if area is None or area in r["affects"]:
            out.append(dict(r, state=st))
    return out


def suspect(rows, when, level):
    """Id of the first live `leveling` defect row that taints an XP sample
    taken at utc datetime `when` at `level`, else None."""
    for r in rows:
        if (r["kind"] != "defect" or not r["exclude_samples"] or "leveling" not in r["affects"]
                or state(r, when) != "active"):
            continue
        if r["level_min"] is not None and (level is None or level < r["level_min"]):
            continue
        if r["level_max"] is not None and (level is None or level > r["level_max"]):
            continue
        return r["id"]
    return None
