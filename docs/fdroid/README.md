# F-Droid submission

Getting `org.openavisio.app` onto the official f-droid.org repository as a beta.

## What's ready

- `versionName` is `0.1.0-beta` (`mobile/android/app/build.gradle`) — the beta
  is marked by the version string, no separate channel.
- fastlane metadata (title, summary, description, changelog) in
  `mobile/android/fastlane/metadata/android/{en-US,de-DE}/` — F-Droid only scans
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
3. **Public issue tracker.** The `IssueTracker` points at Codeberg, but issues
   live on the private Forgejo. Either enable issues on the public mirror or
   point somewhere public. (Minor — F-Droid does not require it.)

## Status: submitted, build green

MR **fdroid/fdroiddata!43322** is open with a **green pipeline** — F-Droid's own
buildserver built and verified the app from source. Awaiting maintainer review;
~24–48h after merge it publishes.

Getting the build green surfaced four F-Droid-environment differences (all fixed
in the recipe, see the header comments in `org.openavisio.app.yml`):

1. **Node 22** — the VM ships Node 20 but `@capacitor/cli` 8 needs ≥22 (NodeSource).
2. **pnpm 9.15.9** — Node 20's corepack can't load pnpm 11 (ESM); pinned via `npm -g`.
3. **`output:`** — multi-module gradle puts the APK in `app/build/outputs`, not the root.
4. **`scandelete`** — the Capacitor CLI ships `.tar.gz` template blobs the scanner rejects.

Plus canonical field order (`gradle` before `prebuild`) for `fdroid rewritemeta`.
