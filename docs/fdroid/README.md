# F-Droid submission

Getting `org.openavisio.app` onto the official f-droid.org repository as a beta.

## What's ready

- `versionName` is `0.1.0-beta` (`mobile/android/app/build.gradle`) — the beta
  is marked by the version string, no separate channel.
- fastlane metadata (title, summary, description, changelog) in
  `mobile/android/app/fastlane/metadata/android/{en-US,de-DE}/` — F-Droid only scans
  `fastlane/`, `<subdir>/fastlane/`, or `src/<flavor>/fastlane/`, so it lives
  under the `mobile/android` subdir, not `mobile/`.
- A draft build recipe in `org.openavisio.app.yml` (this directory).

## How submission works

- F-Droid **builds and signs** the app itself, from source, with its own key.
  So Android release signing (#59) is **not** a prerequisite for being on
  F-Droid. (Reproducible builds, which would let our own signature match, are
  optional best-practice — a later step.)
- Submit by opening a merge request against
  <https://gitlab.com/fdroid/fdroiddata> adding `metadata/org.openavisio.app.yml`
  (copy from the draft here), or file a Request-For-Packaging issue at
  <https://gitlab.com/fdroid/rfp>. The MR is the faster route.
- Once merged, the app appears in the repo within ~24–48h, barring build errors.

## Blockers

1. ~~The public snapshot must be tagged.~~ **Done** — `make-public-snapshot.sh`
   now accumulates one annotated-tagged commit per release (ADR 032, amended).
2. ~~Validate the build recipe.~~ **Done (2026-07-19)** — the exact recipe in the
   yml builds an unsigned release APK from a clean tree (JDK 21 + SDK 36). The
   `subdir`/`prebuild` reflect the validated sequence; `fdroid build` may still
   want minor tweaks, but the build itself is proven.
3. **Public issue tracker.** The `IssueTracker` must point at a public tracker
   for the fork's repository. Point it at the public GitHub repo's issues (or
   enable issues on whatever public mirror is used). (Minor — F-Droid does not
   require it.)

## Before touching the recipe: lint it locally

`fdroidserver` is installed (`pipx install fdroidserver`). Run these in a throwaway
dir with `metadata/org.openavisio.app.yml` + `config/categories.yml` (copied from
fdroiddata) before submitting — they catch what the reviewer otherwise catches:

```
fdroid lint org.openavisio.app        # 0 warnings required (CONTRIBUTING.md)
fdroid rewritemeta org.openavisio.app # must produce no diff (canonical format)
```

This is how the review round-trips stop. Reviewer-enforced rules are in the
recipe's header comments (full commit hash, subdir = app module, prebuild as a
list, valid category, no Name/Summary/Description).

## Status: build proven, packaging not yet submitted

The recipe has been verified against F-Droid's buildserver: it built and
produced the app from source in a clean F-Droid environment. A merge request
against `fdroid/fdroiddata` still has to be opened from this fork (once the
public repository URL is in place); after merge the app publishes within
~24–48h. Recipe validated from tag `v0.1.0-beta2`.

The build works around several F-Droid-environment realities (all in the recipe,
see the header comments in `org.openavisio.app.yml`):

1. **Node from Debian** — the buildserver is Debian trixie (Node 20, no sid), and
   NodeSource is discouraged. The app is pinned to **Capacitor 7** (CLI needs only
   Node ≥ 20) so `apt-get install nodejs npm` is enough — see **ADR 035**.
2. **pnpm 9.15.9** — Node 20's corepack can't load pnpm 11 (ESM); pinned via `npm -g`.
3. **`output:`** — multi-module gradle puts the APK in `app/build/outputs`, not the root.
4. **`scandelete`** — the Capacitor CLI ships `.tar.gz` template blobs the scanner rejects.

Plus canonical field order (`gradle` before `prebuild`) for `fdroid rewritemeta`,
and fastlane at `mobile/android/app/fastlane/` (the `<subdir>/fastlane` path).
