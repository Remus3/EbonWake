"""Plan 158: a corrupt operator doc restores from its last-good copy (or a
daily backup) instead of emptying, and the restore is a signal.

tmp_path roots only; a fixed clock drives the local-day rotation.
"""

import datetime as _dt
import json
import time

from server.ew import signals
from server.ew.store import BACKUP_KEEP, Store


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def _noon(y, m, d):
    return time.mktime(_dt.datetime(y, m, d, 12, 0, 0).timetuple())


def _day(t):
    return time.strftime("%Y%m%d", time.localtime(t))


def _store(tmp_path, t=None):
    clock = Clock(_noon(2026, 10, 18) if t is None else t)
    return Store(tmp_path / "store", clock=clock), clock


def test_corrupt_doc_restores_the_previous_put(tmp_path):
    st, _ = _store(tmp_path)
    st.put("notes", {"v": 1})
    st.put("notes", {"v": 2})
    p = tmp_path / "store" / "notes.json"
    p.write_bytes(p.read_bytes()[:10])  # truncation
    bad = p.read_bytes()
    assert st.get("notes") == {"v": 1}
    kept = list((tmp_path / "store").glob("notes.json.corrupt-*"))
    assert len(kept) == 1 and kept[0].read_bytes() == bad
    # The restored doc is written back, so the next read is plain.
    assert json.loads(p.read_text(encoding="utf-8"))["data"] == {"v": 1}
    assert st.get("notes") == {"v": 1}
    assert [r["domain"] for r in st.restores()] == ["notes"]
    assert st.restores()[0]["source"] == "good"


def test_no_good_copy_falls_back_to_empty(tmp_path):
    root = tmp_path / "store"
    root.mkdir()
    (root / "notes.json").write_text("{not json", encoding="utf-8")
    st = Store(root, clock=Clock(_noon(2026, 10, 18)))
    assert st.get("notes") == {}
    assert st.get("notes", default={"d": 1}) == {"d": 1}
    assert st.restores() == []


def test_unchanged_put_writes_no_good(tmp_path):
    st, _ = _store(tmp_path)
    good = tmp_path / "store" / "notes.json.good"
    st.put("notes", {"v": 1})
    assert not good.exists()  # nothing valid before the first put
    st.put("notes", {"v": 1})
    assert not good.exists()  # same content: no extra IO
    st.put("notes", {"v": 2})
    assert json.loads(good.read_text(encoding="utf-8"))["data"] == {"v": 1}
    before = good.stat().st_mtime_ns
    st.put("notes", {"v": 2})
    assert good.stat().st_mtime_ns == before
    assert json.loads(good.read_text(encoding="utf-8"))["data"] == {"v": 1}


def test_corrupt_good_falls_back_to_empty(tmp_path):
    st, _ = _store(tmp_path)
    st.put("notes", {"v": 1})
    st.put("notes", {"v": 2})
    root = tmp_path / "store"
    (root / "notes.json.good").write_text("{junk", encoding="utf-8")
    for b in (root / "backups").glob("*"):
        b.write_text("[1]", encoding="utf-8")  # the daily backup is bad too
    (root / "notes.json").write_text("{junk", encoding="utf-8")
    assert st.get("notes") == {}
    assert st.restores() == []


def test_daily_backup_first_put_of_the_day_and_prune_keeps_7(tmp_path):
    st, clock = _store(tmp_path, _noon(2026, 10, 1))
    backups = tmp_path / "store" / "backups"
    for i in range(10):
        clock.t = _noon(2026, 10, 1 + i)
        st.put("notes", {"day": i})
        st.put("notes", {"day": i, "later": True})  # second put of the day: no new copy
    names = sorted(b.name for b in backups.glob("notes.*.json"))
    assert len(names) == BACKUP_KEEP == 7
    assert names[0] == f"notes.{_day(_noon(2026, 10, 4))}.json"
    assert names[-1] == f"notes.{_day(_noon(2026, 10, 10))}.json"
    last = json.loads((backups / names[-1]).read_text(encoding="utf-8"))
    assert last["data"] == {"day": 9}  # the day's first put


def test_prune_is_per_domain(tmp_path):
    st, clock = _store(tmp_path, _noon(2026, 10, 1))
    st.put("notes_b", {"x": 1})
    for i in range(9):
        clock.t = _noon(2026, 10, 2 + i)
        st.put("notes", {"day": i})
    backups = tmp_path / "store" / "backups"
    assert len(list(backups.glob("notes.*.json"))) == 7
    assert len(list(backups.glob("notes_b.*.json"))) == 1


def test_restore_falls_back_to_newest_backup(tmp_path):
    st, clock = _store(tmp_path, _noon(2026, 10, 1))
    st.put("notes", {"v": 1})
    clock.t = _noon(2026, 10, 2)
    st.put("notes", {"v": 2})
    root = tmp_path / "store"
    (root / "notes.json.good").write_text("{junk", encoding="utf-8")
    (root / "notes.json").write_text("{junk", encoding="utf-8")
    assert st.get("notes") == {"v": 2}
    assert st.restores()[0]["source"] == "backup"


def test_restores_expire_after_a_day(tmp_path):
    st, clock = _store(tmp_path)
    st.put("notes", {"v": 1})
    st.put("notes", {"v": 2})
    (tmp_path / "store" / "notes.json").write_text("{junk", encoding="utf-8")
    st.get("notes")
    assert len(st.restores()) == 1
    clock.t += 86400 + 1
    assert st.restores() == []


def test_digest_carries_the_restores_section():
    item = {"domain": "notes", "source": "good", "at": 1_800_000_000}
    doc = signals.digest({}, 1_800_000_100, restores=[item, "junk", {"domain": 5}])
    assert doc["restores"]["count"] == 1
    r = doc["restores"]["items"][0]
    assert r["domain"] == "notes" and r["level"] == "warn"
    assert r["text"] == "restored notes from last-good"
    assert signals.digest({}, 1_800_000_100)["restores"] == {"count": 0, "items": []}
    assert signals.digest({}, 1_800_000_100, restores="junk")["restores"]["count"] == 0


def test_service_restores_fault_lists_none():
    def boom():
        raise RuntimeError("x")
    svc = signals.SignalService({}, clock=lambda: 1_800_000_000, restores=boom)
    assert svc.view()["restores"] == {"count": 0, "items": []}
