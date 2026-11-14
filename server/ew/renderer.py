"""Plan 175: DX12 renderer compatibility probe.

Patch 2026-10-29 added a DirectX 12 / FSR 3.1 renderer option. Two silent
breaks would look like "no data": the overlay window no longer drawing above
the client, and ScreenShot files changing name or image format. This module
checks both from EW's own side only:

- `check(history, latest)` (pure): the newest ScreenShot file's extension and
  pixel size against the watcher's own history (store domain `renderer`). A
  format first seen after another one flags `new_ext` / `new_size`; an empty
  history and a known format stay quiet. The flag sticks while the shot that
  introduced the format is still the newest, so a re-read is a no-op.
- `image_size(path)`: width x height from the image header only (PNG IHDR,
  JPEG SOF, BMP DIB) of a file in the operator's ScreenShot folder; nothing
  else of the file is decoded.
- `RendererProbe`: the plan 073 digest input (`renderer` row) and the
  operator's overlay test-pattern result, a plan 079 typed override
  (`overlay.test_pattern`) that retires (`retired_by: "patch"`) once plan
  174's cached notice list shows a patch dated after the day it was set.

Game ToS floor: no client file, memory, packet or window-handle access. The
inputs are the plan 008 watcher's file metadata and EW's own window.
"""

import datetime as _dt
import os
import struct
import threading
import time
from pathlib import Path

from . import dataverdicts

DOMAIN = "renderer"
KEY = "overlay.test_pattern"
RENDERERS = ("dx11", "dx12")
HISTORY_MAX = 20
HEAD_MAX = 256 * 1024  # a JPEG's SOF follows its EXIF / ICC segments
SIZE_CACHE = 16
_SOF = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}


def ext_of(name):
    """Lower-case extension with its dot, '' when the name has none."""
    return os.path.splitext(name)[1].lower() if isinstance(name, str) else ""


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _ts(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if not isinstance(v, str):
        return None
    try:
        when = _dt.datetime.fromisoformat(v)
    except ValueError:
        return None
    return when.timestamp() if when.tzinfo is not None else None


# -- image header ----------------------------------------------------------------

def _png(b):
    if len(b) >= 24 and b[:8] == b"\x89PNG\r\n\x1a\n" and b[12:16] == b"IHDR":
        return struct.unpack(">II", b[16:24])
    return None


def _jpeg(b):
    if b[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 4 <= len(b):
        if b[i] != 0xFF:
            return None
        marker = b[i + 1]
        if marker == 0xFF:  # fill byte
            i += 1
            continue
        if marker in (0x01, *range(0xD0, 0xD9)):  # standalone markers
            i += 2
            continue
        if marker in (0xD9, 0xDA):  # end of image / start of scan: no SOF before it
            return None
        seg = struct.unpack(">H", b[i + 2:i + 4])[0]
        if marker in _SOF:
            if i + 9 > len(b):
                return None
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        i += 2 + seg
    return None


def _bmp(b):
    if len(b) < 26 or b[:2] != b"BM":
        return None
    dib = struct.unpack("<I", b[14:18])[0]
    if dib == 12:
        return struct.unpack("<HH", b[18:22])
    if dib >= 40:
        w, h = struct.unpack("<ii", b[18:26])
        return w, abs(h)
    return None


def image_size(path):
    """(width, height) from the image header, or None (unknown format, short
    or unreadable file). Read-only, at most HEAD_MAX bytes."""
    try:
        with open(path, "rb") as f:
            head = f.read(HEAD_MAX)
    except OSError:
        return None
    for fn in (_png, _jpeg, _bmp):
        try:
            got = fn(head)
        except struct.error:
            got = None
        if got is not None:
            w, h = got
            return (w, h) if w > 0 and h > 0 else None
    return None


# -- history + flag (pure) ---------------------------------------------------------

def empty():
    return {"formats": []}


def _clean_fmt(f):
    if not (isinstance(f, dict) and isinstance(f.get("ext"), str)
            and isinstance(f.get("first_name"), str)):
        return None
    w, h = _int(f.get("w")), _int(f.get("h"))
    if w is None or h is None:
        w = h = None
    was = f.get("was_ext")
    return {"ext": f["ext"], "w": w, "h": h, "first_name": f["first_name"],
            "first_at": _ts(f.get("first_at")), "new_ext": f.get("new_ext") is True,
            "new_size": f.get("new_size") is True,
            "was_ext": [e for e in was if isinstance(e, str)] if isinstance(was, list) else []}


def clean(doc):
    raw = doc.get("formats") if isinstance(doc, dict) else None
    fmts = [c for c in map(_clean_fmt, raw if isinstance(raw, list) else []) if c is not None]
    return {"formats": fmts[-HISTORY_MAX:]}


def _clean_latest(s):
    if not (isinstance(s, dict) and isinstance(s.get("name"), str) and s["name"]):
        return None
    w, h = _int(s.get("w")), _int(s.get("h"))
    if w is None or h is None:
        w = h = None
    return {"name": s["name"], "ext": ext_of(s["name"]), "w": w, "h": h, "at": _ts(s.get("at"))}


def check(history, latest):
    """(history', result). result = {latest, new_ext, new_size, was_ext}:
    the newest shot's format against every format seen before it."""
    hist = clean(history)
    shot = _clean_latest(latest)
    res = {"latest": shot, "new_ext": False, "new_size": False, "was_ext": []}
    if shot is None:
        return hist, res
    fmts = hist["formats"]
    hit = next((f for f in fmts if (f["ext"], f["w"], f["h"]) == (shot["ext"], shot["w"], shot["h"])),
               None)
    if hit is None:
        exts = sorted({f["ext"] for f in fmts})
        sizes = {(f["w"], f["h"]) for f in fmts if f["w"] is not None}
        hit = {"ext": shot["ext"], "w": shot["w"], "h": shot["h"], "first_name": shot["name"],
               "first_at": shot["at"],
               "new_ext": bool(fmts) and shot["ext"] not in exts,
               "new_size": bool(sizes) and shot["w"] is not None
               and (shot["w"], shot["h"]) not in sizes,
               "was_ext": exts if fmts else []}
        hist = {"formats": (fmts + [hit])[-HISTORY_MAX:]}
    if hit["first_name"] == shot["name"]:
        res.update(new_ext=hit["new_ext"], new_size=hit["new_size"], was_ext=list(hit["was_ext"]))
    return hist, res


# -- the overlay test result -------------------------------------------------------

def clean_result(body):
    """{renderer, seen} from a Settings POST body, else ValueError."""
    if not (isinstance(body, dict) and set(body) == {"renderer", "seen"}
            and body["renderer"] in RENDERERS and isinstance(body["seen"], bool)):
        raise ValueError('overlay_test must be {"renderer": "dx11"|"dx12", "seen": true|false}')
    return {"renderer": body["renderer"], "seen": body["seen"]}


def _plain_name(name):
    return (isinstance(name, str) and name not in ("", ".", "..") and "/" not in name
            and "\\" not in name and ":" not in name and "\x00" not in name)


class RendererProbe:
    """`game`: the plan 008 GameWatch (view / health / documents_dir), `store`:
    the JSON store, `ledger`: the plan 079 OverrideLedger, `listed`: () -> plan
    064's cached notice rows (plan 174, never a fetch)."""

    def __init__(self, game, store, ledger, listed=None, clock=time.time, size_fn=image_size):
        self.game = game
        self.store = store
        self.ledger = ledger
        self.listed = listed
        self.clock = clock
        self.size_fn = size_fn
        self._sizes = {}
        self._lock = threading.Lock()

    def _shot_dir(self):
        d = getattr(self.game, "documents_dir", None)
        return Path(d) / "ScreenShot" if d else None

    def _candidates(self):
        try:
            shots = (self.game.view() or {}).get("screenshots") or []
        except Exception:  # noqa: BLE001 - no watcher view = no shot
            shots = []
        fn = getattr(self.game, "health", None)
        try:
            other = (fn() or {}).get("other_shot") if fn is not None else None
        except Exception:  # noqa: BLE001 - the other-extension slot is optional
            other = None
        return [s for s in list(shots) + [other] if isinstance(s, dict)]

    def _size(self, name, s):
        key = (name, s.get("size"), s.get("mtime"))
        if key in self._sizes:
            return self._sizes[key]
        d = self._shot_dir()
        got = None
        if d is not None:
            try:
                got = self.size_fn(d / name)
            except Exception:  # noqa: BLE001 - an unreadable header = size unknown
                got = None
        if len(self._sizes) >= SIZE_CACHE:
            self._sizes.clear()
        self._sizes[key] = got
        return got

    def latest(self):
        """{name, ext, w, h, at} of the newest file the watcher saw, or None."""
        best = None
        for s in self._candidates():
            at = _ts(s.get("mtime"))
            if at is None or not _plain_name(s.get("name")):
                continue
            if best is None or at > best[0]:
                best = (at, s)
        if best is None:
            return None
        at, s = best
        wh = self._size(s["name"], s)
        w, h = wh if isinstance(wh, tuple) and len(wh) == 2 else (None, None)
        return {"name": s["name"], "ext": ext_of(s["name"]), "w": w, "h": h, "at": at}

    def expire(self):
        """Retire the test result once a patch dated after its set day is listed."""
        e = self.ledger.doc()["live"].get(KEY)
        if e is None or self.listed is None:
            return
        try:
            newest = dataverdicts.newest_patch(self.listed())
        except Exception:  # noqa: BLE001 - a broken list cache expires nothing
            newest = None
        if newest is not None and newest["date"] > str(e.get("set_at") or "")[:10]:
            self.ledger.clear(KEY, by="patch", now=self.clock())

    def test(self):
        """{renderer, seen, set_at, expires_at} of the live result, or None."""
        self.expire()
        e = self.ledger.doc()["live"].get(KEY)
        v = e.get("value") if e else None
        if not (isinstance(v, dict) and v.get("renderer") in RENDERERS
                and isinstance(v.get("seen"), bool)):
            return None
        return {"renderer": v["renderer"], "seen": v["seen"], "set_at": e["set_at"],
                "expires_at": e.get("expires_at")}

    def record(self, body):
        """Settings POST {renderer, seen}: a typed override set now."""
        value = clean_result(body)
        self.ledger.set(KEY, value, source="typed", reason="overlay test pattern, checked by eye",
                        now=self.clock())
        return {"test": self.test()}

    def signal(self):
        """Plan 073 `renderer` row input; persists a newly seen format."""
        latest = self.latest()
        with self._lock:
            before = clean(self.store.get(DOMAIN))
            hist, res = check(before, latest)
            if hist != before:
                self.store.put(DOMAIN, hist)
        return dict(res, test=self.test())
