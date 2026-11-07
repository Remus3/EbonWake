"""Imperial Reward Seal ledger (plan 169): the six per-category Reward Seals
of the 2026-11-05 patch (Cooking, Fishing, Subjugation, Training, Work
Supervisor, Alchemy), their exchange rows, and the Golden Seal conversion at
the 2026-12-03 maintenance.

Categories, the Golden Seal row and seeded exchange rows come from the
tracked, sourced `data/reward_seals.json` (each row carries `verified`, so
the plan 085 patch-notes verifier sees it). Seal counts are operator-typed
(OCR may feed them later); nothing is read from the game. Affordability is
pure: a row is affordable when its category's count covers its cost; an
unknown count is never guessed. The conversion countdown targets that date's
maintenance start (an official notice beats the weekly slot, plan 067); the
conversion rate is shown as unknown until a sourced wording lands in the data
file. While Golden Seals are (or may be) held, `digest_rows` feeds one row to
the plan 074 before-maintenance digest.

Store domain `reward_seals`: {"counts": {category | "golden": int},
"counts_at": {key: iso}, "exchange": [{id, category, item, cost}], "updated"}.
"""

import datetime as _dt
import json
import threading
import time
from pathlib import Path

from . import maint as _maint
from .imperial import _ascii, _is_int, _iso, _verified_ok
from .today import slug

DATA_PATH = Path(__file__).resolve().parent / "data" / "reward_seals.json"
DOMAIN = "reward_seals"
CATEGORIES = ("cooking", "fishing", "subjugation", "training", "work-supervisor", "alchemy")
GOLDEN = "golden"
UNKNOWN_RATE = "conversion rate not announced"
COUNT_MAX = 10 ** 6
COST_MAX = 10 ** 6
LIMIT_MAX = 10 ** 4
MAX_ITEM = 60
MAX_ROWS = 120
MAX_TEXT = 300
DATA_KEYS = {"_doc", "categories", "golden", "exchange"}
CAT_KEYS = {"id", "name", "source", "verified"}
GOLDEN_KEYS = {"id", "name", "converts", "rate", "note", "source", "verified"}
ROW_KEYS = {"id", "category", "item", "cost", "limit", "source", "verified"}
_UTC = _dt.timezone.utc


def row_id(category, item):
    return f"{category}-{slug(item)}"[:60]


def _keys_ok(row, keys):
    return isinstance(row, dict) and keys <= set(row) <= keys | {"verify"}


def _src_ok(row):
    return _ascii(row.get("source"), MAX_TEXT) and _verified_ok(row.get("verified"))


def _date(v):
    if not isinstance(v, str) or len(v) != 10:
        return None
    try:
        return _dt.date.fromisoformat(v)
    except ValueError:
        return None


# -- data file -------------------------------------------------------------------

def validate_data(doc):
    """The tracked reward_seals.json, checked; ValueError on any malformed row."""
    if not isinstance(doc, dict) or set(doc) - {"_doc"} != DATA_KEYS - {"_doc"}:
        raise ValueError("reward seal data must be {categories, golden, exchange}")
    cats = doc["categories"]
    if not isinstance(cats, list) or len(cats) != len(CATEGORIES):
        raise ValueError(f"categories must list exactly {', '.join(CATEGORIES)}")
    for want, c in zip(CATEGORIES, cats):
        if not _keys_ok(c, CAT_KEYS) or c["id"] != want:
            raise ValueError(f"category rows must be {{id, name, source, verified}} in order: {want}")
        if not _ascii(c["name"], 40) or not _src_ok(c):
            raise ValueError(f"category {want}: name / source / verified invalid")
    g = doc["golden"]
    if not _keys_ok(g, GOLDEN_KEYS) or g["id"] != "golden-seal" or not _ascii(g["name"], 40):
        raise ValueError("golden must be {id: golden-seal, name, converts, rate, note, source, verified}")
    if _date(g["converts"]) is None:
        raise ValueError("golden.converts must be a real YYYY-MM-DD date")
    if g["rate"] is not None and not _ascii(g["rate"], 120):
        raise ValueError("golden.rate must be null (not announced) or 1..120 ASCII chars")
    if not _ascii(g["note"], MAX_TEXT, allow_empty=True) or not _src_ok(g):
        raise ValueError("golden note / source / verified invalid")
    rows = doc["exchange"]
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError(f"exchange must be a list of at most {MAX_ROWS}")
    ids = set()
    for r in rows:
        if not _keys_ok(r, ROW_KEYS):
            raise ValueError(f"exchange rows must be {{{', '.join(sorted(ROW_KEYS))}}}")
        _check_row(r["category"], r["item"], r["cost"])
        lim = r["limit"]
        if lim is not None and (not _is_int(lim) or not 1 <= lim <= LIMIT_MAX):
            raise ValueError(f"exchange limit must be null or an int in 1..{LIMIT_MAX}")
        if not _src_ok(r):
            raise ValueError(f"exchange {r['item']!r}: source / verified invalid"[:200])
        if r["id"] != row_id(r["category"], r["item"]) or r["id"] in ids:
            raise ValueError(f"exchange id must be unique <category>-<slug(item)>: {r['id']!r}"[:200])
        ids.add(r["id"])
    return doc


def _check_row(category, item, cost):
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of {', '.join(CATEGORIES)}")
    if not _ascii(item, MAX_ITEM):
        raise ValueError(f"item must be 1..{MAX_ITEM} printable ASCII characters")
    if not _is_int(cost) or not 1 <= cost <= COST_MAX:
        raise ValueError(f"cost must be an int in 1..{COST_MAX}")


def load_data(path=None):
    p = Path(DATA_PATH if path is None else path)
    try:
        doc = json.loads(p.read_text(encoding="ascii"))
    except (OSError, ValueError) as e:  # ValueError covers UnicodeDecodeError
        raise ValueError(f"{p.name}: {e}"[:200]) from e
    return validate_data(doc)


# -- pure math ---------------------------------------------------------------------

def _count(v):
    return v if _is_int(v) and 0 <= v <= COUNT_MAX else None


def totals(counts):
    """{total, known, unknown: [category]} over the typed per-category counts
    (the Golden Seal is not a category and never sums in)."""
    counts = counts or {}
    known = {c: _count(counts.get(c)) for c in CATEGORIES}
    return {"total": sum(v for v in known.values() if v is not None),
            "known": sum(1 for v in known.values() if v is not None),
            "unknown": [c for c in CATEGORIES if known[c] is None]}


def afford(rows, counts):
    """Exchange rows + {afford, times, short}: affordable when the row's
    category count covers its cost; an unknown count yields None for all three."""
    out = []
    for r in rows:
        n = _count((counts or {}).get(r["category"]))
        if n is None:
            out.append(dict(r, afford=None, times=None, short=None))
        else:
            out.append(dict(r, afford=n >= r["cost"], times=n // r["cost"],
                            short=max(0, r["cost"] - n)))
    return out


def nearest(rows):
    """{category: {ready, next}}: `ready` = the dearest affordable row, `next`
    = the unaffordable row with the smallest shortfall (ties: cheaper, then id)."""
    out = {}
    for c in CATEGORIES:
        mine = [r for r in rows if r["category"] == c and r.get("afford") is not None]
        ok = sorted((r for r in mine if r["afford"]), key=lambda r: (-r["cost"], r["id"]))
        no = sorted((r for r in mine if not r["afford"]), key=lambda r: (r["short"], r["cost"], r["id"]))
        out[c] = {"ready": ok[0]["id"] if ok else None, "next": no[0]["id"] if no else None}
    return out


def conversion(held, converts, rate, now, at):
    """Golden Seal conversion state: {date, at_utc, in_s, held, passed, warn,
    rate, rate_text, text}. `at` = the conversion moment (that date's
    maintenance start); `warn` while it is ahead and seals are (or may be) held."""
    held = _count(held)
    passed = now >= at
    in_s = 0 if passed else int((at - now).total_seconds())
    rate_text = rate if isinstance(rate, str) and rate else UNKNOWN_RATE
    date = at.date().isoformat() if converts is None else converts
    if passed:
        text = f"Golden Seals converted at the {date} maintenance ({rate_text})"
    else:
        what = "Golden Seals (count not typed)" if held is None else f"{held} Golden Seals"
        text = (f"{what} convert to Reward Seals at the {date} maintenance - {rate_text};"
                " spend or plan them before")
    return {"date": date, "at_utc": _iso(at), "in_s": in_s, "held": held, "passed": passed,
            "warn": not passed and held != 0, "rate": rate if isinstance(rate, str) else None,
            "rate_text": rate_text, "text": text}


# -- service -----------------------------------------------------------------------

class SealService:
    """Operator seal counts + exchange rows over the tracked seal data.
    `maint_inputs` -> {slot, notices} (the app's effective maintenance inputs)
    resolves the conversion moment; every write returns the view."""

    def __init__(self, store, clock=time.time, data_path=None, maint_inputs=None):
        self.store = store
        self.clock = clock
        self.maint_inputs = maint_inputs or (lambda: {})
        self._lock = threading.Lock()
        try:
            self.data, self.data_error = load_data(data_path), None
        except ValueError as e:  # a broken data file never breaks the card
            self.data, self.data_error = None, str(e)

    def _now(self):
        return _dt.datetime.fromtimestamp(self.clock(), _UTC)

    def _load(self):
        doc = self.store.get(DOMAIN)
        raw = doc.get("counts") if isinstance(doc.get("counts"), dict) else {}
        counts = {k: _count(raw.get(k)) for k in CATEGORIES + (GOLDEN,)}
        ra = doc.get("counts_at") if isinstance(doc.get("counts_at"), dict) else {}
        counts_at = {k: ra[k] for k in counts if counts[k] is not None and isinstance(ra.get(k), str)}
        rows, seen = [], set()
        for r in doc.get("exchange") if isinstance(doc.get("exchange"), list) else []:
            try:
                _check_row(r.get("category"), r.get("item"), r.get("cost"))
            except (ValueError, AttributeError):
                continue
            rid = row_id(r["category"], r["item"])
            if r.get("id") == rid and rid not in seen:
                seen.add(rid)
                rows.append({"id": rid, "category": r["category"], "item": r["item"].strip(),
                             "cost": r["cost"]})
        return {"counts": counts, "counts_at": counts_at, "exchange": rows[:MAX_ROWS]}

    def _write(self, fn):
        with self._lock:
            doc = self._load()
            fn(doc)
            self.store.put(DOMAIN, dict(doc, updated=_iso(self._now())))
        return self.view()

    # -- writes ------------------------------------------------------------------

    def set_count(self, arg):
        """{category, count}: a typed seal count (category or "golden"); null clears it."""
        if not isinstance(arg, dict) or set(arg) != {"category", "count"}:
            raise ValueError("seal count must be {category, count}")
        key, n = arg["category"], arg["count"]
        if key not in CATEGORIES + (GOLDEN,):
            raise ValueError(f"category must be one of {', '.join(CATEGORIES + (GOLDEN,))}")
        if n is not None and (not _is_int(n) or not 0 <= n <= COUNT_MAX):
            raise ValueError(f"count must be null or an int in 0..{COUNT_MAX}")
        at = _iso(self._now())

        def go(doc):
            doc["counts"][key] = n
            if n is None:
                doc["counts_at"].pop(key, None)
            else:
                doc["counts_at"][key] = at
        return self._write(go)

    def ex_add(self, arg):
        """{category, item, cost}: an operator exchange row."""
        if not isinstance(arg, dict) or set(arg) != {"category", "item", "cost"}:
            raise ValueError("seal exchange must be {category, item, cost}")
        _check_row(arg["category"], arg["item"], arg["cost"])
        item = arg["item"].strip()
        rid = row_id(arg["category"], item)
        seeded = {r["id"] for r in (self.data or {}).get("exchange", [])}

        def go(doc):
            if rid in seeded or any(r["id"] == rid for r in doc["exchange"]):
                raise ValueError(f"exchange row already listed: {rid}")
            if len(doc["exchange"]) >= MAX_ROWS:
                raise ValueError(f"at most {MAX_ROWS} operator exchange rows")
            doc["exchange"].append({"id": rid, "category": arg["category"], "item": item,
                                    "cost": arg["cost"]})
        return self._write(go)

    def ex_del(self, rid):
        """Remove an operator exchange row (seed rows are edited in the data file)."""
        if not isinstance(rid, str) or not 1 <= len(rid) <= 60:
            raise ValueError("exchange id must be <category>-<slug>")

        def go(doc):
            keep = [r for r in doc["exchange"] if r["id"] != rid]
            if len(keep) == len(doc["exchange"]):
                raise ValueError(f"unknown operator exchange row: {rid}")
            doc["exchange"] = keep
        return self._write(go)

    # -- read --------------------------------------------------------------------

    def _convert_at(self, date):
        try:
            m = self.maint_inputs() or {}
            slot, notices = m.get("slot"), m.get("notices") or {}
        except Exception:  # noqa: BLE001 - an unreadable source = the data file slot
            slot, notices = None, {}
        try:
            return _maint.resolve(date, "before", slot, notices)
        except Exception:  # noqa: BLE001 - a bad slot / notice = the built-in default
            return _maint.resolve(date, "before")

    def _golden(self, held, now):
        g = (self.data or {}).get("golden")
        if g is None:
            return {"date": None, "at_utc": None, "in_s": None, "held": held, "passed": False,
                    "warn": False, "rate": None, "rate_text": UNKNOWN_RATE, "text": "",
                    "source": None, "verified": None}
        at = self._convert_at(_date(g["converts"]))
        return dict(conversion(held, g["converts"], g["rate"], now, at), source=g["source"],
                    verified=g["verified"], note=g["note"])

    def view(self):
        now = self._now()
        with self._lock:
            doc = self._load()
        cats = {c["id"]: c for c in (self.data or {}).get("categories", [])}
        rows = [dict({k: r[k] for k in ("id", "category", "item", "cost", "limit")},
                     origin="seed", source=r["source"], verified=r["verified"])
                for r in (self.data or {}).get("exchange", [])]
        rows += [dict(r, limit=None, origin="operator", source=None, verified=None)
                 for r in doc["exchange"]]
        rows = afford(rows, doc["counts"])
        counts = {c: doc["counts"][c] for c in CATEGORIES}
        return {"now": _iso(now),
                "categories": [{"id": c, "name": cats[c]["name"] if c in cats else c,
                                "count": counts[c], "at": doc["counts_at"].get(c),
                                "source": cats[c]["source"] if c in cats else None,
                                "verified": cats[c]["verified"] if c in cats else None}
                               for c in CATEGORIES],
                "counts": counts, "totals": totals(counts), "exchange": rows,
                "nearest": nearest(rows),
                "golden": self._golden(doc["counts"][GOLDEN], now),
                "data_error": self.data_error}

    def digest_rows(self):
        """Plan 074 `ending` rows: one Golden Seal conversion row while it warns."""
        g = self.view()["golden"]
        if not g["warn"] or g["at_utc"] is None:
            return []
        return [{"kind": "seal", "title": g["text"], "ends": g["at_utc"]}]
