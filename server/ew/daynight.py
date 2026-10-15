"""Night drop-chance clock (plan 131): a calibrated game clock derives the
night flag for the plan 038 drop-buff calculator.

BDO's day / night cycle repeats with a fixed real period (`data/daynight.json`:
period_min real minutes per game day, night_min of them night, the game clock
between night_from and night_to running faster), so one calibration point
predicts every night window. The point comes from an operator screenshot of
the minimap with the game-time tooltip open: one more plan 063 auto-OCR kind,
`gametime` (value {"game": "HH:MM"}, confidence gated like every kind).

Phase: a fraction of the cycle, 0 at night start. A read maps its game time to
a phase; the clock at `now` is the newest read's phase plus the real time since
it over the period. A later read checks drift: within TOL_MIN real minutes of
the prediction it confirms the clock; else the period is refit from the first
read of the chain, and only a refit inside BAND of the data period is taken -
anything else is held for review (an operator accept starts a new chain).

The night flag the calculator uses is the clock's, unless the operator typed a
toggle: that is a plan 079 ledger override (`grind.night`), and it ends at the
next day / night change of the clock (or its ledger expiry while uncalibrated).
Store domain `daynight`: {reads: [{id, at, game, file}], period_min|null,
verified_at|null}. Nothing reaches the game: the input is image files the
operator saved with the game's own screenshot key.
"""

import copy
import datetime as _dt
import json
import math
import re
import threading
import time
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data" / "daynight.json"
KIND = "gametime"
DOMAIN = "daynight"
OVERRIDE_KEY = "grind.night"
TOL_MIN = 3.0            # real minutes: a re-read this close confirms the clock
BAND = 0.02              # a refit period must stay within 2 % of the data period
MAX_READS = 20
DAY_MIN = 1440

# Confidence of one read.
CONF_SAME = 0.95         # the time sits on a tooltip line ("Game Time 22:15")
CONF_NEAR = 0.85         # the time sits on a line just below / beside one
CONF_DOT = 0.9           # x factor: 22.15 - a colon read as a dot
CONF_AMBIG = 0.5         # two different times beside the tooltip
NEAR_LINES = 2.5         # line heights below a tooltip line still counted near

HHMM_RE = re.compile(r"^([01][0-9]|2[0-3]):([0-5][0-9])$")
TIME_RE = re.compile(
    r"(?<![0-9:.])(?:(am|pm)\s*)?([0-9]{1,2})\s*([:.])\s*([0-5][0-9])(?![0-9])"
    r"\s*(am|pm|a\.m\.|p\.m\.)?", re.IGNORECASE)


def _iso(ts):
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).replace(microsecond=0).isoformat()


def _ts(v):
    if not isinstance(v, str):
        return None
    try:
        t = _dt.datetime.fromisoformat(v)
    except ValueError:
        return None
    return t.timestamp() if t.tzinfo is not None else None


def _ok_num(v, lo, hi):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) \
        and lo <= v <= hi


def to_min(hhmm):
    """"HH:MM" -> minutes after game midnight; ValueError on anything else."""
    m = HHMM_RE.fullmatch(hhmm) if isinstance(hhmm, str) else None
    if m is None:
        raise ValueError("game time must be HH:MM (00:00..23:59)")
    return int(m.group(1)) * 60 + int(m.group(2))


def fmt(minutes):
    m = int(minutes) % DAY_MIN
    return f"{m // 60:02d}:{m % 60:02d}"


# -- the table ---------------------------------------------------------------------

def clean_table(doc):
    """The validated data row; ValueError on a bad file."""
    if not isinstance(doc, dict):
        raise ValueError("daynight table must be an object")
    period, night = doc.get("period_min"), doc.get("night_min")
    if not _ok_num(period, 60, DAY_MIN):
        raise ValueError("period_min must be 60..1440 real minutes")
    if not _ok_num(night, 1, period - 1):
        raise ValueError("night_min must be inside the period")
    start, end = to_min(doc.get("night_from")), to_min(doc.get("night_to"))
    if start == end:
        raise ValueError("night_from and night_to must differ")
    titles = doc.get("titles")
    titles = [t.lower() for t in titles if isinstance(t, str) and t.strip()] \
        if isinstance(titles, list) else []
    if not titles:
        raise ValueError("titles must list at least one tooltip hint")
    verified = doc.get("verified")
    return {"period_min": float(period), "night_min": float(night),
            "night_from": doc["night_from"], "night_to": doc["night_to"],
            "from_min": start, "span_min": (end - start) % DAY_MIN, "titles": titles,
            "source": doc["source"] if isinstance(doc.get("source"), str) else "",
            "verified": verified if isinstance(verified, (bool, str)) else False}


def load_table(path=None):
    try:
        doc = json.loads(Path(path or DATA_FILE).read_text(encoding="ascii"))
    except (OSError, ValueError) as e:
        raise ValueError(f"daynight table unreadable: {e}") from None
    return clean_table(doc)


# -- pure clock --------------------------------------------------------------------

def phase_of(game_min, t):
    """Game minutes -> phase 0..1 of the cycle (0 = night start)."""
    nf = t["night_min"] / t["period_min"]
    d = (game_min - t["from_min"]) % DAY_MIN
    if d < t["span_min"]:
        return d / t["span_min"] * nf
    return nf + (d - t["span_min"]) / (DAY_MIN - t["span_min"]) * (1 - nf)


def game_at(frac, t):
    """Phase 0..1 -> game minutes (inverse of phase_of)."""
    nf = t["night_min"] / t["period_min"]
    frac %= 1.0
    if frac < nf:
        d = frac / nf * t["span_min"]
    else:
        d = t["span_min"] + (frac - nf) / (1 - nf) * (DAY_MIN - t["span_min"])
    return int(math.floor(t["from_min"] + d + 1e-9)) % DAY_MIN


def clock_at(now, anchor_at, anchor_game, period, t):
    """{night, next_change, phase, game_now} at epoch `now` from one read
    (`anchor_game` "HH:MM" seen at epoch `anchor_at`) and the cycle period."""
    nf = t["night_min"] / t["period_min"]
    f = (phase_of(to_min(anchor_game), t) + (now - anchor_at) / (period * 60.0)) % 1.0
    night = f < nf
    left = ((nf - f) if night else (1.0 - f)) * period * 60.0
    return {"night": night, "next_change": now + left, "phase": f,
            "game_now": fmt(game_at(f, t))}


def check(reads, period, game, shot_at, t):
    """(act, why, period) for a new read against the stored chain: first (no
    chain), skip (older than the newest read), ok (inside TOL_MIN), refit
    (period refit inside BAND; the new period) or hold."""
    if not reads:
        return "first", None, None
    last = reads[-1]
    last_at = _ts(last["at"])
    if shot_at <= last_at:
        return "skip", "older than the newest game-time read", None
    p = period or t["period_min"]
    obs = phase_of(to_min(game), t)
    pred = (phase_of(to_min(last["game"]), t) + (shot_at - last_at) / (p * 60.0)) % 1.0
    err = ((obs - pred + 0.5) % 1.0 - 0.5) * p
    if abs(err) <= TOL_MIN:
        return "ok", None, None
    base = reads[0]
    elapsed = (shot_at - _ts(base["at"])) / 60.0
    df = obs - phase_of(to_min(base["game"]), t)
    cycles = round(elapsed / p - df) + df
    if cycles > 0:
        refit = elapsed / cycles
        if abs(refit - t["period_min"]) / t["period_min"] <= BAND:
            return "refit", f"period refit to {refit:.2f} min", refit
    return ("hold", f"game time {game} is {err:+.0f} min off the clock and no period "
            f"within {BAND * 100:.0f} % of {t['period_min']:g} min fits it", None)


# -- OCR ---------------------------------------------------------------------------

def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _times(text):
    """[(game minutes, dotted)] read on one line."""
    out = []
    for m in TIME_RE.finditer(text):
        h, mm = int(m.group(2)), int(m.group(4))
        ampm = (m.group(1) or m.group(5) or "").lower().replace(".", "")
        if ampm:
            if not 1 <= h <= 12:
                continue
            h = h % 12 + (12 if ampm == "pm" else 0)
        elif h > 23:
            continue
        out.append((h * 60 + mm, m.group(3) == "."))
    return out


def is_gametime(doc, titles):
    lines = doc.get("lines") if isinstance(doc, dict) else None
    hints = [_norm(t) for t in titles]
    return any(isinstance(ln, dict) and isinstance(ln.get("text"), str)
               and any(h and h in _norm(ln["text"]) for h in hints)
               for ln in (lines if isinstance(lines, list) else []))


def parse(doc, titles):
    """[{kind, name, value: {game}, conf, why}] from a minimap game-time
    tooltip shot (at most one field); [] when no tooltip line is seen."""
    lines = [ln for ln in (doc.get("lines") if isinstance(doc, dict) else None) or []
             if isinstance(ln, dict) and isinstance(ln.get("text"), str)]
    hints = [_norm(t) for t in titles]
    tips = [ln for ln in lines if any(h and h in _norm(ln["text"]) for h in hints)]
    if not tips:
        return []
    found = []    # (minutes, conf, why)
    for ln in lines:
        on_tip = ln in tips
        near = on_tip or any(_near(tip, ln) for tip in tips)
        if not near:
            continue
        for mins, dotted in _times(ln["text"]):
            conf = CONF_SAME if on_tip else CONF_NEAR
            why = "time on the tooltip line" if on_tip else "time beside the tooltip"
            if dotted:
                conf, why = conf * CONF_DOT, why + "; colon read as a dot"
            found.append((mins, conf, why))
    if not found:
        return []
    best = max(found, key=lambda f: f[1])
    conf, why = best[1], best[2]
    if len({f[0] for f in found}) > 1:
        conf, why = min(conf, CONF_AMBIG), why + "; another time beside it"
    return [{"kind": KIND, "name": "game time", "value": {"game": fmt(best[0])},
             "conf": round(conf, 3), "why": why}]


def _near(tip, ln):
    try:
        h = max(1.0, float(tip.get("h") or 0))
        dy = float(ln.get("y")) - float(tip.get("y"))
    except (TypeError, ValueError):
        return False
    return -0.5 * h <= dy <= NEAR_LINES * h


def check_value(v):
    if not isinstance(v, dict) or set(v) != {"game"}:
        raise ValueError("a game-time read is {game: HH:MM}")
    to_min(v["game"])
    return {"game": v["game"]}


# -- service -----------------------------------------------------------------------

def _clean_read(r):
    if not (isinstance(r, dict) and isinstance(r.get("id"), str) and _ts(r.get("at")) is not None
            and isinstance(r.get("game"), str) and HHMM_RE.fullmatch(r["game"])):
        return None
    return {"id": r["id"][:20], "at": r["at"], "game": r["game"],
            "file": r["file"][:255] if isinstance(r.get("file"), str) else ""}


def clean(doc, t=None):
    doc = doc if isinstance(doc, dict) else {}
    reads = [c for c in map(_clean_read, doc.get("reads") if isinstance(
        doc.get("reads"), list) else []) if c is not None]
    reads.sort(key=lambda r: _ts(r["at"]))
    period = doc.get("period_min")
    base = t["period_min"] if t else None
    ok = _ok_num(period, 1, DAY_MIN) and (base is None or abs(period - base) / base <= BAND)
    v = doc.get("verified_at")
    return {"reads": reads[-MAX_READS:], "period_min": float(period) if ok else None,
            "verified_at": v if _ts(v) is not None else None}


class DayNightService:
    """The calibrated clock. `ledger` (plan 079 OverrideLedger) holds the typed
    night toggle; without one the toggle is not available here."""

    def __init__(self, store, table=None, clock=time.time, ledger=None, path=None):
        self.store = store
        self.clock = clock
        self.ledger = ledger
        self.error = None
        if table is None:
            try:
                table = load_table(path)
            except ValueError as e:
                table, self.error = None, str(e)
        self.table = table
        self._lock = threading.RLock()

    @property
    def titles(self):
        return self.table["titles"] if self.table else []

    def _need(self):
        if self.table is None:
            raise ValueError(f"day/night table unavailable: {self.error}")
        return self.table

    def _doc(self):
        return clean(self.store.get(DOMAIN), self.table)

    def _period(self, d):
        return d["period_min"] or self.table["period_min"]

    def ocr_check(self, value, shot_at):
        """(ok|skip|hold, why) for an auto-OCR read before it is committed."""
        t = self._need()
        game = check_value(value)["game"]
        d = self._doc()
        act, why, _ = check(d["reads"], d["period_min"], game, shot_at, t)
        return ("ok", why) if act in ("first", "ok", "refit") else (act, why)

    def commit(self, value, file, shot_at, uid, force=False):
        """Store one read; returns the doc before it (the undo state). A held
        read raises unless `force` (an operator accept), which starts a new chain."""
        t = self._need()
        game = check_value(value)["game"]
        with self._lock:
            d = self._doc()
            prev = copy.deepcopy(d)
            act, why, period = check(d["reads"], d["period_min"], game, shot_at, t)
            read = {"id": str(uid)[:20], "at": _iso(shot_at), "game": game,
                    "file": file[:255] if isinstance(file, str) else ""}
            if act == "skip":
                raise ValueError(why)
            if act == "hold" and not force:
                raise ValueError(why)
            if act in ("first", "hold"):
                d = {"reads": [read], "period_min": None, "verified_at": None}
            else:
                d["reads"] = (d["reads"] + [read])[-MAX_READS:]
                d["verified_at"] = _iso(self.clock())
                if act == "refit":
                    d["period_min"] = round(period, 4)
            self.store.put(DOMAIN, d)
        return prev

    def restore(self, uid, prev):
        """Undo of one committed read: only while it is still the newest."""
        with self._lock:
            d = self._doc()
            if not d["reads"] or d["reads"][-1]["id"] != uid:
                raise ValueError("the game clock was read again since; undo the newer read first")
            self.store.put(DOMAIN, clean(prev, self.table))

    def state(self, now=None):
        """The clock at `now`, or None while uncalibrated."""
        if self.table is None:
            return None
        d = self._doc()
        if not d["reads"]:
            return None
        a = d["reads"][-1]
        now = self.clock() if now is None else now
        return clock_at(now, _ts(a["at"]), a["game"], self._period(d), self.table)

    def effective(self, now=None):
        """{night, via: clock|override|null, until_utc, calibrated}: the typed
        toggle (until the next day / night change) over the clock; via null =
        neither (the calculator's own toggle applies)."""
        now = self.clock() if now is None else now
        st = self.state(now)
        out = {"calibrated": st is not None,
               "next_change_utc": _iso(st["next_change"]) if st else None}
        ov = self._override(now, st)
        if ov is not None:
            return dict(out, night=ov[0], via="override",
                        until_utc=_iso(ov[1]) if ov[1] is not None else None)
        if st is not None:
            return dict(out, night=st["night"], via="clock", until_utc=out["next_change_utc"])
        return dict(out, night=False, via=None, until_utc=None)

    def _override(self, now, st):
        if self.ledger is None or not self.ledger.covers(OVERRIDE_KEY):
            return None
        r = self.ledger.effective(OVERRIDE_KEY, None, None, now)
        if r["from"] != "override":
            return None
        e = r["entry"]
        until = _ts(e.get("expires_at"))
        if st is not None:
            set_at = _ts(e.get("set_at"))
            change = self.state(set_at)["next_change"] if set_at is not None else now
            until = change if until is None else min(until, change)
        if until is not None and until <= now:
            self.ledger.clear(OVERRIDE_KEY, by="clock", now=now)
            return None
        return bool(r["value"]), until

    def set_override(self, on, now=None):
        """The typed night toggle as a ledger override."""
        if self.ledger is None:
            raise ValueError("the override ledger is not available")
        if not isinstance(on, bool):
            raise ValueError("on must be true or false")
        now = self.clock() if now is None else now
        self.ledger.set(OVERRIDE_KEY, on, reason="typed night toggle; ends at the next "
                        "day / night change of the clock", now=now)

    def view(self, now=None):
        """GET /api/daynight."""
        now = self.clock() if now is None else now
        if self.table is None:
            return {"error": self.error, "calibrated": False, "night": False, "via": None,
                    "until_utc": None, "next_change_utc": None}
        t = self.table
        d = self._doc()
        st = self.state(now)
        eff = self.effective(now)
        a = d["reads"][-1] if d["reads"] else None
        return dict(eff, error=None, game_now=st["game_now"] if st else None,
                    night_now=st["night"] if st else None,
                    ends_in_s=max(0, int(st["next_change"] - now)) if st else None,
                    period_min=self._period(d), night_min=t["night_min"],
                    night_from=t["night_from"], night_to=t["night_to"],
                    refit=d["period_min"] is not None, source=t["source"],
                    verified=bool(t["verified"]) or d["verified_at"] is not None,
                    verified_at=d["verified_at"], reads=len(d["reads"]),
                    anchor={"at": a["at"], "game": a["game"], "file": a["file"]} if a else None,
                    at=_iso(now))
