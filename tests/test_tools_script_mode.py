"""Plan 172: every tools/*.py entry point runs as a script without an import
crash (row 171: `python tools/lane_samples.py status` died on a circular
import that only exists when the file is __main__; module-importing tests
never see that class of defect).

Each case runs in a subprocess against a copy of tools/, server/ and
ops/fleet_kit/ under tmp_path, so no tool reads or writes the live tree.
Two checks per entry point:
1. script-mode import: the file's top level runs as __main__ (the code
   before its `if __name__ == "__main__":` guard), so the exact import order
   of a script run is exercised with no side effect at all;
2. `--help` (or the documented read-only status verb) runs for real and
   exits 0 or the tool's documented usage rc, with no Traceback.
NO_HELP names the tools whose argv path acts even on --help (git config,
process launch, network, live-state read); they get check 1 only."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
MAIN_GUARD = re.compile(r"^if __name__ == ['\"]__main__['\"]:", re.M)
COPY = ("tools", "server", "ops/fleet_kit")
TIMEOUT_S = 60

# tool -> (argv, accepted return codes). Default: (["--help"], {0}).
HELP = {
    "eta.py": (["--help"], {64}),  # prints its doc, usage rc 64
    "loop_task.py": (["--help"], {2}),  # usage line, rc 2
    "logon_task.py": (["--help"], {2}),
    "profile_selfhost.py": (["--help"], {2}),  # prints help, usage rc 2
    "lane_samples.py": (["status"], {0}),  # row 171 acceptance: one status line
}
# --help is not parsed by these: running them acts (reason per entry).
NO_HELP = {
    "install_hooks.py": "runs git config core.hooksPath",
    "launch.py": "starts the server and Electron",
    "verify_action_pins.py": "git ls-remote over the network",
    "ew_facts.py": "reads live lane and server state",
}

BOOT = """
import os
import sys
path = sys.argv[1]
sys.argv = sys.argv[1:]
sys.path[0] = os.path.dirname(path)
src = open(path, encoding='utf-8').read()
cut = MARK.search(src)
g = sys.modules['__main__'].__dict__
g['__file__'] = path
exec(compile(src[:cut.start()], path, 'exec'), g)
print('script-mode-import-ok')
"""


def entry_points():
    return sorted(p.name for p in TOOLS.glob("*.py")
                  if MAIN_GUARD.search(p.read_text(encoding="utf-8")))


ENTRY = entry_points()


@pytest.fixture(scope="module")
def tree(tmp_path_factory):
    root = tmp_path_factory.mktemp("p172tree")
    for rel in COPY:
        shutil.copytree(REPO / rel, root / rel,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return root


def _run(argv, cwd):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONIOENCODING"] = "utf-8"
    env["FLEET_SIDECAR_ROOT"] = ""
    return subprocess.run([sys.executable, *argv], cwd=str(cwd), env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=TIMEOUT_S)


def test_entry_points_found():
    assert len(ENTRY) >= 10
    assert "lane_samples.py" in ENTRY
    for name in [*HELP, *NO_HELP]:
        assert name in ENTRY, f"stale table entry {name}"


@pytest.mark.parametrize("name", ENTRY)
def test_script_mode_import(tree, name):
    boot = "import re\nMARK = re.compile(%r, re.M)\n%s" % (MAIN_GUARD.pattern, BOOT)
    r = _run(["-c", boot, str(tree / "tools" / name)], tree)
    assert "Traceback" not in r.stderr, r.stderr
    assert r.returncode == 0, r.stderr
    assert "script-mode-import-ok" in r.stdout


@pytest.mark.parametrize("name", [n for n in ENTRY if n not in NO_HELP])
def test_script_help_or_status(tree, name):
    argv, ok_rc = HELP.get(name, (["--help"], {0}))
    r = _run([str(tree / "tools" / name), *argv], tree)
    assert "Traceback" not in r.stderr, r.stderr
    assert "ImportError" not in r.stderr, r.stderr
    assert r.returncode in ok_rc, (r.returncode, r.stdout, r.stderr)
    assert (r.stdout + r.stderr).strip(), "no usage or status text"


def test_lane_samples_status_one_line(tree):
    r = _run([str(tree / "tools" / "lane_samples.py"), "status"], tree)
    assert r.returncode == 0, r.stderr
    assert len(r.stdout.strip().splitlines()) == 1, r.stdout
