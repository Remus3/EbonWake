"""Plan 174: flag data rows when a newer official patch exists than the one the
plan 085 verifier last checked (suggest-only digest line on the `data` row).

Fixture dicts and a seeded list cache only; no network, tracked data never written.
"""

import datetime as dt

from server.ew import dataverdicts, eventnotices, signals

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 11, 6, 14, 0, 0, tzinfo=UTC).timestamp()
OLD = "[Updates] Patch Notes - October 29, 2026"
NEW = "[Updates] Patch Notes - November 5, 2026"


def _listed(no, title, stamp=None):
    return {"group_no": no, "title": title, "url": eventnotices.detail_url(no), "stamp": stamp,
            "board": 2}


def _note(no, title):
    return {"group_no": no, "title": title, "url": eventnotices.detail_url(no), "stamp": None,
            "fetched_at": T0, "text": "nothing hinted here"}


def _svc(tmp_path, notes, listed):
    return dataverdicts.VerdictService(lambda: notes, path=tmp_path / "v.json",
                                       clock=lambda: T0, listed=lambda: listed)


def _data_row(inp):
    doc = signals.digest({"data": inp}, T0)
    return next(r for r in doc["rows"] if r["id"] == "data")


# --- pure: newest listed patch -----------------------------------------------------------

def test_newest_patch_picks_latest_dated_patch_title():
    rows = [_listed(10700, OLD), _listed(10720, NEW), _listed(10730, "[Events] Hot Time"),
            _listed(10690, "[Updates] Patch Notes", stamp="2026-10-22"), "junk", {"title": 3}]
    got = dataverdicts.newest_patch(rows)
    assert got == {"date": "2026-11-05", "title": NEW, "notice_no": 10720,
                   "url": eventnotices.detail_url(10720)}
    assert dataverdicts.newest_patch([]) is None
    assert dataverdicts.newest_patch(None) is None
    assert dataverdicts.newest_patch([_listed(1, "[Updates] Patch Notes")]) is None  # no date


def test_newer_compares_dates():
    newest = {"date": "2026-11-05", "title": NEW, "notice_no": 10720, "url": "u"}
    assert dataverdicts.newer({"date": "2026-10-29"}, newest) == newest
    assert dataverdicts.newer({"date": "2026-11-05"}, newest) is None  # equal -> none
    assert dataverdicts.newer({"date": "2026-11-12"}, newest) is None
    assert dataverdicts.newer(None, newest) is None  # missing verifier state -> quiet
    assert dataverdicts.newer({"date": None}, newest) is None
    assert dataverdicts.newer({"date": "2026-10-29"}, None) is None


# --- service: signal input ----------------------------------------------------------------

def test_signal_flags_listed_patch_newer_than_verified(tmp_path):
    svc = _svc(tmp_path, [_note(10700, OLD)], [_listed(10700, OLD), _listed(10720, NEW)])
    sig = svc.signal()
    assert sig["newer"] == {"verified": "2026-10-29", "date": "2026-11-05", "title": NEW,
                            "notice_no": 10720, "url": eventnotices.detail_url(10720)}


def test_signal_equal_patch_is_not_flagged(tmp_path):
    svc = _svc(tmp_path, [_note(10720, NEW)], [_listed(10700, OLD), _listed(10720, NEW)])
    assert svc.signal()["newer"] is None


def test_signal_missing_verifier_state_is_quiet(tmp_path):
    svc = _svc(tmp_path, [], [_listed(10720, NEW)])
    assert svc.signal()["newer"] is None


def test_signal_clears_once_verifier_records_newer_date(tmp_path):
    listed = [_listed(10700, OLD), _listed(10720, NEW)]
    assert _svc(tmp_path, [_note(10700, OLD)], listed).signal()["newer"] is not None
    later = _svc(tmp_path, [_note(10700, OLD), _note(10720, NEW)], listed)
    assert later.signal()["newer"] is None


def test_signal_listing_fault_is_quiet(tmp_path):
    def boom():
        raise RuntimeError("cache")
    svc = dataverdicts.VerdictService(lambda: [_note(10700, OLD)], path=tmp_path / "v.json",
                                      clock=lambda: T0, listed=boom)
    assert svc.signal()["newer"] is None
    plain = dataverdicts.VerdictService(lambda: [_note(10700, OLD)], path=tmp_path / "w.json",
                                        clock=lambda: T0)
    assert plain.signal()["newer"] is None


def test_tracked_data_and_verdicts_untouched_by_flag(tmp_path):
    svc = _svc(tmp_path, [_note(10700, OLD)], [_listed(10720, NEW)])
    before = svc.view()
    svc.signal()
    assert svc.view() == before  # suggest-only: no verdict edit


# --- digest row ---------------------------------------------------------------------------

NEWER = {"verified": "2026-10-29", "date": "2026-11-05", "title": NEW, "notice_no": 10720,
         "url": "u"}
LAST = {"notice_no": 10700, "title": OLD, "url": "u", "date": "2026-10-29"}


def test_digest_row_shows_one_newer_line_with_hint():
    r = _data_row({"last_notice": LAST, "confirmed": 3, "unchecked": 1, "contradicted": [],
                   "newer": NEWER})
    assert (r["level"], r["reason"]) == ("warn", "patch_newer")
    assert r["detail"] == "data verified against 2026-10-29, patch 2026-11-05 is newer"
    assert r["lines"] == []
    assert "verifier" in r["hint"]


def test_digest_row_equal_or_missing_is_ok():
    for newer in (None, "junk"):
        r = _data_row({"last_notice": LAST, "confirmed": 3, "unchecked": 1, "contradicted": [],
                       "newer": newer})
        assert (r["level"], r["reason"]) == ("ok", None)
    r = _data_row({"last_notice": None, "unchecked": 1, "contradicted": []})
    assert (r["level"], r["reason"]) == ("ok", None)


def test_digest_contradicted_wins_and_carries_the_newer_line():
    bad = [{"key": "a.json#x", "evidence": "x to 5%", "date": "2026-10-29"}]
    r = _data_row({"last_notice": LAST, "contradicted": bad, "newer": NEWER})
    assert r["reason"] == "contradicted"
    assert r["lines"][-1] == "data verified against 2026-10-29, patch 2026-11-05 is newer"


# --- notice client: listed patches from the cached list (no fetch) ------------------------

def test_client_listed_reads_cached_list_only(tmp_path):
    calls = []

    def fetch(url, timeout):
        calls.append(url)
        raise AssertionError("no network")
    client = eventnotices.NoticeClient(fetch=fetch, clock=lambda: T0, cache_dir=tmp_path / "c")
    assert client.listed() == []
    rows = [_listed(10720, NEW), _listed(10730, "[Events] Hot Time"), {"group_no": "bad"}]
    client.cached_get(eventnotices.KEY, eventnotices.TTL_S, lambda: {"notices": rows})
    got = client.listed()
    assert [n["group_no"] for n in got] == [10720, 10730]
    assert dataverdicts.newest_patch(got)["date"] == "2026-11-05"
    assert calls == []
