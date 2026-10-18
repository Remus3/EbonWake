"""JSON document store: one file per domain, atomic writes, schema version.

Plan 158: every changing `put` keeps the previous valid bytes as
`<domain>.json.good`, and the first `put` of a local day copies the doc to
`backups/<domain>.<yyyymmdd>.json` (newest BACKUP_KEEP kept per domain). A
corrupt doc restores from `.good`, else the newest valid backup, else the
empty default as before; each restore is listed by `restores()` for a day.
"""

import json
import os
import re
import threading
import time
from pathlib import Path

SCHEMA = 1
BACKUP_DIR = "backups"
BACKUP_KEEP = 7
RESTORE_TTL_S = 86400
_LOCK = threading.Lock()


def atomic_write_json(path, data):
    atomic_write_text(path, json.dumps(data, indent=1, sort_keys=True) + "\n")


def atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    # Windows refuses a replace while another handle reads the target
    # (PermissionError); readers hold handles for microseconds, so retry briefly.
    for attempt in range(20):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.01 * (attempt + 1))


def _doc_data(raw):
    """The `data` dict of a store doc's bytes, or None when they are unreadable."""
    try:
        doc = json.loads(raw.decode("utf-8"))
    except ValueError:  # includes UnicodeDecodeError
        return None
    data = doc.get("data") if isinstance(doc, dict) else None
    return data if isinstance(data, dict) else None


def _read(p):
    try:
        return p.read_bytes()
    except OSError:
        return None


class Store:
    def __init__(self, root, clock=time.time):
        self.root = Path(root)
        self.clock = clock
        self._restores = []  # plan 158: [{domain, source, at}], oldest first

    def _path(self, domain):
        if not domain.replace("_", "").isalnum():
            raise ValueError(f"bad domain name: {domain!r}")
        return self.root / f"{domain}.json"

    def _backups(self, domain):
        """This domain's daily backups, oldest first (exact name match, so
        `notes` never sweeps `notes_b`)."""
        pat = re.compile(re.escape(domain) + r"\.\d{8}\.json")
        try:
            found = [b for b in (self.root / BACKUP_DIR).iterdir() if pat.fullmatch(b.name)]
        except OSError:
            return []
        return sorted(found, key=lambda b: b.name)

    def _restore(self, domain, p):
        """(data, raw, source) from `.good`, else the newest valid backup, else None."""
        candidates = [(p.with_name(p.name + ".good"), "good")]
        candidates += [(b, "backup") for b in reversed(self._backups(domain))]
        for path, source in candidates:
            raw = _read(path)
            data = None if raw is None else _doc_data(raw)
            if data is not None:
                return data, raw, source
        return None

    def restores(self):
        """Plan 158: restores in the last RESTORE_TTL_S, oldest first."""
        cutoff = self.clock() - RESTORE_TTL_S
        with _LOCK:
            self._restores = [r for r in self._restores if r["at"] >= cutoff]
            return [dict(r) for r in self._restores]

    def get(self, domain, default=None):
        p = self._path(domain)
        empty = {} if default is None else default
        with _LOCK:
            for attempt in range(5):
                try:
                    raw = p.read_bytes()
                    break
                except FileNotFoundError:
                    return empty
                except OSError:
                    # A transient lock (antivirus, indexer) on a GOOD file must
                    # never look like corruption: retry, then fail loudly.
                    if attempt == 4:
                        raise
                    time.sleep(0.02 * (attempt + 1))
            data = _doc_data(raw)
            if data is None:
                # Corrupt doc: the bad bytes are kept beside it (renamed, never
                # deleted) for a human to inspect, then the last good copy is
                # put back (plan 158); with none it degrades to empty, never a 500.
                try:
                    p.replace(p.with_name(f"{p.name}.corrupt-{int(time.time())}"))
                except OSError:
                    pass
                found = self._restore(domain, p)
                if found is None:
                    return empty
                data, good, source = found
                try:
                    atomic_write_text(p, good.decode("utf-8"))
                except OSError:
                    pass
                self._restores.append({"domain": domain, "source": source, "at": self.clock()})
            return data

    def put(self, domain, data):
        p = self._path(domain)
        text = json.dumps({"schema": SCHEMA, "data": data}, indent=1, sort_keys=True) + "\n"
        with _LOCK:
            # Plan 158: the previous valid bytes become `.good`, only when the
            # content changes, so a hot domain does not double its IO.
            old = _read(p)
            if old is not None and old != text.encode("utf-8") and _doc_data(old) is not None:
                atomic_write_text(p.with_name(p.name + ".good"), old.decode("utf-8"))
            atomic_write_text(p, text)
            self._daily_backup(domain, text)

    def _daily_backup(self, domain, text):
        """Plan 158: the first put of a local day copies the doc; copies past
        BACKUP_KEEP are pruned (redundant copies of a live doc)."""
        day = time.strftime("%Y%m%d", time.localtime(self.clock()))
        target = self.root / BACKUP_DIR / f"{domain}.{day}.json"
        if target.exists():
            return
        try:
            atomic_write_text(target, text)
            for old in self._backups(domain)[:-BACKUP_KEEP]:
                old.unlink()
        except OSError:
            pass  # a backup fault never fails the operator's write
