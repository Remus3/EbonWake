"""Plan 119: self-hosted BDO-REST-API checker and wirer (ADR 0008).

  python tools/profile_selfhost.py check [--json]   read-only state + verdict
  python tools/profile_selfhost.py wire [--force]   set profile.base_url to the
                                                    loopback instance

`check` makes one robots.txt GET of the official site the instance scrapes
and one TCP connect to the loopback instance (no HTTP, no profile search);
the plan 041 history file gives the feature lights. `wire` goes through plan
030's Settings.apply and refuses while the official site's robots.txt does
not allow the adventurer pages (always) or the instance is down (unless
--force). The family name is never printed. Exit 0 = wired / live, else 2.
"""

import argparse
import datetime as _dt
import json
import socket
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.ew import coupons, progress, settings  # noqa: E402

UPSTREAM = "https://www.naeu.playblackdesert.com"
UPSTREAM_ROBOTS = UPSTREAM + "/robots.txt"
UPSTREAM_URLS = (UPSTREAM + "/en-US/Adventure", UPSTREAM + "/en-US/Adventure/Profile",
                 UPSTREAM + "/en-US/Adventure/Guild/GuildProfile")
IMAGE = "man90/bdo-rest-api"
DOCKER_RUN = (f"docker run -d --restart unless-stopped --name bdo-rest-api "
              f"-p 127.0.0.1:8001:8001 {IMAGE}")
CONNECT_TIMEOUT_S = 3
LIVE_MAX_AGE_S = 24 * 3600  # an older newest refresh predates the wiring
OK_VERDICTS = ("wired", "live")
LIFE_KEYS = ("energy", "contribution", "spec_levels")

NEEDS = {
    "blocked": "keep the profile source off: the official site's robots.txt does not "
               "allow the adventurer pages",
    "no_family": "OPERATOR: set Settings > Profile > Family name",
    "needs_install": f"OPERATOR: install Docker Desktop, then {DOCKER_RUN}",
    "needs_wire": "python tools/profile_selfhost.py wire, then restart the EW server",
    "wired": "restart the EW server, then open Progress (first profile refresh)",
}


def base_state(v):
    """blank | loopback | remote (https, robots-gated) | invalid (= off)."""
    if v is None or v == "":
        return "blank"
    if progress.is_loopback_base(v):
        return "loopback"
    return "remote" if progress.base_ok(v) else "invalid"


def _probe_base(base):
    return base if base_state(base) == "loopback" else progress.SELF_HOST_EXAMPLE


def instance_up(base, connect):
    p = urllib.parse.urlsplit(base)
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        connect((p.hostname, port), CONNECT_TIMEOUT_S).close()
    except OSError:
        return False
    return True


def _age_s(at, clock):
    try:
        return clock() - _dt.datetime.fromisoformat(at).timestamp()
    except (TypeError, ValueError):
        return None


def features(family_ok, base, history, clock):
    """({"004", "041", "042": on | off | waiting | hidden}, characters, age_s)."""
    rows = history.rows()
    last = rows[-1]["at"] if rows else None
    newest = [r for r in rows if r["at"] == last]
    main = next((r for r in newest if r.get("main") is True), None)
    card = "on" if family_ok and progress.base_ok(base) else "off"
    if not newest:
        return {"004": card, "041": "waiting", "042": "waiting"}, 0, None
    life = "on" if main is not None and any(k in main for k in LIFE_KEYS) else "hidden"
    return {"004": card, "041": "on", "042": life}, len(newest), _age_s(last, clock)


def check(root, fetch, connect, clock=time.time):
    cfg = progress.config_profile(root)
    family_ok = progress.family_from_config(cfg) is not None
    base = cfg.get("base_url") if isinstance(cfg.get("base_url"), str) else ""
    robots = coupons.robots_verdict(fetch, urls=UPSTREAM_URLS, robots_url=UPSTREAM_ROBOTS)
    probe = _probe_base(base)
    up = instance_up(probe, connect)
    hist = progress.ProfileHistory(Path(root) / "ops" / "runtime" / "profile_history.jsonl",
                                   clock=clock)
    feats, chars, age = features(family_ok, base, hist, clock)
    if robots != "allow":
        verdict = "blocked"
    elif not family_ok:
        verdict = "no_family"
    elif not up:
        verdict = "needs_install"
    elif base_state(base) != "loopback":
        verdict = "needs_wire"
    elif age is None or age > LIVE_MAX_AGE_S:
        verdict = "wired"
    else:
        verdict = "live"
    return {"verdict": verdict, "upstream_robots": robots, "family": family_ok,
            "base": base_state(base), "instance": "up" if up else "down",
            "probe": probe, "features": feats, "characters": chars,
            "history_age_s": None if age is None else int(age),
            "needs": [NEEDS[verdict]] if verdict in NEEDS else []}


def wire(root, report, force=False):
    """(ok, message); writes profile.base_url only on an allowed, live setup."""
    if report["upstream_robots"] != "allow":
        return False, f"refused: upstream robots {report['upstream_robots']}"
    if not report["family"]:
        return False, "refused: " + NEEDS["no_family"]
    if report["base"] == "loopback":
        return True, "already wired to a loopback base; nothing changed"
    if report["instance"] != "up" and not force:
        return False, "refused: instance down at " + report["probe"] + " (" + \
            NEEDS["needs_install"] + "; --force wires anyway)"
    try:
        settings.Settings(Path(root) / "config" / "local.json").apply(
            {"set": {"profile.base_url": progress.SELF_HOST_EXAMPLE}})
    except ValueError as e:
        return False, f"refused: {e}"
    return True, f"wired profile.base_url = {progress.SELF_HOST_EXAMPLE}; restart the EW server"


def _connect(addr, timeout):
    return socket.create_connection(addr, timeout=timeout)


def _text(r):
    lines = [f"verdict: {r['verdict']}",
             f"upstream robots: {r['upstream_robots']}",
             f"family: {'set' if r['family'] else 'unset'}",
             f"base: {r['base']}",
             f"instance: {r['instance']} ({r['probe']})",
             "features: " + ", ".join(f"{k} {v}" for k, v in r["features"].items()),
             f"characters: {r['characters']}"]
    lines += [f"needs: {n}" for n in r["needs"]]
    return "\n".join(lines) + "\n"


def main(argv=None, root=ROOT, fetch=None, connect=None, clock=time.time, out=None):
    out = out if out is not None else sys.stdout
    ap = argparse.ArgumentParser(prog="profile_selfhost")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--json", action="store_true")
    w = sub.add_parser("wire")
    w.add_argument("--force", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    report = check(root, fetch or coupons.default_fetch, connect or _connect, clock)
    if args.cmd == "check":
        out.write(json.dumps(report, sort_keys=True) + "\n" if args.json else _text(report))
        return 0 if report["verdict"] in OK_VERDICTS else 2
    ok, msg = wire(root, report, force=args.force)
    out.write(msg + "\n")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
