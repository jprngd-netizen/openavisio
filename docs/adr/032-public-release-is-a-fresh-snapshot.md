# ADR 032 — The public release is a fresh snapshot, not this history

**Status:** accepted (2026-07-14)

## Context

OpenAvisio is AGPL-3.0 and will be published. The obvious route — flip the
existing repository to public — turned out to be a trap.

The history contains things that must never be public: a committed private key
(`docs/dev-license-private.pem`, #116), funding applications, a roadmap with
budget, personal outreach letters, internal host addresses. Removing them from
the *working tree* changes nothing: `git rm` adds a commit, it does not erase.

The remedy would be a history rewrite (`git filter-repo`), a force-push, and
temporarily disabling the branch protection and the mirror. That is a lot of
sharp edges around the one thing you cannot undo — and even then, a Forgejo or
Codeberg instance keeps unreachable objects around for a while, so old commits
stay fetchable by hash until garbage collection runs.

## Decision

**The public repository is a fresh snapshot, created at release, with no prior
history.**

- **Forgejo (private)** stays canonical: full history, issues, PRs, CI. This is
  where the work happens, mistakes included.
- **Codeberg (private)** stays a push mirror. It is no longer a shop window —
  it is a free off-site copy of the repository, which is worth having on its own.
- **At release**, a new *public* repository is created from the current tree:
  one commit, AGPL-3.0, no business documents, no keys, no internal addresses.
  Each subsequent release publishes a new snapshot.

## Why this is enough

The AGPL requires that users of the service receive the **source code**. It says
nothing about development history. A clean snapshot satisfies the licence in
full.

What we give up is a public commit history. For a solo project that is not a
real loss: there are no outside contributions to look back on, and the `#113`
style references in our commit messages point at a private tracker anyway — in
public they would only confuse.

## What this rules out

Do **not** flip the private repository to public, ever, and do not "just push it
somewhere quickly". The history is not fit for that and never will be. If a
public repository is needed, it is built from a snapshot — see the release
checklist in `docs/business.md` (private) and #116.
