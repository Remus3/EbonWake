"""Plan 108: family fame bonus from the public profile - the tier table and
the estimate used only when no market sell dialog read exists.

`data/fame_tiers.json` {verified, source, read, note, tiers: [{min_fame,
pct}]} maps family fame (combat + life fame of the newest profile refresh)
to the market sale bonus percent. It ships `verified: false`; an empty table
means no estimate (no invented tier data).
"""

import json
from pathlib import Path

from . import market

TIERS_FILE = Path(__file__).resolve().parent / "data" / "fame_tiers.json"
FAME_FIELDS = ("combat_fame", "life_fame")
FAME_MAX = 10 ** 7
ESTIMATE_NOTE = "estimated from profile fame"


def _int(v, lo, hi):
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def clean_tiers(doc):
    """{verified, tiers: [(min_fame, pct)] ascending}; a bad row is dropped."""
    doc = doc if isinstance(doc, dict) else {}
    rows = doc.get("tiers") if isinstance(doc.get("tiers"), list) else []
    out = {}
    for r in rows:
        if isinstance(r, dict) and _int(r.get("min_fame"), 0, FAME_MAX) \
                and market._valid_fame(r.get("pct")):
            out[r["min_fame"]] = r["pct"]
    return {"verified": doc.get("verified") is True, "tiers": sorted(out.items())}


def load_tiers(path=None):
    try:
        doc = json.loads(Path(path or TIERS_FILE).read_text(encoding="ascii"))
    except (OSError, ValueError):
        doc = None
    return clean_tiers(doc)


def profile_fame(snap):
    """Family fame of one profile snapshot row (combat + life), or None."""
    if not isinstance(snap, dict):
        return None
    vals = [snap[k] for k in FAME_FIELDS if _int(snap.get(k), 0, FAME_MAX)]
    return sum(vals) if vals else None


def estimate(tiers, fame):
    """The bonus percent of the highest tier `fame` reaches, or None."""
    if not _int(fame, 0, FAME_MAX * len(FAME_FIELDS)):
        return None
    pct = None
    for lo, p in (tiers or {}).get("tiers", ()):
        if fame >= lo:
            pct = p
    return pct
