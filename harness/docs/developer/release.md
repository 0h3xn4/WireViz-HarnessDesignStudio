# Cut a release of the tool

This page walks through releasing a new version of Harness Design Studio in plain words; the exact checklist, step by step, is [`../RELEASE.md`](../RELEASE.md).

**Two things are called "release" here.** A *product release* is a new version of the tool (this page). A *harness release* is what a user does inside a project to lock a harness; that is in the [user manual](../user-manual/release-a-harness.md). Do not mix them up.

## Contents

- [Who does what](#who-does-what)
- [Before you start](#before-you-start)
- [1. Prepare the version](#1-prepare-the-version)
- [2. Run the automatic checks](#2-run-the-automatic-checks)
- [3. The steps only a person can do](#3-the-steps-only-a-person-can-do)
- [4. After the release](#4-after-the-release)
- [If a check fails](#if-a-check-fails)

## Who does what

| Part | Who | Where it is described |
| --- | --- | --- |
| Steps 1 to 11 (with 7a, 8a and 11a): version, lint, verifiers, performance, fuzzing, soak, tests, SBOM, vulnerability scan, reproducible build, packages, checksums | The release check program, run by a developer | `python -m tools.release_check` |
| Steps 12 to 14: a test on a clean machine, usability sessions, the owner's sign-off | People. The owner waived 12 and 13 for 0.1.0 (T-30, T-27) and waived the condition of 14 (T-31). | [`../RELEASE.md`](../RELEASE.md), [`../../compliance/DEVIATIONS.md`](../../compliance/DEVIATIONS.md) |
| Step 15: tag the merge commit | A person | [`../RELEASE.md`](../RELEASE.md) step 15 |
| Building the packages and publishing the release page | The workflow `.github/workflows/release.yml`, started by pushing the tag | [`../RELEASE.md`](../RELEASE.md) step 15 |

Pushing the tag `vX.Y.Z` (or publishing a release that creates the tag on GitHub) starts `.github/workflows/release.yml`. It checks that the tag matches the version and the changelog, builds the `.tar.gz` and the `.deb`, runs the packaged self-test, writes `SHA256SUMS` and creates the GitHub release page with the three files attached (with `workflow_dispatch` and the tag name you can run it again; it then replaces the files). The tag is still a person's step.

"Step 14" means the owner's sign-off. "14 steps" in the evidence reports means the number of automatic checks. They are not the same.

## Before you start

- You need Ubuntu 24.04 (the only supported system, [D-127](../DECISIONS.md)), the development environment from [`setup-and-tests.md`](setup-and-tests.md), and network access for the SBOM and the vulnerability scan (or a wheelhouse made with `python -m tools.vendor`).
- Every change since the last release is in `harness/CHANGELOG.md` under `## Unreleased`.
- The pull request with the changes is merged, or you are working on the branch that will be.

## 1. Prepare the version

1. Choose the new number (semantic versioning). Change it in `pyproject.toml` and `src/harness_design_studio/__init__.py`.
2. In `CHANGELOG.md`, rename the `## Unreleased` heading to the new version and date, say there what changed and what is still open, and put a fresh empty `## Unreleased` above it. The release check compares the changelog with the version, skips the *Unreleased* section and fails while it has text.
3. Check the documents that quote the version or the release state: the root [`README.md`](../../../README.md), [`../../README.md`](../../README.md) (status section), [`../../compliance/SIGNOFF.md`](../../compliance/SIGNOFF.md), [`../OPEN_DECISIONS.md`](../OPEN_DECISIONS.md). A release candidate carries `rcN` in its version until the owner signs off (D-113).

**Why this matters for the documents:** until you do this, `master` prints the version of the last release. Pages that describe something that is only under `## Unreleased` should say so; remove those notes when the new version ships. The tool version is part of every project's model hash, so the quoted hashes in the documents change with the version (the tests tell you which).

## 2. Run the automatic checks

From `harness/`:

```
python -m tools.release_check
```

It runs steps 1 to 11 in order and writes `dist/release-docs/release-report.md`. A quicker run for a change in progress:

```
python -m tools.release_check --quick
```

The quick run does only steps 1 to 3 (versions, lint and types, the verifiers). It skips the rest, writes `release-report-quick.md` and says it is not a release check.

The full run builds the installer and the `.deb`, so it takes a long time and needs the Qt libraries (see [`../INSTALL.md`](../INSTALL.md)). With Docker, use the build container in `packaging/ubuntu/container/`.

Read `release-report.md`. It lists each step with its result and keeps the numbers (tests passed, packages scanned). Those numbers belong in the report, not in other documents.

## 3. The steps only a person can do

1. Run the packaged self-test on a clean Ubuntu 24.04 machine with the network switched off (step 12; waived for 0.1.0).
2. Hold usability sessions if the owner wants them (step 13; waived for 0.1.0).
3. The owner signs off (step 14). Record the sign-off in [`../../compliance/SIGNOFF.md`](../../compliance/SIGNOFF.md) in the owner's words, and record any waiver in [`../../compliance/DEVIATIONS.md`](../../compliance/DEVIATIONS.md). A waiver accepts that a requirement is not met; it does not meet it.
4. After the pull request is merged and CI is green on the merge commit (step 15): create the annotated tag `vX.Y.Z` on the merge commit and push it. That starts the release workflow, which builds the packages and publishes the release page. If you cannot push a tag from where you work (HTTP 403 on tag pushes), use the release page instead: GitHub > Releases > Draft a new release > *Choose a tag*: type `vX.Y.Z` and select *Create new tag on publish* > target `master` > Publish. The tag push starts `release.yml`, which fills in the files and notes (version 1.0.0 was published this way; the tag is then a plain tag without a message). When it has finished, open the release page, check that the `.tar.gz`, the `.deb` and `SHA256SUMS` are attached and compare the checksums with the ones recorded in `compliance/evidence/` (a build on another machine can differ in bytes; the release notes say so).

## 4. After the release

- Copy the release report, the checksum list and the vulnerability report into `compliance/evidence/` as `release_X.Y.Z_report.md`, `release_X.Y.Z_SHA256SUMS` and `release_X.Y.Z_vulnerability_report.txt`, as for earlier releases.
- Keep the empty `## Unreleased` section at the top of `CHANGELOG.md` for the next changes.
- Check that the install page ([`../INSTALL.md`](../INSTALL.md)) still names the right place to get the packages.

## If a check fails

Fix the cause and run the check again. Never skip or disable a test to pass a release. [`setup-and-tests.md`](setup-and-tests.md) lists what to do when a test fails, and [`../RELEASE.md`](../RELEASE.md) says what each step proves.

Next: [`tools.md`](tools.md), [`docs-maintenance.md`](docs-maintenance.md).
