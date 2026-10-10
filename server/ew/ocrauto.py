"""Auto-OCR (plan 063): every new screenshot taken while logged in is read
without a button press; confident fields are committed, the rest are queued.

Trigger: a GameWatch listener keeps the logged_in windows; `scan()` enqueues a
watcher-listed shot (plan 008) whose mtime falls inside a window or within
AFTER_LOGOUT_S after it. Shots taken while the game is closed are marked seen
and never read. One worker thread drains the queue through the plan 009
OcrService (same engine chain, same cache), one OCR at a time, at most
`ocr.daily_cap` a local day.

Confidence: every extracted field is {value, conf 0..1, why}. Fields at or over
`ocr.auto_commit_min` are committed (silver sample in store domain `silver`,
buff timer through GrindService) with source `ocr:<file>` and an undo id; the
rest go to store domain `ocr_review` (MAX_REVIEW, oldest dropped) for accept /
fix / discard. Plan 066 adds level / XP % samples (held for review when they
break the history), AP / AAP / DP and a book-use suggestion (always reviewed)
through `ocrinfer`; plan 088 adds Monster Zone Info reads (`zoneinfo`, queued
for review below the gate). Plan 111: a book-use suggestion at or over
AUTO_APPLY_MIN is applied instead of queued, a shot near a world boss spawn
whose text names that boss ticks its loot (`bosses`, by: auto), and every such
auto-apply (and every committed zone read) is listed in store domain
`auto_applied` with an Undo. Plan 115: an event currency balance read from
the exchange window / a tooltip sets that event's balance in eventcurrency
(held when below the logged projection). Nothing reaches the game: the input is image files the operator
saved with the game's own screenshot key, read after they are written.
"""

import datetime as _dt
import math
import re
import threading
import time

from . import autotick, ocr, ocrinfer, zoneinfo
from .grind import MAX_BUFF_MINUTES, MAX_LOOT_COUNT, MAX_SILVER, SEED_BUFFS
from .leveling import _ok_pct
from .levels import LEVEL_RANGE
from .progress import GS_KEYS, GS_RANGE
from .xpbooks import SIZES

AUTO_COMMIT_MIN = 0.9
# Plan 111: a book-use or boss-loot suggestion at or over this is applied (not
# a setting - plan 080 purged tunables); below it the book queues as before and
# a boss stays the plan 068 time-only suggestion.
AUTO_APPLY_MIN = 0.95
MAX_APPLIED = 200
VIEW_APPLIED = 10
BOSS_PROX_EARLY = 0.5    # x factor: a shot before the spawn (the boss was not up yet)
DAILY_CAP = 120
AFTER_LOGOUT_S = 60
MAX_REVIEW = 50
MAX_COMMITS = 200
MAX_SEEN = 500
MAX_SAMPLES = 500
MAX_WINDOWS = 50
VIEW_COMMITS = 20
POLL_S = 2.0
LOGGED_IN = "logged_in"
MAX_READS = 50
MAX_LOOT_ROWS = 60
# Plan 081: planner reads (inventory weight / slots, CP, market fame bonus).
PLANNER_KINDS = ("weight", "slots", "cp", "fame")
# Plan 088: a Monster Zone Info read (zone, recommended level, per-kill EXP).
# Plan 113: a loot-window row (table or catalog item + count) under the gate.
# Plan 115: an event currency balance (exchange window / tooltip) -> eventcurrency.
CURRENCY_KIND = "currency_balance"
KINDS = ("silver", "buff", "level", "gear", "book_use") + PLANNER_KINDS + (
    zoneinfo.KIND, "loot", CURRENCY_KIND)
# a book suggestion and a zone read are accept / discard only; a loot fix is a count
FIX_KINDS = ("silver", "buff", "level", "gear") + PLANNER_KINDS + ("loot", CURRENCY_KIND)
LOOT_KEYS = {"name", "count", "id", "source", "spot", "started"}
LOOT_SOURCES = ("table", "catalog")

# Silver confidence (separators between the digit groups of the read amount).
CONF_GROUPED = 0.97      # 1,234,567 - the game's own format
CONF_DOTTED = 0.93       # 1.234.567 - a comma read as a dot keeps the value
CONF_SPACED_SEP = 0.85   # "1, 234 ,567" - separator with OCR spacing
CONF_SPACE_GROUPS = 0.8  # "1 234 567" - a comma read as a space (or two numbers)
CONF_MIXED = 0.6         # 1,234.567 - mixed separators
CONF_SHORT = 0.95        # <= 3 digits: no grouping expected
CONF_UNGROUPED = 0.7     # >= 4 digits and no separator: commas were dropped
CONF_BROKEN = 0.3        # the amount runs on into a separator + glyph: truncated
CONF_DISAGREE = 0.3      # a second engine read another number
IMPLAUSIBLE = 0.6        # x factor when the value is 10x off the last committed
IMPLAUSIBLE_RATIO = 10
# Buff confidence: name match ratio x time-parse validity.
TIME_OK = 1.0
TIME_NEIGHBOUR = 0.85    # the time came from a line beside / below the name
TIME_ODD = 0.6           # units out of order, repeated, or out of range
TIME_STRAY = 0.8         # another bare number sits beside the time
TIME_AT_CAP = 0.7        # clamped to the 30-day maximum
# Plan 109: a Value Pack lasts 30 days, so a read at the cap is a normal read
# for it; a read ending this much earlier than the armed timer is held (the
# tooltip shows whole hours, so a re-read of the same timer stays inside it).
VP_NAME = "value pack"
VP_EARLY_SLACK_S = 3600

_SEP_RUN = re.compile(r"[,. ]+")
_BROKEN_AFTER = re.compile(r"^ ?[,.] ?[^\s,.]")
_BROKEN_BEFORE = re.compile(r"[^\s,.:] ?[,.] ?$")
_UNIT_ORDER = {"d": 0, "h": 1, "m": 2, "s": 3}
_UNIT_MAX = {"h": 24, "m": 60, "s": 60}


# -- confidence ------------------------------------------------------------------

def _separator_conf(raw):
    """(conf, why) from the digit groups and separators of one amount string."""
    groups = [g for g in _SEP_RUN.split(raw) if g]
    seps = _SEP_RUN.findall(raw)
    if len(groups) == 1:
        if len(groups[0]) <= 3:
            return CONF_SHORT, "short amount"
        return CONF_UNGROUPED, "no digit grouping"
    kinds = {s.strip() or " " for s in seps}
    if kinds == {" "}:
        return CONF_SPACE_GROUPS, "groups split by spaces"
    if len(kinds) > 1:
        return CONF_MIXED, "mixed separators"
    if any(s != s.strip() for s in seps):
        return CONF_SPACED_SEP, "separator with spacing"
    if kinds == {"."}:
        return CONF_DOTTED, "dot grouped"
    return CONF_GROUPED, "comma grouped"


def silver_field(doc, last=None, alt=None):
    """{kind, name, value, conf, why} for the silver amount in an OCR doc, or None.
    `last`: the last committed silver (plausibility); `alt`: another engine's
    read of the same shot (agreement), when one ran."""
    lines = ocr._lines(doc.get("lines") if isinstance(doc, dict) else None)
    hit = ocr._silver_hit(lines)
    if hit is None:
        return None
    value, li, start, end = hit
    text = lines[li]["text"]
    conf, why = _separator_conf(text[start:end])
    whys = [why]
    if _BROKEN_AFTER.match(text[end:]) or _BROKEN_BEFORE.search(text[:start]):
        conf = min(conf, CONF_BROKEN)
        whys.append("amount runs into a broken group")
    if isinstance(last, int) and last > 0 and value >= 0:
        if value > last * IMPLAUSIBLE_RATIO or value * IMPLAUSIBLE_RATIO < last:
            conf *= IMPLAUSIBLE
            whys.append("10x off the last committed silver")
    if alt is not None:
        if alt == value:
            conf = 1 - (1 - conf) / 2
            whys.append("engines agree")
        else:
            conf = min(conf, CONF_DISAGREE)
            whys.append("engines disagree")
    return {"kind": "silver", "name": "silver", "value": value,
            "conf": round(conf, 3), "why": "; ".join(whys)}


def time_conf(text, cap_ok=False):
    """(minutes or None, conf, why) for the duration in one text run.
    `cap_ok`: the 30-day cap is the buff's own length (plan 109 Value Pack)."""
    hits = list(ocr.DURATION.finditer(text if isinstance(text, str) else ""))
    minutes = ocr.duration_minutes(text)
    if minutes is None:
        return None, 0.0, "no time"
    conf, why = TIME_OK, "time parsed"
    units = [m.group(2)[0].lower() for m in hits]
    order = [_UNIT_ORDER[u] for u in units]
    if order != sorted(set(order)):
        conf, why = TIME_ODD, "time units out of order or repeated"
    elif any(int(m.group(1)) >= _UNIT_MAX[u] for m, u in zip(hits, units)
             if u in _UNIT_MAX and units.index(u) > 0):
        conf, why = TIME_ODD, "time field out of range"
    rest = ocr.DURATION.sub(" ", text)
    if re.search(r"\d", rest):
        conf, why = min(conf, TIME_STRAY), "stray number beside the time"
    if minutes >= MAX_BUFF_MINUTES and not cap_ok:
        conf, why = min(conf, TIME_AT_CAP), "time at the 30-day cap"
    return minutes, conf, why


def _is_vp(name):
    return isinstance(name, str) and name.strip().lower() == VP_NAME


def buff_fields(doc, names=SEED_BUFFS):
    """[{kind, name, value (minutes), conf, why}]: one per buff name with a
    time, first sighting wins. conf = name match ratio x time-parse validity;
    an exact (normalised) name is 1.0, else the plan 040 1 - edit distance."""
    lines = ocr._lines(doc.get("lines") if isinstance(doc, dict) else None)
    known = ocr._loot_names(list(names))
    out, seen = [], set()

    def add(name, ratio, minutes, tconf, why):
        if name in seen or minutes is None:
            return
        seen.add(name)
        out.append({"kind": "buff", "name": name, "value": minutes,
                    "conf": round(ratio * tconf, 3),
                    "why": f"name {'exact' if ratio == 1 else f'~{ratio:.2f}'}; {why}"})

    for i, ln in enumerate(lines):
        found = ocr._find_names(ln["text"], names)
        if not found:
            name, d = ocr._best_name(ln["text"], known) if known else (None, None)
            if name is not None:
                minutes, tconf, why = time_conf(ln["text"], _is_vp(name))
                add(name, round(1 - d, 2), minutes, tconf, why)
            continue
        for name, rest in found:
            minutes, tconf, why = time_conf(rest, _is_vp(name))
            if minutes is None and len(found) == 1:
                for b in ocr._neighbours(lines, i):
                    if ocr._find_name(b["text"], names)[0] is not None:
                        continue
                    minutes, tconf, why = time_conf(b["text"], _is_vp(name))
                    if minutes is not None:
                        tconf, why = min(tconf, TIME_NEIGHBOUR), why + " (neighbour line)"
                        break
            add(name, 1, minutes, tconf, why)
    return out


def boss_name_conf(doc, boss):
    """Plan 111: how well the OCR text names `boss` - 1.0 for the (normalised)
    name on a line, else the best plan 040 1 - edit distance, else 0. The loot
    window title reads "<boss>'s ..." so it matches by the same name."""
    lines = ocr._lines(doc.get("lines") if isinstance(doc, dict) else None)
    known = ocr._loot_names([boss])
    best = 0.0
    for ln in lines:
        if ocr._find_names(ln["text"], [boss]):
            return 1.0
        _, d = ocr._best_name(ln["text"], known) if known else (None, None)
        if d is not None:
            best = max(best, round(1 - d, 3))
    return best


# -- helpers ---------------------------------------------------------------------

def _iso(ts):
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).replace(microsecond=0).isoformat()


def _ts(s):
    if not isinstance(s, str):
        return None
    try:
        when = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return when.timestamp() if when.tzinfo is not None else None


def _ok_int(v, lo, hi):
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def _ok_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _ok_conf(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1


def _str(v, cap=200):
    return v[:cap] if isinstance(v, str) else ""


def _check_value(kind, v):
    if kind == "silver" and _ok_int(v, 0, MAX_SILVER):
        return v
    if kind == "buff" and _ok_int(v, 1, MAX_BUFF_MINUTES):
        return v
    if kind == "gear" and _ok_int(v, *GS_RANGE):
        return v
    if kind == "level":
        if isinstance(v, dict) and set(v) == {"level", "pct"} \
                and _ok_int(v["level"], *LEVEL_RANGE) and _ok_pct(v["pct"]):
            return {"level": v["level"], "pct": v["pct"]}
        raise ValueError(f"level value must be {{level {LEVEL_RANGE[0]}..{LEVEL_RANGE[1]}, "
                         "pct 0..100 with at most 3 decimals}")
    if kind == "book_use":
        if isinstance(v, dict) and set(v) == {"size", "pct_before", "pct_after"} \
                and v["size"] in SIZES and _ok_pct(v["pct_before"]) and _ok_pct(v["pct_after"]):
            return dict(v)
        raise ValueError("book_use value must be {size, pct_before, pct_after}")
    if kind == "weight":
        if isinstance(v, dict) and set(v) == {"used", "max"} \
                and all(_ok_num(v[k]) for k in v) \
                and 1 <= v["max"] <= ocrinfer.MAX_LT_READ and 0 <= v["used"] <= 2 * v["max"]:
            return {"used": v["used"], "max": v["max"]}
        raise ValueError(f"weight value must be {{used, max}} LT, max 1..{ocrinfer.MAX_LT_READ}")
    if kind == "slots":
        lo, hi = ocrinfer.SLOTS_RANGE
        if isinstance(v, dict) and set(v) == {"used", "total"} and _ok_int(v["total"], lo, hi) \
                and _ok_int(v["used"], 0, v["total"]):
            return {"used": v["used"], "total": v["total"]}
        raise ValueError(f"slots value must be {{used, total}}, total {lo}..{hi}")
    if kind == "cp" and _ok_int(v, 0, ocrinfer.CP_MAX_READ):
        return v
    if kind == CURRENCY_KIND and _ok_int(v, 0, ocrinfer.CUR_MAX_READ):
        return v
    if kind == zoneinfo.KIND:
        return zoneinfo.check_value(v)
    if kind == "fame":
        if _ok_num(v) and 0 <= v <= ocrinfer.FAME_MAX_READ:
            return v
        raise ValueError(f"fame value must be a number 0..{ocrinfer.FAME_MAX_READ}")
    if kind == "loot":
        if (isinstance(v, dict) and set(v) == LOOT_KEYS and isinstance(v["name"], str)
                and v["name"].strip() and len(v["name"]) <= 200
                and _ok_int(v["count"], 1, MAX_LOOT_COUNT) and v["source"] in LOOT_SOURCES
                and (v["id"] is None or _ok_int(v["id"], 1, 2 ** 31 - 1))
                and isinstance(v["spot"], str) and _ts(v["started"]) is not None):
            return dict(v)
        raise ValueError(f"loot value must be {{name, count 1..{MAX_LOOT_COUNT}, id, "
                         "source: table|catalog, spot, started}")
    ranges = {"silver": f"0..{MAX_SILVER}", "buff": f"1..{MAX_BUFF_MINUTES}",
              "gear": f"{GS_RANGE[0]}..{GS_RANGE[1]}", "cp": f"0..{ocrinfer.CP_MAX_READ}",
              CURRENCY_KIND: f"0..{ocrinfer.CUR_MAX_READ}"}
    raise ValueError(f"{kind} value must be an int {ranges.get(kind, '')}".rstrip())


class AutoOcr:
    """Store domains: `ocr_auto` {day, count, seen: [key], commits: [{id, file,
    kind, name, value, at, shot_at, prev?, sample?, undone}], next}, `ocr_review`
    {items: [{id, file, kind, name, value, conf, why, at, shot_at}], next},
    `silver` {samples: [{id, at, value, source}]} (oldest first); plan 111
    `auto_applied` {items: [{id, at, kind, value, conf, file, undo_id, undone}],
    next} (newest first, MAX_APPLIED)."""

    def __init__(self, store, game, reader, grind, settings=None, clock=time.time,
                 on_change=None, leveling=None, progress=None, play=None, regions=None,
                 loot_target=None, zones=None, bosses=None, catalog=None, currency=None):
        self.store = store
        self.game = game
        self.reader = reader              # OcrService (plan 009): .doc(name) -> {text, lines}
        self.grind = grind                # GrindService: buff / restore_buff
        # Plan 066 (each optional; without one its fields are not read):
        self.leveling = leveling          # LevelingService: level / XP samples, books
        self.progress = progress          # ProgressService: gs stats
        self.play = play                  # fn() -> PlaySession.view() (silver/h window)
        # Plan 081: fn() -> {spot, started, names, end?} of the running grind session
        # (plan 113: or the just-closed auto one, with its `end`), or None; its loot
        # counts read from each shot land in `ocr_loot`.
        self.loot_target = loot_target
        # Plan 113: fn() -> {(id, sid): name}, the plan 028 item-name index; off-table
        # loot lines are matched against it. Without one only the table matches.
        self.catalog = catalog
        # Plan 088: ZoneXpService; without one zone panels are not read.
        self.zones = zones
        # Plan 111: BossService; without one boss loot is never auto-ticked.
        self.bosses = bosses
        # Plan 115: CurrencyService; without one event currency is not read.
        self.currency = currency
        self.zone_titles = zoneinfo.load_titles()
        self.regions = regions if regions is not None else ocrinfer.load_regions()
        self.settings = settings or (lambda: {})
        self.clock = clock
        self.on_change = on_change        # fn() after a commit / queue / undo
        self._lock = threading.RLock()
        self._windows = []                # [[start, end|None]] logged_in spans, epoch s
        self._queue = []                  # [(key, shot)]
        self._busy = threading.Lock()     # one OCR at a time
        self._ok_at = None                # plan 073: last good read / last failure
        self._err = None                  # (message, at)
        self._stop = threading.Event()
        self._thread = None

    # -- settings ----------------------------------------------------------------

    def _cfg(self):
        try:
            s = self.settings() or {}
        except Exception:  # noqa: BLE001 - unreadable config = the defaults
            s = {}
        enabled = s.get("ocr.auto", True)
        mn = s.get("ocr.auto_commit_min", AUTO_COMMIT_MIN)
        cap = s.get("ocr.daily_cap", DAILY_CAP)
        return (enabled is not False,
                mn if _ok_conf(mn) and not isinstance(mn, bool) else AUTO_COMMIT_MIN,
                cap if _ok_int(cap, 0, 10 ** 6) else DAILY_CAP)

    # -- trigger -----------------------------------------------------------------

    def on_game(self, prev, new, at):
        """Plan 008 change hook (GameWatch.listeners): logged_in windows."""
        with self._lock:
            if new == LOGGED_IN:
                if not self._windows or self._windows[-1][1] is not None:
                    self._windows.append([at, None])
            elif self._windows and self._windows[-1][1] is None:
                self._windows[-1][1] = at
            del self._windows[:-MAX_WINDOWS]

    def eligible(self, ts):
        """A shot at `ts` falls in a logged_in window or AFTER_LOGOUT_S after it."""
        with self._lock:
            return any(start <= ts and (end is None or ts <= end + AFTER_LOGOUT_S)
                       for start, end in self._windows)

    @staticmethod
    def _key(shot):
        return f"{shot.get('name')}|{shot.get('size')}|{shot.get('mtime')}"

    def _day(self):
        return time.strftime("%Y-%m-%d", time.localtime(self.clock()))

    def _auto(self):
        doc = self.store.get("ocr_auto")
        day = self._day()
        seen = [k for k in doc.get("seen", []) if isinstance(k, str)] \
            if isinstance(doc.get("seen"), list) else []
        commits = [c for c in doc.get("commits", []) if isinstance(c, dict)] \
            if isinstance(doc.get("commits"), list) else []
        count = doc.get("count") if doc.get("day") == day and _ok_int(doc.get("count"), 0, 10 ** 9) \
            else 0
        nxt = doc.get("next") if _ok_int(doc.get("next"), 1, 10 ** 9) else 1
        return {"day": day, "count": count, "seen": seen, "commits": commits, "next": nxt}

    def _save_auto(self, d):
        d["seen"] = d["seen"][-MAX_SEEN:]
        d["commits"] = d["commits"][-MAX_COMMITS:]
        self.store.put("ocr_auto", d)

    def scan(self):
        """Enqueue every new listed shot taken while logged in; mark the rest
        seen. Returns the number enqueued. Safe to call any time (idempotent)."""
        enabled, _, cap = self._cfg()
        if not enabled:
            return 0
        shots = self.game.view().get("screenshots") or []
        added = 0
        with self._lock:
            d = self._auto()
            seen = set(d["seen"]) | {k for k, _ in self._queue}
            changed = False
            for shot in sorted(shots, key=lambda s: str(s.get("mtime"))):
                key = self._key(shot)
                if key in seen:
                    continue
                if not _ok_int(shot.get("size"), 1, 10 ** 12):
                    continue  # QA 009: still being written; listed again when done
                ts = _ts(shot.get("mtime"))
                seen.add(key)
                if ts is None or not self.eligible(ts):
                    d["seen"].append(key)  # listed, never read
                    changed = True
                    continue
                if d["count"] + len(self._queue) >= cap:
                    d["seen"].append(key)  # over today's cap: the Read button remains
                    changed = True
                    continue
                self._queue.append((key, dict(shot)))
                added += 1
            if changed:
                self._save_auto(d)
        return added

    def drain(self):
        """OCR every queued shot, one at a time. Returns the number read."""
        n = 0
        while True:
            with self._lock:
                if not self._queue:
                    return n
                key, shot = self._queue.pop(0)
            with self._busy:
                self._process(key, shot)
            n += 1

    def _process(self, key, shot):
        enabled, mn, _ = self._cfg()
        if self._growing(shot):
            return  # QA 009: not counted, not seen; the final size is a new key
        with self._lock:
            d = self._auto()
            if key in d["seen"]:
                return
            d["seen"].append(key)
            d["count"] += 1
            self._save_auto(d)
        if not enabled:
            return
        try:
            doc = self.reader.doc(shot["name"])
        except (ocr.OcrError, ValueError, OSError) as e:
            with self._lock:
                self._err = (str(e)[:200], self.clock())
            return  # an unreadable shot is skipped; Read re-runs it on demand
        with self._lock:
            self._ok_at = self.clock()
        fields = []
        s = silver_field(doc, last=self._last_silver())
        if s is not None:
            fields.append(s)
        fields += buff_fields(doc)
        size = self._size(shot["name"])
        fields += self._progress_fields(shot["name"], doc, size)
        fields += ocrinfer.planner_fields(doc, size=size, regions=self.regions)
        if self.zones is not None:
            fields += zoneinfo.parse(doc, self.zone_titles)
        shot_at = _ts(shot.get("mtime")) or self.clock()
        if self.currency is not None:
            fields += ocrinfer.currency_field(doc, self.currency.rules, shot_at)
        touched = self._loot_read(shot["name"], doc, shot_at, mn)
        for f in fields:
            if f["kind"] == "buff" and f["value"] - math.floor(
                    max(0.0, self.clock() - shot_at) / 60) < 1:
                continue  # ran out since the shot: nothing left to arm or review
            hold, before = None, None
            if f["kind"] == "level":
                samples = self.leveling.samples()
                hold = ocrinfer.check_level(samples, f["value"]["level"], f["value"]["pct"],
                                            shot_at)
                if hold is not None:
                    f = dict(f, why=f"{f['why']}; {hold}")  # S7: never auto-committed
                else:
                    before = (ocrinfer.prev_sample(samples, shot_at), self.leveling.rate())
            agree = None
            if f["kind"] == "buff" and f["conf"] >= mn and _is_vp(f["name"]):
                hold = self._vp_hold(f["name"], f["value"], shot_at)
                if hold is not None:
                    f = dict(f, why=f"{f['why']}; {hold}")
            if f["kind"] == "fame" and f["conf"] >= mn:
                hold, agree = self._fame_hold(shot["name"], f["value"], shot_at)
                if hold is not None:
                    f = dict(f, why=f"{f['why']}; {hold}")
            if f["kind"] == CURRENCY_KIND:
                try:
                    act, why = self.currency.ocr_check(f["name"], f["value"], shot_at)
                except ValueError:
                    continue  # the event is no longer tracked: nothing to set
                if act == "skip":
                    continue  # an older shot than the stored read: nothing to change
                if act == "hold":
                    hold = why
                    f = dict(f, why=f"{f['why']}; {why}")
            if hold is None and f["conf"] >= mn:
                try:
                    uid = self._commit(shot["name"], f["kind"], f["name"], f["value"], shot_at)
                    if agree is not None:
                        self._drop_review(agree)
                    touched = True
                    if f["kind"] == zoneinfo.KIND:
                        self._log_applied(f["kind"], f["value"], f["conf"], shot["name"], uid)
                    if before is not None:
                        self._suggest_book(shot["name"], f["value"], shot_at, *before,
                                           level_conf=f["conf"])
                    continue
                except ValueError as e:
                    f = dict(f, why=f"{f['why']}; {e}")
            self._enqueue_review(shot["name"], f, shot_at)
            touched = True
        touched = self._boss_read(shot["name"], doc, shot_at) or touched
        if touched:
            self._changed()

    def _growing(self, shot):
        """The file on disk no longer has the listed size (BDO still writing it)."""
        d = getattr(self.game, "shot_dir", None)
        if d is None:
            return False
        try:
            return (d / shot["name"]).stat().st_size != shot.get("size")
        except OSError:
            return False  # gone / unreadable: the reader reports it as before

    def _size(self, name):
        if getattr(self.game, "shot_dir", None) is None:
            return None
        return ocrinfer.image_size(self.game.shot_dir / name)

    def _progress_fields(self, name, doc, size=None):
        """Plan 066 fields for the services this worker was given."""
        if self.leveling is None and self.progress is None:
            return []
        out = []
        # Plan 088: a zone panel's "Lv. 58 <zone>" + a monster % below it is no
        # character level; level / XP % are not read from such a shot.
        if self.leveling is not None and not (self.zones is not None
                                              and zoneinfo.is_zone_info(doc, self.zone_titles)):
            lv = ocrinfer.level_field(doc, size=size, regions=self.regions)
            if lv is not None:
                out.append(lv)
        if self.progress is not None:
            out += ocrinfer.gear_fields(doc, size=size, regions=self.regions)
        return out

    def _suggest_book(self, file, value, shot_at, prev, rate, level_conf=1.0):
        """A book use for an XP jump: applied at AUTO_APPLY_MIN or over (plan
        111, logged with an Undo), else queued for review."""
        books = getattr(self.leveling, "books", None)
        if books is None:
            return
        recent = books.recent(value["level"], shot_at - ocrinfer.BOOK_RECENT_S)
        sug = ocrinfer.book_suggestion(prev, value["level"], value["pct"], shot_at, rate, recent,
                                       level_conf)
        if sug is None:
            return
        if sug["conf"] >= AUTO_APPLY_MIN:
            try:
                uid = self._commit(file, sug["kind"], sug["name"], sug["value"], shot_at)
                self._log_applied(sug["kind"], sug["value"], sug["conf"], file, uid)
                return
            except ValueError as e:
                sug = dict(sug, why=f"{sug['why']}; {e}")
        self._enqueue_review(file, sug, shot_at)

    def _boss_read(self, file, doc, shot_at):
        """Plan 111: a shot within BOSS_WINDOW_MIN of a spawn whose text names
        that boss ticks its loot (by: auto) when name match x window proximity
        reaches AUTO_APPLY_MIN; a weaker or time-only match stays the plan 068
        suggestion. Only logged-in shots get here. True on a tick."""
        if self.bosses is None:
            return False
        ticked = False
        for day, boss, spawn in autotick.boss_spawns(shot_at, self.bosses.table):
            prox = 1.0 if shot_at >= spawn else BOSS_PROX_EARLY
            conf = round(boss_name_conf(doc, boss) * prox, 3)
            if conf < AUTO_APPLY_MIN:
                continue
            try:
                if not self.bosses.auto_tick(day, boss):
                    continue  # ticked already, unticked by the operator, or Garmoth cap
            except ValueError:
                continue  # an old shot outside the tick window
            self._log_applied("boss", {"day": day, "boss": boss}, conf, file, f"{day}|{boss}")
            ticked = True
        return ticked

    def _changed(self):
        if self.on_change is not None:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001 - a notifier never breaks the worker
                pass

    # -- commits -----------------------------------------------------------------

    def _last_silver(self):
        samples = self.store.get("silver").get("samples")
        for s in reversed(samples if isinstance(samples, list) else []):
            if isinstance(s, dict) and _ok_int(s.get("value"), 0, MAX_SILVER):
                return s["value"]
        return None

    def _reads(self):
        """Store domain `ocr_reads` {kind: [{id, at, value, source}]}, cleaned."""
        doc = self.store.get("ocr_reads")
        out = {}
        for kind in PLANNER_KINDS:
            rows = doc.get(kind) if isinstance(doc.get(kind), list) else []
            keep = []
            for r in rows:
                if not (isinstance(r, dict) and _ts(r.get("at")) is not None):
                    continue
                try:
                    _check_value(kind, r.get("value"))
                except ValueError:
                    continue
                keep.append(r)
            out[kind] = keep
        return out

    def latest(self, kind):
        """Plan 081: {value, at, source} of the newest committed `kind` read (by
        shot time; silver from the plan 063 samples), or None."""
        if kind == "silver":
            samples = self.store.get("silver").get("samples")
            rows = [s for s in samples if isinstance(s, dict)
                    and _ok_int(s.get("value"), 0, MAX_SILVER)
                    and _ts(s.get("at")) is not None] if isinstance(samples, list) else []
        elif kind in PLANNER_KINDS:
            with self._lock:
                rows = self._reads()[kind]
        else:
            raise ValueError(f"unknown read kind: {kind}")
        if not rows:
            return None
        r = max(enumerate(rows), key=lambda p: (_ts(p[1]["at"]), p[0]))[1]
        return {"value": r["value"], "at": r["at"],
                "source": r["source"] if isinstance(r.get("source"), str) else "ocr"}

    # -- plan 108: the persisted family fame read ------------------------------------

    def fame_read(self):
        """{value, at, source: "ocr", file} of the newest committed fame read:
        store domain `fame` (kept across commit-list rotation and restarts),
        or a newer `ocr_reads` row (a store written before plan 108); or None."""
        doc = self.store.get("fame")
        best = None
        try:
            if _ts(doc.get("at")) is not None:
                best = {"value": _check_value("fame", doc.get("value")), "at": doc["at"],
                        "source": "ocr", "file": _str(doc.get("file"), 255) or None}
        except ValueError:
            best = None
        r = self.latest("fame")
        if r is not None and (best is None or _ts(r["at"]) > _ts(best["at"])):
            src = r["source"]
            best = {"value": r["value"], "at": r["at"], "source": "ocr",
                    "file": (src[4:] or None) if src.startswith("ocr:") else None}
        return best

    def _fame_put(self, uid, value, at, file):
        self.store.put("fame", {"id": uid, "value": value, "at": _iso(at), "source": "ocr",
                                "file": _str(file, 255)})

    def _fame_hold(self, file, value, shot_at):
        """Slice 4: (why held | None, id of an agreeing review item | None). Fame
        only rises: a read below the newest one (from a later shot) is held
        until a second screenshot reads the same value."""
        cur = self.fame_read()
        if cur is None or value >= cur["value"] or shot_at < _ts(cur["at"]):
            return None, None
        with self._lock:
            items = self._review()["items"]
        for i in items:
            if i.get("kind") == "fame" and i.get("value") == value and i.get("file") != file:
                return None, i.get("id")
        return (f"fame went down from {cur['value']} %; held until a second screenshot "
                "agrees"), None

    # -- plan 109: Value Pack renewal guard -------------------------------------------

    def _vp_hold(self, name, minutes, shot_at):
        """Why a Value Pack read is held, or None. A read ending later than the
        armed timer is a renewal and commits; one ending earlier (beyond the
        tooltip's hour granularity) is queued - a misread must not cut VP short."""
        cur = self._buff_state(name)
        ends = _ts(cur["ends"]) if cur else None
        if ends is None or ends <= self.clock():
            return None
        if shot_at + minutes * 60 < ends - VP_EARLY_SLACK_S:
            return ("Value Pack ends earlier than the armed timer; held until the operator "
                    "accepts it")
        return None

    def _drop_review(self, rid):
        with self._lock:
            r = self._review()
            r["items"] = [i for i in r["items"] if i.get("id") != rid]
            self.store.put("ocr_review", r)

    # -- plan 081: loot counts of the running grind session ------------------------

    def _target(self):
        if self.loot_target is None:
            return None
        try:
            t = self.loot_target()
        except Exception:  # noqa: BLE001 - no grind session read = no loot prefill
            return None
        if not (isinstance(t, dict) and isinstance(t.get("spot"), str)
                and _ts(t.get("started")) is not None and isinstance(t.get("names"), list)
                and (t.get("end") is None or _ts(t.get("end")) is not None)):
            return None
        return t

    def _catalog(self):
        if self.catalog is None:
            return None
        try:
            c = self.catalog()
        except Exception:  # noqa: BLE001 - no index read = table names only
            return None
        return c if isinstance(c, dict) else None

    def _loot_read(self, file, doc, shot_at, mn):
        """Loot counts read from a shot taken during the running grind session
        (plan 113: or the just-closed auto one, up to AFTER_LOGOUT_S past its end)
        land in store domain `ocr_loot` {spot, started, items: {name: {count,
        conf, low, at, file, id, source}}}; a newer read of one item replaces the
        older one (the loot window shows running totals). Plan 113: rows under
        the gate go to review (kind `loot`) instead. True when something changed."""
        t = self._target()
        if t is None or shot_at < _ts(t["started"]):
            return False
        if t.get("end") is not None and shot_at > _ts(t["end"]) + AFTER_LOGOUT_S:
            return False
        cat = self._catalog()
        if not t["names"] and not cat:
            return False
        rows = [r for r in ocr.extract_loot(doc.get("lines") or [], t["names"], cat)["rows"]
                if _ok_int(r.get("count"), 1, MAX_LOOT_COUNT)]
        keep = []
        for r in rows:
            conf = r.get("confidence") if _ok_conf(r.get("confidence")) else 0
            if conf >= mn:
                keep.append(r)
                continue
            value = {"name": r["name"], "count": r["count"], "id": r.get("id"),
                     "source": r.get("source", "table"), "spot": t["spot"],
                     "started": t["started"]}
            self._enqueue_review(file, {"kind": "loot", "name": r["name"], "value": value,
                                        "conf": conf, "why": "loot name read below the gate"},
                                 shot_at)
        if keep:
            self._loot_put(t["spot"], t["started"], keep, shot_at, file)
        return bool(rows)

    def _loot_put(self, spot, started, rows, shot_at, file):
        """Write `rows` [{name, count, confidence, id?, source?}] read at
        `shot_at` into `ocr_loot` for that session. Returns {name: previous item
        or None} for the rows written (an older read never replaces a newer one)."""
        prev = {}
        with self._lock:
            cur = self.store.get("ocr_loot")
            same = cur.get("spot") == spot and cur.get("started") == started
            items = dict(cur.get("items")) if same and isinstance(cur.get("items"), dict) else {}
            for r in rows:
                old = items.get(r["name"])
                if isinstance(old, dict) and (_ts(old.get("at")) or 0) > shot_at:
                    continue
                conf = r.get("confidence") if _ok_conf(r.get("confidence")) else 0
                prev[r["name"]] = old if isinstance(old, dict) else None
                items[r["name"]] = {"count": r["count"], "conf": conf, "low": False,
                                    "at": _iso(shot_at), "file": _str(file, 255),
                                    "id": r.get("id") if _ok_int(r.get("id"), 1, 2 ** 31 - 1)
                                    else None,
                                    "source": r.get("source") if r.get("source") in LOOT_SOURCES
                                    else "table"}
            if len(items) > MAX_LOOT_ROWS:
                items = dict(sorted(items.items(), key=lambda kv: kv[1]["at"])[-MAX_LOOT_ROWS:])
            self.store.put("ocr_loot", {"spot": spot, "started": started, "items": items})
        return prev

    def _loot_restore(self, spot, started, name, written, prev):
        """Undo one loot commit while the item is still the one it wrote."""
        with self._lock:
            cur = self.store.get("ocr_loot")
            items = cur.get("items") if isinstance(cur.get("items"), dict) else {}
            if cur.get("spot") != spot or cur.get("started") != started \
                    or items.get(name) != written:
                raise ValueError(f"{name} was read again since this commit")
            items = dict(items)
            if isinstance(prev, dict):
                items[name] = prev
            else:
                items.pop(name, None)
            self.store.put("ocr_loot", {"spot": spot, "started": started, "items": items})

    def loot_prefill(self, spot, started):
        """{source: "ocr", spot, started, at, items: [{name, count, conf, low,
        at, file, id, source}]} read during the grind session that started at
        `started` on `spot`, or None."""
        cur = self.store.get("ocr_loot")
        if cur.get("spot") != spot or cur.get("started") != started \
                or not isinstance(cur.get("items"), dict):
            return None
        items = [dict(v, name=k) for k, v in sorted(cur["items"].items())
                 if isinstance(v, dict) and _ok_int(v.get("count"), 1, 10 ** 9)
                 and _ts(v.get("at")) is not None]
        if not items:
            return None
        return {"source": "ocr", "spot": spot, "started": started,
                "at": max(i["at"] for i in items), "items": items}

    def _buff_state(self, name):
        """Stored {ends, armed} of a grind buff (by name), or None."""
        doc = self.store.get("grind")
        for b in doc.get("buffs", []) if isinstance(doc.get("buffs"), list) else []:
            if isinstance(b, dict) and isinstance(b.get("name"), str) \
                    and isinstance(name, str) and b["name"].lower() == name.lower():
                return {"ends": b.get("ends"), "armed": b.get("armed")}
        return None

    def _commit(self, file, kind, name, value, shot_at, via="auto", at_shot=True):
        """Commit one field to its domain; returns the undo id."""
        value = _check_value(kind, value)
        now = self.clock()
        with self._lock:
            d = self._auto()
            uid = f"u{d['next']}"
            entry = {"id": uid, "file": _str(file, 255), "kind": kind, "name": name,
                     "value": value, "at": _iso(now), "shot_at": _iso(shot_at),
                     "via": via, "undone": False}
            if kind == "silver":
                doc = self.store.get("silver")
                samples = doc.get("samples") if isinstance(doc.get("samples"), list) else []
                samples.append({"id": uid, "at": _iso(shot_at), "value": value,
                                "source": f"ocr:{_str(file, 255)}"})
                self.store.put("silver", {"samples": samples[-MAX_SAMPLES:]})
            elif kind in ("level", "book_use"):
                if self.leveling is None:
                    raise ValueError("leveling is not available")
                if kind == "level":
                    entry["ts"] = self.leveling.ocr_sample(value["level"], value["pct"], shot_at)
                else:
                    used = self.leveling.book_use(value)["books"]["used"][0]
                    entry["row"] = {k: used[k] for k in ("at", "size", "level", "pct_before",
                                                         "pct_after")}
            elif kind == "gear":
                if self.progress is None or name not in GS_KEYS:
                    raise ValueError("gear score is not available")
                entry["prev"] = self.progress.gs_ocr(name, value, _iso(shot_at),
                                                     force=via != "auto")
            elif kind == zoneinfo.KIND:
                if self.zones is None:
                    raise ValueError("zone info is not available")
                level = self.leveling.level_at(shot_at) if self.leveling is not None else None
                key, prev = self.zones.commit(value, _str(file, 255), shot_at, level)
                entry.update(key=key, prev=prev, read_at=_iso(shot_at))
            elif kind == "loot":
                cur = self.store.get("ocr_loot")
                if (_ts(cur.get("started")) or 0) > _ts(value["started"]):
                    raise ValueError("that grind session's loot was replaced by a newer one")
                row = {"name": value["name"], "count": value["count"], "confidence": 1.0,
                       "id": value["id"], "source": value["source"]}
                prev = self._loot_put(value["spot"], value["started"], [row], shot_at, file)
                if value["name"] not in prev:
                    raise ValueError(f"{value['name']} has a newer read")
                items = self.store.get("ocr_loot").get("items") or {}
                entry.update(prev=prev[value["name"]], written=items.get(value["name"]))
            elif kind == CURRENCY_KIND:
                # Plan 115: the balance as read at the shot (a fix too: it corrects the read).
                entry["prev"] = self._need(self.currency).set_balance(
                    name, value, source=f"ocr:{_str(file, 255)}", at=shot_at, uid=uid)
            elif kind in PLANNER_KINDS:
                reads = self._reads()
                reads[kind] = (reads.get(kind, []) + [{
                    "id": uid, "at": _iso(shot_at), "value": value,
                    "source": f"ocr:{_str(file, 255)}"}])[-MAX_READS:]
                self.store.put("ocr_reads", reads)
                cur = _ts(self.store.get("fame").get("at")) if kind == "fame" else None
                if kind == "fame" and (cur is None or shot_at >= cur):
                    self._fame_put(uid, value, shot_at, file)  # plan 108: the newest read
            else:
                # `value` is minutes left at the shot; a fix is typed as minutes left now.
                left = value - math.floor(max(0.0, now - shot_at) / 60) if at_shot else value
                if left < 1:
                    raise ValueError(f"{name} ran out since the screenshot; "
                                     "fix with the minutes left now, or discard")
                prev = self._buff_state(name)
                entry["prev"] = {"ends": prev["ends"] if prev else None,
                                 "armed": prev.get("armed") if prev else None}
                self.grind.buff({"name": name, "minutes": left})
                now_state = self._buff_state(name)
                entry["ends"] = now_state["ends"] if now_state else None
                entry["minutes_left"] = left
            d["next"] += 1
            d["commits"].append(entry)
            self._save_auto(d)
        return uid

    @staticmethod
    def _need(service):
        if service is None:
            raise ValueError("that service is not available")
        return service

    def undo(self, uid):
        """Reverse one commit: the silver sample is removed, a buff timer goes
        back to what it was before the commit; plan 066: the OCR level sample /
        book use is removed, a gs stat goes back (each only while unchanged)."""
        if not isinstance(uid, str) or not re.fullmatch(r"u[0-9]{1,9}", uid):
            raise ValueError("undo must be an id like u3")
        with self._lock:
            d = self._auto()
            c = next((c for c in d["commits"] if c.get("id") == uid), None)
            if c is None:
                raise ValueError(f"unknown commit: {uid}")
            if c.get("undone"):
                raise ValueError(f"already undone: {uid}")
            if c.get("kind") == "silver":
                doc = self.store.get("silver")
                samples = doc.get("samples") if isinstance(doc.get("samples"), list) else []
                self.store.put("silver", {"samples": [s for s in samples
                                                      if not (isinstance(s, dict)
                                                              and s.get("id") == uid)]})
            elif c.get("kind") == "level":
                self._need(self.leveling).ocr_sample_del(c.get("ts"))
            elif c.get("kind") == "book_use":
                lev = self._need(self.leveling)
                idx = lev.books.used_index(c.get("row") or {}) if lev.books else None
                if idx is None:
                    raise ValueError("that book use was deleted; edit it in Leveling")
                lev.book_del(idx)
            elif c.get("kind") == "gear":
                self._need(self.progress).gs_restore(c.get("name"), c.get("value"),
                                                     c.get("prev"))
            elif c.get("kind") == zoneinfo.KIND:
                self._need(self.zones).restore(c.get("key"), c.get("prev"), c.get("read_at"),
                                               c.get("file"))
            elif c.get("kind") == "loot":
                v = c.get("value") if isinstance(c.get("value"), dict) else {}
                self._loot_restore(v.get("spot"), v.get("started"), v.get("name"),
                                   c.get("written"), c.get("prev"))
            elif c.get("kind") == CURRENCY_KIND:
                self._need(self.currency).restore_read(c.get("name"), uid, c.get("prev"))
            elif c.get("kind") in PLANNER_KINDS:
                reads = self._reads()
                reads[c["kind"]] = [r for r in reads.get(c["kind"], []) if r.get("id") != uid]
                self.store.put("ocr_reads", reads)
                if c["kind"] == "fame" and self.store.get("fame").get("id") == uid:
                    # Plan 108: back to the newest read left, or no read at all.
                    rest = sorted(reads["fame"], key=lambda r: _ts(r["at"]))
                    if rest:
                        src = rest[-1].get("source")
                        self._fame_put(rest[-1].get("id"), rest[-1]["value"],
                                       _ts(rest[-1]["at"]),
                                       src[4:] if isinstance(src, str)
                                       and src.startswith("ocr:") else "")
                    else:
                        self.store.put("fame", {})
            else:
                # Only while the timer is still the one this commit wrote: a later
                # commit or a manual re-arm / clear is never overwritten.
                cur = self._buff_state(c.get("name"))
                if cur is None or cur["ends"] != c.get("ends"):
                    raise ValueError(f"{c.get('name')} changed since this commit; "
                                     "set it in the Grind tab")
                prev = c.get("prev") if isinstance(c.get("prev"), dict) else {}
                self.grind.restore_buff(c.get("name"), prev.get("ends"), prev.get("armed"))
            c["undone"] = True
            self._save_auto(d)
            self._mark_undone(uid)
        self._changed()
        return self.view()

    # -- plan 111: auto-applied log ------------------------------------------------

    def _applied(self):
        doc = self.store.get("auto_applied")
        items = [i for i in doc.get("items", []) if isinstance(i, dict)] \
            if isinstance(doc.get("items"), list) else []
        nxt = doc.get("next") if _ok_int(doc.get("next"), 1, 10 ** 9) else 1
        return {"items": items, "next": nxt}

    def _log_applied(self, kind, value, conf, file, undo_id):
        with self._lock:
            a = self._applied()
            row = {"id": f"a{a['next']}", "at": _iso(self.clock()), "kind": kind,
                   "value": value, "conf": conf, "file": _str(file, 255),
                   "undo_id": undo_id, "undone": False}
            a["items"] = ([row] + a["items"])[:MAX_APPLIED]
            a["next"] += 1
            self.store.put("auto_applied", a)

    def _mark_undone(self, undo_id):
        with self._lock:
            a = self._applied()
            hit = False
            for row in a["items"]:
                if row.get("undo_id") == undo_id and not row.get("undone"):
                    row["undone"] = hit = True
            if hit:
                self.store.put("auto_applied", a)

    def undo_applied(self, aid):
        """Undo one auto-applied row: a book use / zone read through `undo`, a
        boss loot tick through BossService.untick (which also blocks a later
        auto tick of that boss on that day)."""
        if not isinstance(aid, str) or not re.fullmatch(r"a[0-9]{1,9}", aid):
            raise ValueError("undo must be an id like a3")
        with self._lock:
            row = next((r for r in self._applied()["items"] if r.get("id") == aid), None)
            if row is None:
                raise ValueError(f"unknown auto-applied row: {aid}")
            if row.get("undone"):
                raise ValueError(f"already undone: {aid}")
            if row.get("kind") != "boss":
                return self.undo(row.get("undo_id"))
            v = row.get("value") if isinstance(row.get("value"), dict) else {}
            self._need(self.bosses).untick({"boss": v.get("boss"), "day": v.get("day")})
            self._mark_undone(row.get("undo_id"))
        self._changed()
        return self.view()

    # -- review queue ------------------------------------------------------------

    def _review(self):
        doc = self.store.get("ocr_review")
        items = [i for i in doc.get("items", []) if isinstance(i, dict)] \
            if isinstance(doc.get("items"), list) else []
        nxt = doc.get("next") if _ok_int(doc.get("next"), 1, 10 ** 9) else 1
        return {"items": items, "next": nxt}

    def _enqueue_review(self, file, f, shot_at):
        with self._lock:
            r = self._review()
            r["items"].append({"id": f"r{r['next']}", "file": _str(file, 255),
                               "kind": f["kind"], "name": f["name"], "value": f["value"],
                               "conf": f["conf"], "why": _str(f["why"]),
                               "at": _iso(self.clock()), "shot_at": _iso(shot_at)})
            r["next"] += 1
            r["items"] = r["items"][-MAX_REVIEW:]
            self.store.put("ocr_review", r)

    def review(self, arg):
        """`{id, action: accept|discard}` or `{id, action: fix, value}`."""
        if not isinstance(arg, dict) or not isinstance(arg.get("id"), str):
            raise ValueError("review must be {id, action, value?}")
        action = arg.get("action")
        keys = {"id", "action", "value"} if action == "fix" else {"id", "action"}
        if action not in ("accept", "fix", "discard") or set(arg) != keys:
            raise ValueError("review must be {id, action: accept|discard} or {id, action: fix, value}")
        with self._lock:
            r = self._review()
            item = next((i for i in r["items"] if i.get("id") == arg["id"]), None)
            if item is None or item.get("kind") not in KINDS:
                raise ValueError(f"unknown review item: {arg['id']}")
            if action == "fix" and item["kind"] not in FIX_KINDS:
                raise ValueError(f"a {item['kind']} suggestion is accepted or discarded")
            if action != "discard":
                value = arg["value"] if action == "fix" else item.get("value")
                if action == "fix" and item["kind"] == "loot":
                    # Plan 113: a loot fix is the corrected count.
                    if not _ok_int(value, 1, MAX_LOOT_COUNT):
                        raise ValueError(f"a loot fix is a count 1..{MAX_LOOT_COUNT}")
                    value = dict(item.get("value") or {}, count=value)
                self._commit(item.get("file"), item["kind"], item.get("name"), value,
                             _ts(item.get("shot_at")) or self.clock(), via=action,
                             at_shot=action == "accept")
            r["items"] = [i for i in r["items"] if i is not item]
            self.store.put("ocr_review", r)
        self._changed()
        return self.view()

    # -- reads -------------------------------------------------------------------

    def view(self):
        """GET /api/ocr/auto body."""
        enabled, mn, cap = self._cfg()
        with self._lock:
            d = self._auto()
            items = self._review()["items"]
            applied = self._applied()["items"][:VIEW_APPLIED]
            pending = len(self._queue)
        commits = [{k: c.get(k) for k in ("id", "file", "kind", "name", "value", "at", "via")}
                   for c in reversed(d["commits"]) if not c.get("undone")][:VIEW_COMMITS]
        review = [{k: i.get(k) for k in ("id", "file", "kind", "name", "value", "conf", "why",
                                         "shot_at")} for i in reversed(items)]
        return {"enabled": enabled, "commit_min": mn, "daily_cap": cap, "today": d["count"],
                "pending": pending, "review": review, "commits": commits,
                "applied": [{k: a.get(k) for k in ("id", "at", "kind", "value", "conf", "file",
                                                   "undone")} for a in applied],
                "silver": self._last_silver(), "silver_h": self._silver_h()}

    def health(self):
        """Plan 073 signal inputs: last good read, last failure, queue depth."""
        enabled = self._cfg()[0]
        with self._lock:
            err = self._err
            return {"enabled": enabled, "ok_at": self._ok_at, "pending": len(self._queue),
                    "error": err[0] if err else None, "error_at": err[1] if err else None}

    def _silver_h(self):
        """Plan 066: silver/h between OCR silver samples in one play session."""
        if self.play is None:
            return None
        try:
            window = ocrinfer.session_window(self.play())
        except Exception:  # noqa: BLE001 - a broken session feed never breaks the card
            return None
        samples = self.store.get("silver").get("samples")
        return ocrinfer.silver_rate(samples if isinstance(samples, list) else [], window)

    # -- thread ------------------------------------------------------------------

    def _run(self, interval):
        while not self._stop.is_set():
            try:
                self.scan()
                self.drain()
            except Exception:  # noqa: BLE001 - a bad tick never kills the worker
                pass
            self._stop.wait(interval)

    def start(self, interval=POLL_S):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(interval,),
                                        name="ew-ocr-auto", daemon=True)
        self._thread.start()

    def stop(self, timeout=2.0):
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout)
