# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project intends to follow [Semantic Versioning](https://semver.org/) once it has tagged releases. Commits follow [Conventional Commits](https://www.conventionalcommits.org/), so entries can be derived from them.

## [Unreleased]

The project has no tagged release yet; everything on `main` is pre-release.

### Added

- Repository standards: private vulnerability reporting policy, `CODEOWNERS`, Dependabot configuration, issue-form contact links, pull request template, this changelog, and a project README.
- Branch protection on `main` (pull request and six passing CI checks required; force pushes and deletion blocked).

### Changed

- CI workflows run with read-only tokens and use actions pinned to commit SHAs.
- The previous README (operating notes of the local runtime, 24-27 Oct 2026) moved to `docs/LOCAL_RUNTIME_HISTORY.md`.

### Planned work, tracked outside this file

- The E0-E17 execution packages are described in `docs/EXECUTION_DESIGN_20261119.md` and are being merged through pull requests.

## How to release

1. Move the entries under *Unreleased* to a new `## [x.y.z] - YYYY-MM-DD` heading.
2. Tag the merge commit `vX.Y.Z` and publish a GitHub release with the same notes.
3. Update the supported-versions table in `SECURITY.md`.
