<p align="center">
  <img src="docs/assets/social-preview.png" width="100%" alt="Ebonwake banner: a faceted teal gem above a wake, the project name and the tagline - Black Desert Online companion, dashboard and click-through overlay, never reads memory or sends game input">
</p>

# Ebonwake

**A Black Desert Online companion that never touches the game.**

[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](.github/workflows/ci.yml)
[![Node 20+](https://img.shields.io/badge/node-20%2B-green)](app/package.json)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey)](#requirements)

Ebonwake is a compact tabbed dashboard plus a transparent, click-through
overlay for one Black Desert Online player. A small local server on
`127.0.0.1` feeds both. It tracks market prices, daily and weekly resets,
grind sessions, events and gear plans. It runs beside the game, not inside
it: no memory reading, no injection, no input automation - ever.

![Ebonwake dashboard, Market tab: a watchlist row, item detail, add/edit form and a hot list of Central Market prices](docs/assets/dashboard-market.png)

<sub>Dashboard, Market tab. Captured by the app's own desktop self-test
(`EW_SELFTEST`), which drives only Ebonwake's windows - not the game.</sub>

## Contents

- [What it never does](#what-it-never-does)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Privacy](#privacy)
- [Architecture and layout](#architecture-and-layout)
- [Development and tests](#development-and-tests)
- [Contributing](#contributing)
- [License and disclaimer](#license-and-disclaimer)

## What it never does

Black Desert's anti-cheat (XIGNCODE3 on NA/EU) and its operational policy ban
unauthorized programs and every macro. Ebonwake's boundary is fixed. It is
not a setting:

- **No memory reading or writing** of the game process.
- **No injection** - no DLLs, no D3D/DXGI hooks, nothing loaded into the
  client.
- **No input automation** - no synthetic keys or clicks to the game window, no
  macros, no AFK helpers, no screen-reading that leads to input.
- **No packet access** and **no client file changes**.
- **No authenticated market actions** - market calls are read-only `GET`s.

What it reads: the public arsha.io v2 market API, an optional self-hosted
BDO-REST-API instance for the profile card (the public instance disallows bots
in its robots.txt and is never called), a tail of the client's own session log
(running / logged in / disconnected only), screenshots **you** take (OCR), and
what you type.

The overlay is a separate always-on-top Electron window with
`setIgnoreMouseEvents(true)`, toggled by Electron's `globalShortcut`. No
low-level keyboard hooks. Run the game borderless or windowed. Long form:
[`docs/research/0001-bdo-data-and-tos.md`](docs/research/0001-bdo-data-and-tos.md).

## Quick start

```
git clone <https URL from this page's Code button> Ebonwake
cd Ebonwake
python -m server.ew                # local server on 127.0.0.1:8940
```

In a second terminal:

```
npm ci --prefix app                # once: installs Electron
npm start --prefix app             # dashboard + overlay
```

There is no packaged release; run from a clone. To start Ebonwake at
Windows logon: `python tools/logon_task.py install` (`remove` undoes it).

### Requirements

- **Windows** (the game and its paths are Windows-only)
- **Python 3.11+**, standard library only for the server and tools
- **Node 20+** for the Electron app
- Optional: Tesseract for screenshot OCR (Windows OCR is the fallback)

## Usage

| Tab | What it does |
|---|---|
| **Home** | What to do now: active timers, today's progress, the session summary and a first-run checklist |
| **Today** | Daily and weekly checklist with NA reset countdowns, login events, dice |
| **Market** | Central Market prices, history, order book and alert thresholds from the public arsha.io API - read-only, cached, with backoff |
| **Progress** | Main-story, season-pass and gear tracks; optional profile card from a self-hosted BDO-REST-API |
| **Grind** | Grind session log, silver per hour, buff timers |
| **Events** | Coupon, event and Twitch-drop tracker with expiries |
| **Deadeye** | Build notes and an enhancement plan |
| **System** | Server health, game state (not running / running / logged in) from the client's session log, screenshot OCR |
| **Settings** | Hotkeys, game folders, market tax bonuses and the other per-host values, written to `config/local.json` |

The **overlay** shows the reset clocks, today's checklist count, the grind
session, the active buff and whatever ends soonest. `Ctrl+Alt+E` toggles it;
`Ctrl+Alt+D` brings the dashboard back. Both keys are configurable.

<p>
  <img src="docs/assets/dashboard-today.png" width="64%" alt="Ebonwake dashboard, Today tab: daily and weekly checklists with reset countdowns">
  <img src="docs/assets/overlay.png" width="30%" alt="Ebonwake overlay card: game state, daily and weekly reset, checklist count, grind, buff, ending soon, server">
</p>

Per-host settings (hotkeys, game folders, market tax bonuses, optional profile
family name and self-hosted profile API, OCR engine) live in
`config/local.json`. Copy it from
[`config/local.example.json`](config/local.example.json) or edit it from the
Settings tab. It is gitignored.

## Privacy

- **No telemetry, no accounts, no analytics.** Nothing leaves the machine
  except the public read-only API calls above.
- The server binds `127.0.0.1` only.
- Checklists, notes, grind logs and screenshot results stay in the local,
  gitignored `ops/runtime/` directory.
- The profile card is off by default. When on, it sends only the family name
  you configure, and only to the self-hosted BDO-REST-API instance you set as
  `profile.base_url` (run it on loopback). The public instance is never
  called.
- API keys, if you add any, live in user environment variables and are
  referenced - never stored - from `config/local.json`.

## Architecture and layout

```
server/ew/   Python stdlib server: API, dashboard assets, overlay SSE
app/         Electron: dashboard window + transparent click-through overlay
tools/       work loop, lane driver, ETA log, leak sweep, hook installer
ops/         vendored fleet kit (do not edit), runtime state (gitignored)
docs/        spec, plans, research, ADRs
ci/          hash-pinned CI and dev requirements
```

The spec is [`docs/design/0001-ebonwake-spec.md`](docs/design/0001-ebonwake-spec.md);
decisions are in [`docs/adr/`](docs/adr/); open work is in
[`docs/plans/ROADMAP.md`](docs/plans/ROADMAP.md).

Ebonwake is written with AI-assisted tooling (Claude Code agent sessions)
under the direction of one human operator, who sets the goals, reviews the
results and owns every commit. Some files exist for that process, not for
runtime:

- [`CLAUDE.md`](CLAUDE.md) - standing rules for every agent session: the
  game-safety floor, spec first, failing test first, an independent verifier
  before any done-claim, ASCII + LF, no secrets in tracked files.
- [`.claude/`](.claude/) - agent definitions (for example the verifier and
  the adjudicator), slash commands and hook settings.
- [`ops/`](ops/) - `ops/fleet_kit/` is a vendored, version-pinned helper kit
  (git locking, test-suite gating, commit identity checks), never edited
  here. `ops/loop/` holds the scheduled work loop's control files; the loop
  itself is `tools/ew_loop.py`.
- [`.githooks/`](.githooks/) - pre-commit and pre-push hooks run a leak sweep
  (machine paths, account ids, emails, secret shapes); the commit-msg hook
  strips AI or bot attribution trailers.
- [`EW-NEXT-SESSION.txt`](EW-NEXT-SESSION.txt) - the hand-off between
  sessions.

## Development and tests

```
python tools/install_hooks.py                                  # once: git hooks
python -m pip install --require-hashes -r ci/requirements-ci.txt  # pytest, ruff
python -m ruff check server tools tests
python -m pytest -q
npm test --prefix app
```

The JavaScript tests run under `node --test`; no Electron is needed. CI
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs ruff, pytest on
Python 3.11 and 3.14, the node tests and a leak sweep on every pull request
and on each push to `main` that changes code. CodeQL runs alongside.

Commit subjects follow
[Conventional Commits](https://www.conventionalcommits.org/) (for example
`feat(plan-132): ...`, `fix(...)`, `merge: <topic>`).

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) first. The game-safety boundary is
stricter than usual and every pull request is measured against it. Also see
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) and [`SECURITY.md`](SECURITY.md)
(private vulnerability reporting; cheats and anti-cheat bypasses are out of
scope).

## License and disclaimer

Apache License 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). AI
assistance does not change the licence or its warranty disclaimer.

**Ebonwake is an unofficial fan project. It is not affiliated with, endorsed
by, or connected to Pearl Abyss.** Black Desert and Black Desert Online are
trademarks of Pearl Abyss Corp.; all other trademarks belong to their
respective owners.

**No game assets or game data are redistributed.** Market data is fetched at
run time from public APIs; everything else is this project's own code or what
you enter yourself.
