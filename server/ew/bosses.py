"""World boss schedule (plan 031): NA table as sourced data, DST-correct next spawns.

The table is tracked static data (`data/world_bosses_na.json`, Pacific Time,
transcribed from the official Adventurer's Guide via research 0003); nothing reads
the in-game boss notification. Pacific time is computed with the US rule (DST from
the second Sunday of March 02:00 to the first Sunday of November 02:00 local), not
`zoneinfo`, which has no tz data on Windows without a package. Loot ticks are
operator clicks stored in the `bosses` store domain.

Plan 176: from the maintenance before a US clock change until the change, NA
spawns sit `offset_hours` off the PT table (fall +1, spring -1; official
notice 2026-10-22). Windows come from tracked `data/dst_windows.json`; years it
does not list are derived by rule (Thursday maintenance before the change, to
the change) and marked `derived`. The daily / weekly reset stays on UTC.
"""

import datetime as _dt
import functools
import json
import re
import threading
import time
from pathlib import Path

from . import maint
from .today import DATE_RE, last_weekly_reset, next_weekly_reset

TABLE_FILE = Path(__file__).resolve().parent / "data" / "world_bosses_na.json"
WINDOWS_FILE = Path(__file__).resolve().parent / "data" / "dst_windows.json"
AT_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
GARMOTH = "Garmoth"
TICK_WINDOW_DAYS = 7  # a tick may name today's PT day or up to this many days back
DST_ASSUMPTION = ("spawns follow the PT wall clock, except inside a DST transition "
                  "window (maintenance before the clock change to the change, plan 176)")
DST_PENDING_DAYS = 7  # plan 176: digest line this far ahead of an unverified window
WINDOW_KEYS = {"start_utc", "end_utc", "offset_hours", "source", "verified"}
DERIVED_SOURCE = "derived: Thursday maintenance before the US clock change, to the change"
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_DAY = _dt.timedelta(days=1)
_UTC = _dt.timezone.utc


# -- Pacific time (US rule) ---------------------------------------------------

def _nth_sunday(year, month, n):
    first = _dt.date(year, month, 1)
    return first + _dt.timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))


def _dst_bounds_local(year):
    """DST [start, end) in PT wall clock: 2nd Sun Mar 02:00 .. 1st Sun Nov 02:00."""
    two = _dt.time(2, 0)
    return (_dt.datetime.combine(_nth_sunday(year, 3, 2), two),
            _dt.datetime.combine(_nth_sunday(year, 11, 1), two))


def _utc(now):
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(_UTC)


def pt_offset_hours(now):
    """UTC offset of Pacific time at instant `now`: -7 (PDT) or -8 (PST)."""
    n = _utc(now)
    start, end = _dst_bounds_local(n.year)
    start_utc = (start + _dt.timedelta(hours=8)).replace(tzinfo=_UTC)  # 02:00 PST
    end_utc = (end + _dt.timedelta(hours=7)).replace(tzinfo=_UTC)      # 02:00 PDT
    return -7 if start_utc <= n < end_utc else -8


def utc_to_pt(now):
    """Instant -> naive PT wall-clock datetime."""
    n = _utc(now)
    return (n + _dt.timedelta(hours=pt_offset_hours(n))).replace(tzinfo=None)


def pt_to_utc(local):
    """Naive PT wall-clock datetime -> aware UTC. The repeated 01:xx hour in
    November resolves to PDT (first occurrence); the skipped 02:xx hour in March
    resolves to PDT too. No table slot falls in either hour."""
    if local.tzinfo is not None:
        raise ValueError("local must be a naive PT datetime")
    start, end = _dst_bounds_local(local.year)
    off = 7 if start <= local < end else 8
    return (local + _dt.timedelta(hours=off)).replace(tzinfo=_UTC)


def _iso(when):
    return when.astimezone(_UTC).replace(microsecond=0).isoformat()


def _parse_iso(s):
    if not isinstance(s, str):
        return None
    try:
        when = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return when if when.tzinfo is not None else None


# -- DST transition windows (plan 176) --------------------------------------------

def load_windows(path=None):
    """Tracked `data/dst_windows.json` -> [{start_utc, end_utc, offset_hours,
    source, verified}] (validated, ISO strings kept); raises ValueError."""
    try:
        doc = json.loads(Path(path or WINDOWS_FILE).read_text(encoding="ascii"))
    except (OSError, ValueError) as e:
        raise ValueError(f"dst windows unreadable: {type(e).__name__}") from e
    rows = doc.get("windows") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        raise ValueError("dst windows must be an object with a windows list")
    out = []
    for w in rows:
        if not (isinstance(w, dict) and set(w) == WINDOW_KEYS):
            raise ValueError(f"dst window must have exactly {sorted(WINDOW_KEYS)}")
        start, end = _parse_iso(w["start_utc"]), _parse_iso(w["end_utc"])
        if start is None or end is None or end <= start:
            raise ValueError("dst window start_utc / end_utc must be aware ISO, end after start")
        if w["offset_hours"] not in (1, -1) or isinstance(w["offset_hours"], bool):
            raise ValueError("dst window offset_hours must be 1 or -1")
        if not isinstance(w["source"], str) or not w["source"]:
            raise ValueError("dst window source must be text")
        v = w["verified"]
        if not (v is False or (isinstance(v, str) and DATE_RE.match(v))):
            raise ValueError("dst window verified must be false or a YYYY-MM-DD date")
        out.append(dict(w))
    return out


@functools.lru_cache(maxsize=1)
def _listed_default():
    try:
        return tuple(load_windows())
    except ValueError:  # a broken file still leaves the derived windows
        return ()


def _window(start, end, offset, source, verified, derived):
    return {"start_utc": _iso(start), "end_utc": _iso(end), "offset_hours": offset,
            "source": source, "verified": verified, "derived": derived,
            "start": start, "end": end}


@functools.lru_cache(maxsize=16)
def _derived(year):
    """Rule windows of `year`: spring (-1) and fall (+1), from the maintenance
    start on the Thursday before the change to the change instant."""
    hh, mm = (int(x) for x in maint.load_slot()["start_utc"].split(":"))
    out = []
    for month, n, off, utc_h in ((3, 2, -1, 10), (11, 1, 1, 9)):  # 02:00 PST / 02:00 PDT
        sunday = _nth_sunday(year, month, n)
        end = _dt.datetime.combine(sunday, _dt.time(utc_h), tzinfo=_UTC)
        start = _dt.datetime.combine(sunday - 3 * _DAY, _dt.time(hh, mm), tzinfo=_UTC)
        out.append(_window(start, end, off, DERIVED_SOURCE, False, True))
    return tuple(out)


def dst_windows(now, listed=None):
    """Listed windows plus derived ones for the years around `now` that no
    listed window overlaps, in start order. Rows carry `derived` and parsed
    `start` / `end` datetimes."""
    n = _utc(now)
    rows = [_window(_parse_iso(w["start_utc"]).astimezone(_UTC),
                    _parse_iso(w["end_utc"]).astimezone(_UTC), w["offset_hours"],
                    w["source"], w["verified"], False)
            for w in (_listed_default() if listed is None else listed)]
    for year in (n.year - 1, n.year, n.year + 1):
        for d in _derived(year):
            if not any(r["start"] < d["end"] and d["start"] < r["end"] for r in rows):
                rows.append(dict(d))
    return sorted(rows, key=lambda r: r["start"])


def _window_at(at, windows):
    for w in windows:
        if w["start"] <= at < w["end"]:
            return w
    return None


def _ends_pt(w):
    """'Sun 02:00 PT': the window end on the PT wall clock in force just before it."""
    local = w["end"] + _dt.timedelta(hours=pt_offset_hours(w["end"] - _dt.timedelta(seconds=1)))
    return f"{_WEEKDAYS[local.weekday()]} {local:%H:%M} PT"


def dst_info(w):
    """API / banner shape of one window, or None."""
    if w is None:
        return None
    return {"shift_h": w["offset_hours"], "start_utc": w["start_utc"], "end_utc": w["end_utc"],
            "ends_pt": _ends_pt(w), "source": w["source"], "verified": w["verified"],
            "derived": w["derived"]}


def dst_pending(now, windows=None):
    """Plan 176 digest input: the first window not `verified` that is active or
    starts within DST_PENDING_DAYS of `now`, else None."""
    n = _utc(now)
    for w in dst_windows(n) if windows is None else windows:
        if not w["verified"] and w["start"] - DST_PENDING_DAYS * _DAY <= n < w["end"]:
            return {"start_utc": w["start_utc"], "end_utc": w["end_utc"],
                    "shift_h": w["offset_hours"], "derived": w["derived"], "verified": False}
    return None


# -- table -----------------------------------------------------------------------

def load_table(path=None):
    """Tracked `data/world_bosses_na.json` -> validated doc; raises ValueError."""
    try:
        doc = json.loads(Path(path or TABLE_FILE).read_text(encoding="ascii"))
    except (OSError, ValueError) as e:
        raise ValueError(f"boss table unreadable: {type(e).__name__}") from e
    if not isinstance(doc, dict) or doc.get("tz") != "PT":
        raise ValueError("boss table must be an object with tz PT")
    for key in ("source", "verified", "note"):
        if not isinstance(doc.get(key), str) or not doc[key]:
            raise ValueError(f"boss table {key} must be text")
    rules = doc.get("rules")
    if not (isinstance(rules, dict) and isinstance(rules.get("despawn_min"), int)
            and isinstance(rules.get("short_despawn"), dict)
            and all(isinstance(v, int) for v in rules["short_despawn"].values())
            and isinstance(rules.get("garmoth_loot_per_week"), int)):
        raise ValueError("boss table rules malformed")
    slots = doc.get("slots")
    if not isinstance(slots, list) or not slots:
        raise ValueError("boss table slots must be a non-empty list")
    for s in slots:
        if not (isinstance(s, dict) and set(s) == {"weekday", "at", "bosses"}):
            raise ValueError("slot must have exactly weekday, at, bosses")
        wd = s["weekday"]
        if not isinstance(wd, int) or isinstance(wd, bool) or not 0 <= wd <= 6:
            raise ValueError("slot weekday must be an int 0-6 (Mon=0)")
        if not isinstance(s["at"], str) or not AT_RE.match(s["at"]):
            raise ValueError("slot at must be HH:MM")
        if not (isinstance(s["bosses"], list) and s["bosses"]
                and all(isinstance(b, str) and b for b in s["bosses"])):
            raise ValueError("slot bosses must be a non-empty list of names")
    return doc


def _by_weekday(table):
    out = {d: [] for d in range(7)}
    for s in table["slots"]:
        out[s["weekday"]].append(s)
    for rows in out.values():
        rows.sort(key=lambda s: s["at"])
    return out


def _spawn(table, slot, day, windows=None):
    """(aware UTC spawn, row) of `slot` on PT table `day`. Plan 176: a spawn whose
    table instant falls in a DST transition window moves by its offset; the row
    carries `shift_h` and `window` {source, ends, verified, derived} (or None)."""
    hh, mm = slot["at"].split(":")
    local = _dt.datetime.combine(day, _dt.time(int(hh), int(mm)))
    rules = table["rules"]
    base = pt_to_utc(local)
    w = _window_at(base, dst_windows(base) if windows is None else windows)
    shift = w["offset_hours"] if w else 0
    at = base + _dt.timedelta(hours=shift)
    off = _dt.timezone(_dt.timedelta(hours=pt_offset_hours(at)))
    despawn = max(rules["short_despawn"].get(b, rules["despawn_min"]) for b in slot["bosses"])
    return at, {"bosses": list(slot["bosses"]), "at_utc": _iso(at),
                "at_pt": at.astimezone(off).isoformat(),
                "day": day.isoformat(), "despawn_min": despawn, "shift_h": shift,
                "window": None if w is None else {
                    "source": w["source"], "ends": w["end_utc"], "verified": w["verified"],
                    "derived": w["derived"]}}


def next_spawns(now_utc, n=3, table=None, windows=None):
    """The next `n` spawns at or after `now_utc`: [{bosses, at_utc, at_pt, day,
    despawn_min, shift_h, window}] in time order. `day` is the PT table day.
    `windows` (plan 176) defaults to `dst_windows(now)`; [] turns shifts off."""
    now = _utc(now_utc)
    table = table or load_table()
    windows = dst_windows(now) if windows is None else windows
    week = _by_weekday(table)
    out, day = [], utc_to_pt(now).date() - _DAY  # a +1 h shift can push a slot past midnight
    full = False
    for _ in range(7 * (n // max(1, len(table["slots"])) + 2) + 1):
        for slot in week[day.weekday()]:
            at, row = _spawn(table, slot, day, windows)
            if at >= now:
                out.append((at, row))
        day += _DAY
        if full:  # one more table day collected: a 1 h shift cannot reorder past it
            break
        full = len(out) >= n
    return [row for _, row in sorted(out, key=lambda p: p[0])][:n]


# -- service ---------------------------------------------------------------------

class BossService:
    """Store domain `bosses`: {"looted": {"<PT day>|<boss>": "<iso ticked_at>"},
    "by": {"<PT day>|<boss>": "auto"}, "no_auto": ["<PT day>|<boss>"],
    "updated": "<iso>"}. Plan 111: `by` marks the ticks an OCR loot read made;
    an untick (operator or Undo) lists the key in `no_auto` so no later shot
    re-ticks it."""

    def __init__(self, store, clock=time.time, table=None, windows=None):
        self.store = store
        self.clock = clock
        self.table = table or load_table()
        self.listed = windows  # plan 176: listed DST windows (None = the tracked file)
        self._week = _by_weekday(self.table)
        self._lock = threading.Lock()

    def _now(self):
        return _dt.datetime.fromtimestamp(self.clock(), _UTC)

    def _load(self):
        raw = self.store.get("bosses").get("looted")
        out = {}
        for k, v in (raw.items() if isinstance(raw, dict) else ()):
            day, _, boss = k.partition("|") if isinstance(k, str) else ("", "", "")
            if DATE_RE.match(day) and boss and _parse_iso(v) is not None:
                out[k] = v
        return out

    def _check(self, arg, now):
        if not isinstance(arg, dict) or set(arg) != {"boss", "day"}:
            raise ValueError("tick must be {boss, day}")
        boss, day = arg["boss"], arg["day"]
        if not isinstance(day, str) or not DATE_RE.match(day):
            raise ValueError("day must be an ISO date YYYY-MM-DD (PT)")
        try:
            d = _dt.date.fromisoformat(day)
        except ValueError:
            raise ValueError("day must be a real date") from None
        today = utc_to_pt(now).date()
        if not today - TICK_WINDOW_DAYS * _DAY <= d <= today:
            raise ValueError(f"day must be today (PT) or up to {TICK_WINDOW_DAYS} days back")
        if not isinstance(boss, str) or not any(
                boss in s["bosses"] for s in self._week[d.weekday()]):
            raise ValueError(f"boss must be one that spawns on {day} (PT)")
        return f"{day}|{boss}"

    def _extra(self):
        """({key: "auto"}, [blocked key]) - plan 111 auto-tick bookkeeping."""
        doc = self.store.get("bosses")
        by = doc.get("by") if isinstance(doc.get("by"), dict) else {}
        blocked = doc.get("no_auto") if isinstance(doc.get("no_auto"), list) else []
        return ({k: v for k, v in by.items() if isinstance(k, str) and v == "auto"},
                [k for k in blocked if isinstance(k, str)])

    def _save(self, looted, now, by=None, blocked=None):
        if by is None or blocked is None:
            by, blocked = self._extra()
        floor = (utc_to_pt(now).date() - TICK_WINDOW_DAYS * _DAY).isoformat()
        looted = {k: v for k, v in looted.items() if k.split("|", 1)[0] >= floor}
        self.store.put("bosses", {"looted": looted,
                                  "by": {k: v for k, v in by.items() if k in looted},
                                  "no_auto": sorted({k for k in blocked
                                                     if k.split("|", 1)[0] >= floor}),
                                  "updated": _iso(now)})

    def _garmoth(self, looted, now):
        reset = last_weekly_reset(now)
        return sum(1 for k, v in looted.items()
                   if k.endswith("|" + GARMOTH) and _parse_iso(v) >= reset)

    def view(self):
        """GET /api/bosses body."""
        now = self._now()
        today = utc_to_pt(now).date()
        windows = dst_windows(now, self.listed)
        remaining, slots = [], []
        for slot in self._week[today.weekday()]:
            at, row = _spawn(self.table, slot, today, windows)
            gone = at + _dt.timedelta(minutes=row["despawn_min"]) <= now
            if not gone:
                remaining.append(dict(row, up=at <= now))
            slots.append(dict(row, up=at <= now and not gone, past=gone))  # plan 032
        looted_raw = self._load()
        by = self._extra()[0]
        looted, auto = {}, {}
        for k in sorted(looted_raw):
            day, _, boss = k.partition("|")
            looted.setdefault(day, []).append(boss)
            if by.get(k) == "auto":
                auto.setdefault(day, []).append(boss)
        garmoth = self._garmoth(looted_raw, now)
        nxt = next_spawns(now, 3, self.table, windows)
        # Plan 176 banner: the window in force now, else the one the next spawns sit in.
        active = _window_at(now, windows) or next(
            (_window_at(_parse_iso(s["at_utc"]) - _dt.timedelta(hours=s["shift_h"]), windows)
             for s in nxt if s["shift_h"]), None)
        return {"now": _iso(now), "tz": self.table["tz"], "source": self.table["source"],
                "verified": self.table["verified"], "dst_assumption": DST_ASSUMPTION,
                "rules": self.table["rules"], "dst": dst_info(active),
                "next": nxt,
                "today": {"day": today.isoformat(), "remaining": remaining, "slots": slots},
                "looted": looted, "auto": auto,
                "garmoth": {"looted": garmoth,
                            "cap": self.table["rules"]["garmoth_loot_per_week"],
                            "week_reset": _iso(next_weekly_reset(now))}}

    def dst_pending(self):
        """Plan 176: digest input - an unverified window active or within 7 days."""
        now = self._now()
        return dst_pending(now, dst_windows(now, self.listed))

    def tick(self, arg):
        with self._lock:
            now = self._now()
            key = self._check(arg, now)
            looted = self._load()
            looted.setdefault(key, _iso(now))
            self._save(looted, now)
        return self.view()

    def untick(self, arg):
        """Operator untick or plan 111 Undo: the key is also blocked from a
        later auto tick."""
        with self._lock:
            now = self._now()
            key = self._check(arg, now)
            looted = self._load()
            looted.pop(key, None)
            by, blocked = self._extra()
            self._save(looted, now, by, blocked + [key])
        return self.view()

    def looted_since(self, since):
        """Plan 114: loot ticks (operator or auto) made at or after `since`
        (aware datetime)."""
        return sum(1 for v in self._load().values() if _parse_iso(v) >= since)

    def auto_tick(self, day, boss):
        """Plan 111: an OCR loot read ticks `boss` on PT `day` with by: auto.
        False (nothing written) when it is ticked already, an untick blocked
        it, or the Garmoth weekly cap is reached; ValueError on a bad day /
        boss (as tick)."""
        with self._lock:
            now = self._now()
            key = self._check({"boss": boss, "day": day}, now)
            looted = self._load()
            by, blocked = self._extra()
            if key in looted or key in blocked:
                return False
            if boss == GARMOTH and \
                    self._garmoth(looted, now) >= self.table["rules"]["garmoth_loot_per_week"]:
                return False
            looted[key] = _iso(now)
            by[key] = "auto"
            self._save(looted, now, by, blocked)
        return True
