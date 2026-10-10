# Plan 119 - Self-hosted BDO-REST-API for family / gear

Status: open. Lane hint: `build`. Depends on: 061 (robots gate, self-host
base), 004 (profile card), 041 (profile history), 042 (Life & CP card), 030
(settings form).

Spec gap: plan 061 turned the profile source off (the public host is
robots-disallowed) and documented a self-hosted instance as the way back on,
but nothing adjudicated the install, nothing tells the operator or a session
whether the instance is up, and nothing wires `profile.base_url` safely. The
host config still names the public host, so 004 / 041 / 042 sit at
"profile source off".

## Ruling (adjudicated first; ADR 0008)

Decision: ADOPT a self-hosted `man90/bdo-rest-api` container, published on
loopback only (`127.0.0.1:8001`, the documented default; outside EW's
8940-8959 block, so it is configured, not assigned). Installing Docker
Desktop (admin / UAC prompt, WSL 2 backend, licence accept) and starting the
container are OPERATOR physical acts, batched into one ask; everything else
(the checker, wiring the base, verifying the features) is EW's.

Robots-clean: the instance scrapes the official adventurer pages on
`www.naeu.playblackdesert.com`, whose robots.txt (read 2026-10-10, research
0020) disallows only `/MyPage/`, `/CS/QNA/`, `/InGame/`; `/en-US/Adventure`
paths are allowed. EW re-checks that policy (both `*` and the Ebonwake
agent) before it wires the base and on every `check`; a disallow or an
unreadable robots.txt blocks wiring and is reported, never overridden (not
even by `--force`). EW's own call rate stays plan 004's: one adventurer
search per hour (TTL 3600 s), so the instance scrapes at most that often for
EW. Game ToS floor: public web pages only, unauthenticated GETs, nothing
touches the client.

Alternatives: (a) keep the source off and rely on OCR (plan 066) - loses
041 history and 042 life skills, which OCR does not read; (b) build the Go
binary natively - needs a Go toolchain install, same install class, no
update path; (c) the public instance - robots `Disallow: /`, forbidden.
Why: the container is the upstream's documented deployment, loopback-only
binding keeps it off the network, and the upstream site's robots.txt allows
the pages it reads. Reverses if: the official site's robots.txt disallows
`/en-US/Adventure`, the upstream image is abandoned or changes port, or the
operator declines the Docker install.

## Build

1. `tools/profile_selfhost.py`, stdlib, read-only unless `wire`:
   - `check [--json]`: upstream robots verdict (one robots.txt GET of the
     official site); config state (family set yes/no - never spelled; base
     `blank` / `loopback` / `remote` / `invalid`); instance `up` / `down` /
     `n/a` by ONE TCP connect to the loopback base host:port (no HTTP, no
     profile GET); feature lights from the plan 041 history file: 004 card
     (family + usable base), 041 history (rows in the newest refresh), 042
     Life & CP (main snapshot carries energy / contribution / spec levels).
     Verdict, in order: `blocked` (upstream robots not allow), `no_family`,
     `needs_install` (instance down), `needs_wire` (base not the loopback
     instance), `wired` (no history row yet - restart the EW server, then
     the first GET refreshes), `live` (history rows present). `needs` lists
     the acts, OPERATOR ones prefixed `OPERATOR:`.
   - `wire [--force]`: sets `profile.base_url` to the loopback example
     through plan 030's `Settings.apply` (validated, comment-preserving,
     atomic). Refuses on upstream robots not allow (always), and on
     instance down unless `--force`. Already loopback = no-op. Prints the
     restart reminder (`profile.base_url` is a restart key).
   - Exit codes: 0 `live` / `wired`, 2 otherwise (so a loop step can gate on
     it).
2. `config/local.example.json` profile `_doc` names the checker and the
   loopback-only `docker run` line.
3. Tests `tests/test_profile_selfhost.py`, no network, no socket (fakes for
   fetch and connect): each verdict; robots disallow blocks `wire` even with
   `--force`; instance down blocks `wire` without `--force`; wire writes the
   loopback base and keeps every other key; second wire is a no-op; family
   never appears in output; feature lights from a fixture history; the
   checker makes zero non-robots HTTP calls.

## Operator ask (batched, one line)

OPERATOR: install Docker Desktop, then
`docker run -d --restart unless-stopped --name bdo-rest-api -p 127.0.0.1:8001:8001 man90/bdo-rest-api`;
the next session runs `python tools/profile_selfhost.py wire` and restarts
the EW server.

Acceptance: `check` reports the true state on this host; with the instance
up, `wire` sets the base and a restart lights 004 / 041 / 042 (verdict
`live`); with it down, nothing is wired and the verdict names the operator
act; gates green; verifier PASS within 3 rounds.

ToS check: unauthenticated GETs of public pages, robots.txt honoured at both
hops; no game input, no memory read, no client file.

## As-built deviations

Self-adjudicated by the build lane (2026-10-10); refute-rounds: 0/3 at hand-in.

1. Live verification on this host is deferred: Docker is not installed and
   the lane runs headless (the install needs a UAC prompt), so `wire` was
   not run against the host config and 004 / 041 / 042 were verified with
   fixtures only. Alternatives: wire the base now with `--force` - the
   loopback client would fail three times and back off 24 h, turning the
   expected "off" into an error card. Why: wiring a dead base trades an
   honest muted line for a red error. Reverses if: the operator ask lands;
   the next session runs `check` / `wire`.
2. The lane does not edit per-host `config/local.json` (plan 061 deviation
   8 precedent); `wire` is the tool a session runs on the host.
3. Instance probe is a TCP connect, not an HTTP GET: the upstream API has no
   documented health route, and a search GET would scrape the official site
   for a probe. Reverses if: upstream documents a cheap health route.
