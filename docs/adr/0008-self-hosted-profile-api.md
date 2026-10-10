# ADR 0008 - Self-hosted BDO-REST-API on loopback

Status: accepted 2026-10-10 (self-adjudicated, plan 119).

Decision: the profile source (plans 004 / 041 / 042) runs against a
self-hosted `man90/bdo-rest-api` container published on `127.0.0.1:8001`
only. Docker Desktop install and the container start are operator acts;
EW checks and wires the base with `tools/profile_selfhost.py`. EW wires
only while the official site's robots.txt allows the adventurer pages the
instance reads, and keeps its own rate at one search per hour.

Alternatives: keep the source off and rely on OCR (plan 066); a native Go
build; the public instance (robots `Disallow: /`, forbidden).

Why: upstream's documented deployment, network-isolated by the loopback
binding, robots-clean at both hops; OCR cannot supply 041 history or 042
life skills.

Reverses if: the official site's robots.txt disallows `/en-US/Adventure`,
the upstream image is abandoned or changes port, or the operator declines
the install.
