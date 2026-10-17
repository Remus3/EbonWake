"""Plan 082 ToS floor: portraits.py only ever READS FaceTexture.

AST scan (research 0011 s3): no write-mode open(), no os-level remove /
rename / replace / utime / chmod / unlink, path-mutating methods only inside
the two archive helpers, and no reference to the per-character UI cache,
Customization or the game folder. A runtime check confirms a scan leaves the
FaceTexture bytes and timestamps untouched.
"""

import ast
import os
from pathlib import Path

from server.ew import portraits
from server.ew.store import Store

SRC = Path(portraits.__file__)
TREE = ast.parse(SRC.read_text(encoding="utf-8"))
MUTATORS = {"write_bytes", "write_text", "unlink", "replace", "rename", "touch", "chmod",
            "rmdir", "utime", "remove", "truncate"}
ARCHIVE_HELPERS = {"_write_archive", "_drop_archive"}


def _funcs():
    for node in ast.walk(TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def write_opens(tree):
    """Lines of open() calls that are not an explicit read-only mode."""
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name) and f.id == "open":
            pos = node.args[1:2]  # open(path, mode)
        elif isinstance(f, ast.Attribute) and f.attr in ("open", "fdopen"):
            # os.open / os.fdopen take flags or a descriptor: never a plain read
            if isinstance(f.value, ast.Name) and f.value.id == "os":
                bad.append(node.lineno)
                continue
            # io.open(path, mode); Path.open(mode)
            io_open = isinstance(f.value, ast.Name) and f.value.id == "io"
            pos = node.args[1:2] if io_open else node.args[:1]
        else:
            continue
        modes = list(pos) + [k.value for k in node.keywords if k.arg == "mode"]
        if not modes or any(not (isinstance(m, ast.Constant) and isinstance(m.value, str))
                            or set(m.value) & set("wax+") for m in modes):
            bad.append(node.lineno)
    return bad


def test_no_write_mode_open():
    assert write_opens(TREE) == []


def test_write_open_scan_sees_every_open_form():
    """TESTS-B-04 (plan 151): Path.open / io.open / os.open slipped past the scan."""
    src = ("open(p, 'rb')\n"            # 1 ok
           "open(p)\n"                  # 2 no explicit mode
           "open(p, 'wb')\n"            # 3
           "p.open('wb')\n"             # 4 Path.open
           "p.open(mode='a')\n"         # 5
           "io.open(p, 'w')\n"          # 6
           "os.open(p, os.O_RDWR)\n"    # 7 flags, never a read-only mode string
           "p.open('rb')\n")            # 8 ok
    assert write_opens(ast.parse(src)) == [2, 3, 4, 5, 6, 7]


def test_no_os_level_mutation():
    for node in ast.walk(TREE):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id in ("os", "shutil"):
            assert node.attr not in MUTATORS | {"rmtree", "move", "copy", "copyfile",
                                                "makedirs", "mkdir"}, \
                f"{node.value.id}.{node.attr} at line {node.lineno}"


def test_path_mutators_only_in_archive_helpers():
    allowed = set()
    for fn in _funcs():
        if fn.name in ARCHIVE_HELPERS:
            allowed |= {id(n) for n in ast.walk(fn)}
    for node in ast.walk(TREE):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in MUTATORS:
            assert id(node) in allowed, f".{node.func.attr}() outside archive helpers, line {node.lineno}"


def test_archive_helpers_only_called_with_archive_dir():
    for node in ast.walk(TREE):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ARCHIVE_HELPERS:
            text = ast.unparse(node.args[0])
            assert "archive_dir" in text and "face" not in text.lower(), text


def test_no_cache_customization_or_game_folder_reference():
    text = SRC.read_text(encoding="utf-8")
    for word in ("UserCache", "Customization", "install", "gameVariable", "BlackDesert64"):
        assert word.lower() not in text.lower(), word


def test_scan_leaves_facetexture_untouched(tmp_path):
    from ew_testkit import bmp

    face = tmp_path / "docs" / "FaceTexture"
    face.mkdir(parents=True)
    p = face / "12345678901234567.bmp"
    data = bmp(8, 8)
    p.write_bytes(data)
    os.utime(p, (1_700_000_000, 1_700_000_000))
    before = (p.stat().st_mtime_ns, p.stat().st_size, sorted(os.listdir(face)))
    svc = portraits.PortraitService(Store(tmp_path / "s"), tmp_path / "arch",
                                    documents=lambda: tmp_path / "docs",
                                    loads=lambda: [{"char_no": "12345678901234567", "at": "x"}],
                                    progress_cls=lambda: "Deadeye")
    svc.poll("logged_in", 0)
    svc.scan()
    assert svc.current("Deadeye") is not None
    assert p.read_bytes() == data
    assert (p.stat().st_mtime_ns, p.stat().st_size, sorted(os.listdir(face))) == before
