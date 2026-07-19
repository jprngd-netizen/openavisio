# F-Droid submission

Getting `org.openavisio.app` onto the official f-droid.org repository as a beta.

## What's ready

- `versionName` is `0.1.0-beta` (`mobile/android/app/build.gradle`) — the beta
  is marked by the version string, no separate channel.
- fastlane metadata (title, summary, description, changelog) in
  `mobile/fastlane/metadata/android/{en-US,de-DE}/` — F-Droid reads these from
  the source tree.
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

## Remaining steps to actually submit

1. Cut a public beta release: tag it, run `scripts/make-public-snapshot.sh <tag>`
   so the tag lands on Codeberg, and set that tag as `commit:` in the yml.
2. Open the merge request against `fdroiddata` with the yml.
