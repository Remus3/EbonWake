"""Plan 151 hardening audit of tests/test_[m-z]*.py (docs/audit/20261017-tests-b.md);
plan 157 (TESTS-B-07) extends both guards to every tests/test_*.py file.

AST guards over the slice, so the fixed hygiene cannot drift back:

TESTS-B-01: a test server never falls back to the host's own state. Without
config_path= the Settings / override ledger / onboarding read (and a settings
POST writes) the repo's real config/local.json; without market_client= the
default ArshaClient reads and writes the live ops/runtime market cache with a
real network fetch; without profile_cfg= / profile_client= the host's profile
family is read from config/local.json.

TESTS-B-02: every test function or fixture that builds a server closes it, and
every helper that opens an HTTPConnection closes it.
"""

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Plan 157 (TESTS-B-07): the guard covers every tests/test_*.py file, not
# only the [m-z] slice plan 151 audited.
SLICE = sorted(HERE.glob("test_*.py"))
ISOLATION = ("config_path", "market_client", "market_seed")
PROFILE = ("profile_cfg", "profile_client")
# Tests whose subject IS the default fallback (they run under the plan 150
# hermetic host, so the fallback reaches a tmp copy, never the real repo).
FALLBACK_TESTS = {
    "test_hermetic_p150.py": {"test_server_defaults_are_isolated"},
    "test_config_path_p155.py": {"test_server_reads_only_the_injected_config_path",
                                 "test_server_without_config_path_keeps_the_default_file"},
}


def _name(func):
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and _name(n.func) == name]


def _functions(tree):
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _outermost(tree):
    """Functions not nested in another function (fixtures, tests, helpers)."""
    inner = {id(m) for f in _functions(tree) for m in ast.walk(f) if m is not f
             and isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return [f for f in _functions(tree) if id(f) not in inner]


def missing_isolation(tree, skip=()):
    """make_server(...) calls that let the server reach the host's state
    (calls inside a function named in skip are the fallback's own tests)."""
    skipped = {id(c) for f in _outermost(tree) if f.name in skip
               for c in _calls(f, "make_server")}
    out = []
    for call in _calls(tree, "make_server"):
        if id(call) in skipped:
            continue
        kw = {k.arg for k in call.keywords}
        gaps = [k for k in ISOLATION if k not in kw]
        if not kw & set(PROFILE):
            gaps.append("profile_cfg|profile_client")
        if gaps:
            out.append((call.lineno, gaps))
    return out


def unclosed(tree):
    """Functions that build a server without server_close() or open an
    HTTPConnection without close()."""
    out = []
    for fn in _outermost(tree):
        if _calls(fn, "make_server") and not _calls(fn, "server_close"):
            out.append((fn.lineno, fn.name, "server_close"))
        if _calls(fn, "HTTPConnection") and not _calls(fn, "close"):
            out.append((fn.lineno, fn.name, "close"))
    return out


def _scan(check):
    bad = {}
    for p in SLICE:
        tree = ast.parse(p.read_text(encoding="utf-8"))
        if check is missing_isolation:
            found = check(tree, FALLBACK_TESTS.get(p.name, ()))
        else:
            found = check(tree)
        if found:
            bad[p.name] = found
    return bad


def test_slice_is_every_test_file():
    names = [p.name for p in SLICE]
    assert "test_app_routes.py" in names and "test_zoneinfo.py" in names
    assert names == sorted(p.name for p in HERE.glob("test_*.py"))


def test_b01_every_slice_server_is_isolated_from_the_host():
    assert _scan(missing_isolation) == {}


def test_fallback_exemptions_name_real_functions():
    # a renamed or deleted fallback test must not leave a stale exemption
    for name, funcs in FALLBACK_TESTS.items():
        tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
        have = {f.name for f in _outermost(tree) if _calls(f, "make_server")}
        assert funcs <= have, (name, funcs - have)
    bad = ast.parse("def t(tmp_path):\n    make_server(port=0)\n")
    assert missing_isolation(bad, {"t"}) == [] and missing_isolation(bad) != []


def test_b02_every_slice_server_and_connection_is_closed():
    assert _scan(unclosed) == {}


def test_guards_catch_the_bad_shapes():
    bad = ast.parse(
        "def srv(tmp_path):\n"
        "    s = ewapp.make_server(port=0, store_root=tmp_path, market_seed=[])\n"
        "    yield s\n"
        "    s.shutdown()\n"
        "def _post(s):\n"
        "    c = http.client.HTTPConnection('127.0.0.1', 1, timeout=5)\n"
        "    return c.getresponse()\n")
    assert missing_isolation(bad) == [(2, ["config_path", "market_client",
                                           "profile_cfg|profile_client"])]
    assert unclosed(bad) == [(1, "srv", "server_close"), (5, "_post", "close")]
    good = ast.parse(
        "def srv(tmp_path):\n"
        "    s = make_server(port=0, config_path=1, market_client=2, market_seed=[],\n"
        "                    profile_client=3)\n"
        "    try:\n"
        "        yield s\n"
        "    finally:\n"
        "        s.server_close()\n")
    assert missing_isolation(good) == [] and unclosed(good) == []
