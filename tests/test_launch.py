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


class _Popen:
    def __init__(self):
        self.calls = []

    def __call__(self, args, **kw):
        self.calls.append((args, kw))


def _fakes(monkeypatch, health):
    """health: successive healthy() answers (the last one repeats)."""
    answers = list(health)
    pop, sleeps = _Popen(), []
    monkeypatch.setattr(launch, "healthy",
                        lambda timeout=1.0: answers.pop(0) if len(answers) > 1 else answers[0])
    monkeypatch.setattr(launch, "electron_exe", lambda: Path("electron.exe"))
    monkeypatch.setattr(launch, "pythonw", lambda: "pythonw.exe")
    monkeypatch.setattr(launch.subprocess, "Popen", pop)
    monkeypatch.setattr(launch.time, "sleep", sleeps.append)
    return pop, sleeps


def test_unhealthy_server_is_spawned_hidden_then_polled(monkeypatch):
    """Plan 156, TESTS-A-26: the spawn-and-poll branch and the Popen kwargs."""
    pop, sleeps = _fakes(monkeypatch, [False, False, False, True])
    assert launch.main([]) == 0
    (srv_args, srv_kw), (app_args, app_kw) = pop.calls
    assert srv_args == ["pythonw.exe", "-m", "server.ew"]
    assert srv_kw == {"cwd": str(launch.ROOT), "creationflags": launch.FLAGS, "close_fds": True}
    assert sleeps == [0.25, 0.25]  # two failed polls, the third sees it healthy
    assert app_args == ["electron.exe", "."]
    assert app_kw["cwd"] == str(launch.ROOT / "app") and app_kw["close_fds"] is True
    assert app_kw["creationflags"] == launch.FLAGS
    assert app_kw["env"]["EW_PYTHONW"] == "pythonw.exe"


def test_server_only_starts_no_electron_and_reports_health(monkeypatch):
    pop, _ = _fakes(monkeypatch, [True])
    assert launch.main(["--server-only"]) == 0 and pop.calls == []  # reused, nothing spawned
    pop, sleeps = _fakes(monkeypatch, [False])
    assert launch.main(["--server-only"]) == 1
    assert [a for a, _ in pop.calls] == [["pythonw.exe", "-m", "server.ew"]]
    assert len(sleeps) == 40  # the poll gives up after 40 tries, never hangs
