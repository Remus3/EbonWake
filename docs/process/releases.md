# Releases and milestone tags

Ruled by MAIN's PUBREPO posture order (2026-10-15, item 1a). This file is
the process; reasoning lives in that ruling.

## Rules

1. Milestone tags only. No tag per session, per lane or per green CI run.
2. Cut by hand, annotated (`git tag -a`), semver 0.x: `v0.MINOR.PATCH`.
   MINOR = a user-visible milestone (a batch of shipped plans); PATCH = a fix
   release on top of it.
3. The tagged commit must be an ancestor of the published `origin/main`:
   `git merge-base --is-ancestor <commit> origin/main` exits 0 before tagging.
4. Push the single tag ref only: `git push origin refs/tags/v0.X.Y`.
   Never `git push --tags`, never `--mirror`. The push runs through
   `ops/fleet_kit/fleet_gitlock.py run --owner <id> -- git push ...`.
5. Release notes are hand-written from the ledger (`docs/handoff-ledger.txt`,
   ROADMAP rows shipped since the previous tag), in plain outsider language:
   no fleet vocabulary, agent worktree names, machine paths or account ids.
   `gh release create v0.X.Y --notes-file <file>`; `--generate-notes` stays
   OFF (generated notes are empty with local merges).

6. Bot PRs (Dependabot) never merge as-is: path A (operator squash, no
   `Co-authored-by:` trailer) or path B (close + operator re-apply commit),
   then read back (`tools/bot_pr_check.py`). Rule: CLAUDE.md "Bot PRs".

## Steps

    git fetch origin
    git merge-base --is-ancestor <commit> origin/main
    git tag -a v0.X.Y <commit> -m "Ebonwake v0.X.Y"
    python ops/fleet_kit/fleet_gitlock.py run --owner <id> -- git push origin refs/tags/v0.X.Y
    gh release create v0.X.Y --verify-tag --title "Ebonwake v0.X.Y" --notes-file <notes.md>

Read back: `git ls-remote --tags origin` lists the new tag and its peeled
commit is reachable from `origin/main`.

## Unreachable tags

Before the first tag, and whenever a stray tag appears, list every tag
(`git tag -l`, `git ls-remote --tags origin`) and resolve each one not
reachable from main. Before deleting any tag, record its name and sha in
this file (section below); remote deletes only by a single-ref push.

## Tag log

- 2026-10-15: inventory before the first tag - 0 local tags, 0 remote tags.
  Nothing to resolve.
