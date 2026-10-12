"""Auto-tick inferable Today rows (plan 068).

Rules are data on the row (`today.parse_auto`): `login` ticks on the first
logged_in seen after the row's reset, `logged_minutes:N` once the plan 056 dice
clock counts N logged-in minutes since the reset, `ready_minutes:N` only marks
the row ready. Auto ticks carry `by: auto`; an operator untick blocks them until
the row's next reset (TodayService). A screenshot (plan 008 watcher) taken while
logged in within BOSS_WINDOW_MIN of a plan 031 spawn suggests that boss as
"probably done" - a suggestion only, never a loot tick (plan 111: the OCR
worker ticks it when the shot's text also names the boss, `ocrauto`).
Plan 114: `shot:<cue>` rows tick from the OCR worker's doc of a logged-in shot
(`on_doc`), `bosses:N` rows once the period's boss loot ticks reach N.
Plan 127: a Black Spirit's Scheduler shot ticks every listed done row
(`scheduler`, called by the OCR worker, which logs and queues the result).

Inputs are the session-log state, screenshot file times, the OCR text of shots
the operator saved, EW's own boss ticks and the clock: nothing is read from or
sent to the game.
"""

import datetime as _dt
import threading
import time

from . import bosses as _bosses
from . import ocrinfer
from . import today as _today

LOGGED_IN = "logged_in"
BOSS_WINDOW_MIN = 20
EVAL_S = 30          # a poll re-evaluates the rules at most this often
MAX_WINDOWS = 64     # logged_in spans kept in memory
MAX_SEEN = 500       # screenshot keys remembered (the watcher lists at most 50)
SCHED_DOMAIN = "autotick_sched"  # plan 127: {unknown: [slug], seeded: [row id]}
MAX_SCHED_UNKNOWN = 200
_UTC = _dt.timezone.utc
_DAY = _dt.timedelta(days=1)


def _parse(s):
    if not isinstance(s, str):
        return None
    try:
        when = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return when.timestamp() if when.tzinfo is not None else None


def _iso(ts):
    return _dt.datetime.fromtimestamp(ts, _UTC).replace(microsecond=0).isoformat()


def boss_spawns(at, table):
    """Epoch `at` -> [(PT day, boss, spawn epoch)] for every spawn within
    +- BOSS_WINDOW_MIN (edges inclusive)."""
    week = _bosses._by_weekday(table)
    day0 = _bosses.utc_to_pt(_dt.datetime.fromtimestamp(at, _UTC)).date()
    out = []
    for day in (day0 - _DAY, day0, day0 + _DAY):
        for slot in week[day.weekday()]:
            spawn, row = _bosses._spawn(table, slot, day)
            if abs(spawn.timestamp() - at) <= BOSS_WINDOW_MIN * 60:
                out.extend((row["day"], b, spawn.timestamp()) for b in row["bosses"])
    return out


def boss_suggestions(at, table):
    """Epoch `at` -> [(PT day, boss)] for every spawn within +- BOSS_WINDOW_MIN
    (edges inclusive)."""
    return [(day, boss) for day, boss, _ in boss_spawns(at, table)]


class AutoTick:
    """Store domain `autotick`: {"boss_suggest": {"<PT day>|<boss>": "<shot iso>"}}.
    A GameWatch listener (logged_in spans + login rule) and poller (minutes rules,
    session spanning a reset, new screenshots)."""

    def __init__(self, store, today, dice, game, table=None, settings=None,
                 clock=time.time, on_change=None, bosses=None, cues=None, sched=None):
        self.store = store
        self.today = today
        self.dice = dice
        self.game = game
        self.table = table or _bosses.load_table()
        # Plan 114: BossService for `bosses:N` (without one the rule never
        # ticks); the tracked shot cues (a malformed file = no shot cues).
        self.bosses = bosses
        if cues is None:
            try:
                cues = _today.load_cues()
            except ValueError:
                cues = {}
        self.cues = cues
        # Plan 127: the Scheduler window data (a malformed entry = no Scheduler reads).
        if sched is None:
            try:
                sched = _today.load_scheduler()
            except ValueError:
                sched = None
        self.sched = sched
        self.settings = settings or (lambda: {})
        self.clock = clock
        self.on_change = on_change
        self._lock = threading.Lock()
        self._windows = []   # [[start, end|None]] logged_in spans, epoch s
        self._seen = set()   # screenshot keys already scanned
        self._last_eval = None

    def _enabled(self):
        try:
            return (self.settings() or {}).get("checklist.auto", True) is not False
        except Exception:  # noqa: BLE001 - unreadable config = the default
            return True

    def _changed(self):
        if self.on_change is not None:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001 - a notifier never breaks a tick
                pass

    # -- GameWatch hooks -----------------------------------------------------------

    def on_game(self, prev, new, at):
        """Plan 008 change hook: logged_in spans; a login ticks `login` rows."""
        with self._lock:
            if new == LOGGED_IN:
                if not self._windows or self._windows[-1][1] is not None:
                    self._windows.append([at, None])
            elif self._windows and self._windows[-1][1] is None:
                self._windows[-1][1] = at
            del self._windows[:-MAX_WINDOWS]
        if new == LOGGED_IN and self._enabled():
            self._tick_rows(("login",), at)

    def on_poll(self, state, at):
        """Plan 062 poller hook: rules at most every EVAL_S, then new shots."""
        if self._last_eval is None or at - self._last_eval >= EVAL_S or at < self._last_eval:
            self._last_eval = at
            self.evaluate(at, state)
        self.scan_shots()

    # -- rules --------------------------------------------------------------------

    def _tick_rows(self, kinds, at):
        ticked = False
        for iid, rule, _ in self.today.auto_rows():
            if _today.parse_auto(rule)[0] in kinds:
                ticked = self.today.auto_tick(iid, at) or ticked
        if ticked:
            self._changed()
        return ticked

    def _played_min(self, now):
        """(logged-in minutes since the dice reset, that reset as epoch)."""
        st = self.dice.status(now)
        reset = _today.last_reset(self.dice.rule, _dt.datetime.fromtimestamp(now, _UTC))
        return st["played_min"], reset.timestamp()

    def _minutes_ok(self, n, row_rule, now, played):
        """N minutes reached and counted wholly inside the row's own period."""
        mins, dice_reset = played
        row_reset = _today.last_reset(row_rule, _dt.datetime.fromtimestamp(now, _UTC))
        return mins >= n and dice_reset >= row_reset.timestamp()

    def evaluate(self, now=None, state=None):
        """Apply the ticking rules at `now`: `login` while logged in now (a session
        that spans a reset), `logged_minutes:N` from the dice clock."""
        now = self.clock() if now is None else now
        if not self._enabled():
            return False
        if state is None:
            state = (self.game.view() or {}).get("state")
        ticked = False
        played = None
        for iid, rule, row_rule in self.today.auto_rows():
            kind, n = _today.parse_auto(rule)
            if kind == "login" and state == LOGGED_IN:
                ticked = self.today.auto_tick(iid, now) or ticked
            elif kind == "logged_minutes":
                played = played or self._played_min(now)
                if self._minutes_ok(n, row_rule, now, played):
                    ticked = self.today.auto_tick(iid, now) or ticked
            elif kind == "bosses" and self.bosses is not None:
                since = _today.last_reset(row_rule, _dt.datetime.fromtimestamp(now, _UTC))
                if self.bosses.looted_since(since) >= n:
                    ticked = self.today.auto_tick(iid, now) or ticked
        if ticked:
            self._changed()
        return ticked

    def on_doc(self, file, doc, shot_at):
        """Plan 114: the plan 063 worker's OCR doc of a shot taken at epoch
        `shot_at` (no second OCR). A shot inside a logged_in span whose text
        matches a row's `shot:<cue>` ticks that row (by: auto) in the period in
        force at the shot. True when a row ticked."""
        if not self._enabled() or not self._in_window(shot_at):
            return False
        text = doc.get("text") if isinstance(doc, dict) else None
        if not isinstance(text, str) or not text.strip():
            lines = doc.get("lines") if isinstance(doc, dict) else None
            text = "\n".join(ln.get("text") for ln in (lines if isinstance(lines, list) else [])
                             if isinstance(ln, dict) and isinstance(ln.get("text"), str))
        text = " ".join(text.split())
        if self.sched is not None and ocrinfer.is_scheduler(doc, self.sched):
            return False  # plan 127: a Scheduler shot is read per line (`scheduler`)
        ticked = False
        for iid, rule, _ in self.today.auto_rows():
            kind, cue = _today.parse_auto(rule)
            if kind == "shot" and cue in self.cues and _today.cue_matches(self.cues[cue], text):
                ticked = self.today.auto_tick(iid, shot_at) or ticked
        if ticked:
            self._changed()
        return ticked

    # -- plan 127: Black Spirit's Scheduler shot ------------------------------------

    def _sched_state(self):
        doc = self.store.get(SCHED_DOMAIN)
        return {k: [x for x in doc.get(k) if isinstance(x, str)]
                if isinstance(doc.get(k), list) else [] for k in ("unknown", "seeded")}

    def scheduler(self, doc, shot_at, min_conf=0.0):
        """Plan 127: the OCR doc of a Scheduler window shot taken at epoch
        `shot_at` inside a logged_in span -> {ticked: [{row, title, conf}],
        unknown: [{name, cadence, state, remaining_s}]}, or None (auto off, not
        logged in, not a Scheduler shot). Each done line of a Today row with a
        ticking rule ticks it (by: auto, the period in force at the shot, an
        operator untick blocks); open lines never untick; a plan 127 seed row is
        added the first time it is listed; an unmatched line is returned once
        ever (store domain `autotick_sched`)."""
        if (self.sched is None or not self._enabled() or not self._in_window(shot_at)
                or not ocrinfer.is_scheduler(doc, self.sched)):
            return None
        with self._lock:
            st = self._sched_state()
            listed = {r["row"] for r in ocrinfer.scheduler_rows(doc, self.sched)}
            changed = False
            for iid, (title, kind) in _today.SCHED_SEED.items():
                if iid in listed and iid not in st["seeded"]:
                    try:
                        self.today.ensure_row(iid, title, kind, _today.SCHED_RULE)
                    except ValueError:
                        continue  # a full list: tried again on the next shot
                    st["seeded"].append(iid)
                    changed = True
            titles = self.today.titles()
            rows = ocrinfer.scheduler_rows(doc, self.sched, titles)
            unknown = []
            for r in rows:
                key = _today.slug(r["name"])
                if r["row"] is None and key not in st["unknown"]:
                    st["unknown"] = (st["unknown"] + [key])[-MAX_SCHED_UNKNOWN:]
                    changed = True
                    unknown.append({"name": r["name"], "cadence": r["cadence"],
                                    "state": r["state"], "remaining_s": r.get("remaining_s")})
            if changed:
                self.store.put(SCHED_DOMAIN, st)
        ticked = [{"row": r["row"], "title": titles.get(r["row"], r["row"]), "conf": r["conf"]}
                  for r in rows if r["row"] is not None and r["state"] == "done"
                  and r["conf"] >= min_conf and self.today.auto_tick(r["row"], shot_at)]
        if ticked:
            self._changed()
        return {"ticked": ticked, "unknown": unknown}

    def map_unknown(self, name, value, shot_at):
        """Plan 127 review accept: an unknown Scheduler line becomes a Today row
        of its cadence (plan 021 kind default reset) bound to `shot:scheduler`;
        a line read as done ticks it at the shot. Returns the new row id."""
        cadence = value.get("cadence") if isinstance(value, dict) else None
        if cadence not in ("daily", "weekly"):
            raise ValueError("a scheduler row is daily or weekly")
        before = set(self.today.titles())
        self.today.add({"title": name, "kind": cadence, "auto": _today.SCHED_RULE})
        iid = next(iter(set(self.today.titles()) - before))
        if value.get("state") == "done" and self.today.auto_tick(iid, shot_at):
            self._changed()
        return iid

    def undo_row(self, iid):
        """Plan 127 Undo of a Scheduler tick: the operator untick (blocks auto
        ticks of the row until its next reset)."""
        self.today.untick(iid)
        self._changed()

    def decorate(self, view, now=None):
        """GET /api/today: `ready` on every `ready_minutes:N` row."""
        now = self.clock() if now is None else now
        played = None
        rules = {iid: row_rule for iid, _, row_rule in self.today.auto_rows()}
        for row in view.get("items", []):
            kind = n = None
            if "auto" in row:
                kind, n = _today.parse_auto(row["auto"])
            if kind != "ready_minutes" or row["id"] not in rules:
                continue
            played = played or self._played_min(now)
            row["ready"] = self._minutes_ok(n, rules[row["id"]], now, played)
        return view

    # -- boss suggestion ----------------------------------------------------------

    def _in_window(self, ts):
        with self._lock:
            return any(start <= ts and (end is None or ts <= end)
                       for start, end in self._windows)

    def _load(self):
        raw = self.store.get("autotick").get("boss_suggest")
        out = {}
        for k, v in (raw.items() if isinstance(raw, dict) else ()):
            day, _, boss = k.partition("|") if isinstance(k, str) else ("", "", "")
            if _today.DATE_RE.match(day) and boss and _parse(v) is not None:
                out[k] = v
        return out

    def scan_shots(self):
        """New screenshots taken while logged in near a spawn -> suggestions."""
        shots = (self.game.view() or {}).get("screenshots") or []
        fresh = [s for s in shots
                 if f"{s.get('name')}|{s.get('size')}|{s.get('mtime')}" not in self._seen]
        if not fresh:  # the common poll: no config read, no store read
            return False
        self._seen.update(f"{s.get('name')}|{s.get('size')}|{s.get('mtime')}" for s in fresh)
        if not self._enabled():  # a shot taken while off is never suggested later
            return False
        found = {}
        for s in fresh:
            ts = _parse(s.get("mtime"))
            if ts is None or not self._in_window(ts):
                continue
            for day, boss in boss_suggestions(ts, self.table):
                found.setdefault(f"{day}|{boss}", _iso(ts))
        if len(self._seen) > MAX_SEEN:
            self._seen = set(list(self._seen)[-MAX_SEEN:])
        if not found:
            return False
        with self._lock:
            have = self._load()
            new = {k: v for k, v in found.items() if k not in have}
            if not new:
                return False
            have.update(new)
            floor = (_bosses.utc_to_pt(_dt.datetime.fromtimestamp(self.clock(), _UTC)).date()
                     - _bosses.TICK_WINDOW_DAYS * _DAY).isoformat()
            have = {k: v for k, v in have.items() if k.split("|", 1)[0] >= floor}
            self.store.put("autotick", {"boss_suggest": have})
        self._changed()
        return True

    def boss_view(self, view):
        """GET /api/bosses + `suggested`: {PT day: [boss]} not yet looted."""
        looted = view.get("looted") if isinstance(view.get("looted"), dict) else {}
        out = {}
        if self._enabled():
            for k in sorted(self._load()):
                day, _, boss = k.partition("|")
                if boss not in (looted.get(day) or []):
                    out.setdefault(day, []).append(boss)
        return dict(view, suggested=out)
