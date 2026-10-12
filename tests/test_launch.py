"""Order N1af105: tools/launch.py passes --hidden through to Electron so the
logon task starts the app to the tray; the Desktop shortcut is unchanged."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import launch  # noqa: E402


def test_electron_args_default_shows_dashboard():
    assert launch.electron_args([]) == ["."]


def test_electron_args_hidden_passes_through():
    assert launch.electron_args(["--hidden"]) == [".", "--hidden"]


def test_main_hands_electron_args_to_popen(monkeypatch):
    seen = []
    monkeypatch.setattr(launch, "healthy", lambda timeout=1.0: True)
    monkeypatch.setattr(launch, "electron_exe", lambda: Path("electron.exe"))
    monkeypatch.setattr(launch.subprocess, "Popen", lambda args, **kw: seen.append(args))
    assert launch.main(["--hidden"]) == 0
    assert launch.main([]) == 0
    assert seen == [["electron.exe", ".", "--hidden"], ["electron.exe", "."]]
