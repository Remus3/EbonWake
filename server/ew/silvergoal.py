"""Weekly silver goal (plan 140): this week's earned silver against a goal, with
the pace needed per remaining day and a projection at the trailing 7-day rate.

Pure over EW's own ledgers: grind sessions (plan 005 typed rows, plan 112 auto
rows) and the inventory sales log (plan 045 / 123). The week is the plan 021
NA weekly reset window (today.last_weekly_reset / next_weekly_reset), the same
rule the Today weeklies use.

De-duplication: a plan 112 auto row whose silver is an OCR wallet delta
(`silver_src: "ocr_delta"`, window `silver_from` first_at..last_at) already
contains any sale collected inside that window, so sales win and the delta
keeps only what the sales do not explain (floored at 0). A typed amount is the
operator's own number and is never trimmed.

The goal is an explicit override (plan 079 key `grind.week_goal`, expiring at
the weekly reset), else the median of the last 4 full weeks' earned plus 10
percent (weeks before the first ledger entry do not count), else none: the
card hides itself. All silver is integer. Nothing is read from the game.
"""

import datetime as _dt
import math
import time

from . import grind, market
from .today import _iso, _parse_iso, last_weekly_reset, next_weekly_reset

OVERRIDE_KEY = "grind.week_goal"
MAX_GOAL = grind.MAX_SILVER
HISTORY_WEEKS = 4
UPLIFT_PCT = 110
TRAIL_DAYS = 7
_DAY = _dt.timedelta(days=1)
_WEEK = 7 * _DAY


def week_window(now):
    """(start, end) of the NA weekly reset window holding `now`."""
    return last_weekly_reset(now), next_weekly_reset(now)


def _list(v):
    return v if isinstance(v, list) else []


def _sale_rows(raw):
    """[(at, net)] for each well-formed sale; net per plan 027 at the sale's fame."""
    out = []
    for s in _list(raw):
        if not isinstance(s, dict):
            continue
        at = _parse_iso(s.get("at"))
        try:
            net = market.net_proceeds(s.get("price"), s.get("vp") is True, s.get("fame_pct", 0))
        except ValueError:
            net = None
        if at is not None and net is not None:
            out.append((at, net))
    return out


def entries(sources):
    """[(at, silver)] after de-duplication: one row per session (at its start)
    and one per sale (at its time)."""
    src = sources if isinstance(sources, dict) else {}
    sales = _sale_rows(src.get("sales"))
    out = list(sales)
    for raw in _list(src.get("sessions")):
        s = grind._clean_session(raw)
        if s is None:
            continue
        silver = s["silver"]
        sf = s.get("silver_from")
        if s.get("silver_src") == "ocr_delta" and sf is not None:
            lo, hi = _parse_iso(sf["first_at"]), _parse_iso(sf["last_at"])
            covered = sum(n for at, n in sales if lo <= at <= hi)
            silver = max(0, silver - covered)
        out.append((_parse_iso(s["started"]), silver))
    return out


def _sum(rows, since, until):
    return sum(n for at, n in rows if since <= at < until)


def earned_week(sources, week):
    """Integer silver earned in `week` (start, end): sessions + sales net, de-duplicated."""
    return _sum(entries(sources), week[0], week[1])


def _median_uplift(vals):
    xs = sorted(vals)
    n = len(xs)
    if n % 2:
        return xs[n // 2] * UPLIFT_PCT // 100
    return (xs[n // 2 - 1] + xs[n // 2]) * UPLIFT_PCT // 200


def _is_goal(v):
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def goal(sources, now, override=None):
    """{value, source: override|history|None, weeks: [earned, ...] oldest first}."""
    rows = entries(sources)
    start = week_window(now)[0]
    weeks = []
    if rows:
        first = min(at for at, _ in rows)
        for back in range(HISTORY_WEEKS, 0, -1):
            ws = start - back * _WEEK
            if ws + _WEEK > first:  # history had begun by the end of this week
                weeks.append(_sum(rows, ws, ws + _WEEK))
    if _is_goal(override):
        return {"value": override, "source": "override", "weeks": weeks}
    value = _median_uplift(weeks) if weeks else 0
    if value <= 0:
        return {"value": None, "source": None, "weeks": weeks}
    return {"value": value, "source": "history", "weeks": weeks}


def pace(sources, now, earned, goal_value):
    """{days_left, needed_per_day, rate_per_day, projection, on_track}; integers.
    days_left counts a part day as a day; the projection adds the trailing
    7-day rate over the exact time left."""
    end = week_window(now)[1]
    secs = max(0, int((end - now).total_seconds()))
    days_left = max(1, math.ceil(secs / 86400))
    rate = _sum(entries(sources), now - TRAIL_DAYS * _DAY, now + _dt.timedelta(seconds=1)) \
        // TRAIL_DAYS
    left = max(0, goal_value - earned)
    projection = earned + rate * secs // 86400
    return {"days_left": days_left, "needed_per_day": -(-left // days_left),
            "rate_per_day": rate, "projection": projection,
            "on_track": earned >= goal_value or projection >= goal_value}


def view(sources, now, override=None, running=False):
    """GET /api/silvergoal body. `hidden` while there is no goal (zero-touch)."""
    week = week_window(now)
    earned = earned_week(sources, week)
    g = goal(sources, now, override)
    p = pace(sources, now, earned, g["value"]) if g["value"] is not None else None
    return {"now": _iso(now), "week": {"start": _iso(week[0]), "end": _iso(week[1])},
            "earned": earned, "goal": g["value"], "goal_source": g["source"],
            "history": g["weeks"], "pace": p, "hidden": g["value"] is None,
            "running": running is True}


class SilverGoalService:
    """GET /api/silvergoal over store domains `grind` + `inventory` (whole
    ledgers, not the 200-row GET views). The typed goal is ledger key
    OVERRIDE_KEY, written through the existing POST /api/grind route
    ({"week_goal": silver | null}); `running()` -> bool is the game state."""

    def __init__(self, store, ledger, clock=time.time, running=None):
        self.store = store
        self.ledger = ledger
        self.clock = clock
        self.running = running

    def _now(self):
        return _dt.datetime.fromtimestamp(self.clock(), _dt.timezone.utc)

    def _override(self, now):
        if self.ledger is None:
            return None
        return self.ledger.effective(OVERRIDE_KEY, None, 0, now=now.timestamp())["value"]

    def _running(self):
        try:
            return self.running is not None and self.running() is True
        except Exception:  # noqa: BLE001 - the game flag is an extra, never fatal
            return False

    def sources(self):
        def domain(name, key):
            doc = self.store.get(name)
            return _list(doc.get(key)) if isinstance(doc, dict) else []
        return {"sessions": domain("grind", "sessions"), "sales": domain("inventory", "sales")}

    def view(self):
        now = self._now()
        return view(self.sources(), now, self._override(now), self._running())

    def set_goal(self, value):
        """A typed goal (int silver, > 0) until the weekly reset; null clears it."""
        if self.ledger is None:
            raise ValueError("the override ledger is not available")
        if value is None:
            self.ledger.clear(OVERRIDE_KEY)
        elif not _is_goal(value) or value > MAX_GOAL:
            raise ValueError(f"week_goal must be null or an int silver in 1..{MAX_GOAL}")
        else:
            self.ledger.set(OVERRIDE_KEY, value, reason="typed weekly silver goal; ends at "
                            "the weekly reset")
        return self.view()
