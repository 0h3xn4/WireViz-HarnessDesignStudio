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
| Step 15: tag the merge commit and publish the release page, with the packages attached | A person | [`../RELEASE.md`](../RELEASE.md) step 15 |

A coding assistant cannot attach files to a GitHub release page. Attaching the `.deb`, the `.tar.gz` and `SHA256SUMS` is a person's step.

"Step 14" means the owner's sign-off. "14 steps" in the evidence reports means the number of automatic checks. They are not the same.

## Before you start

- You need Ubuntu 24.04 (the only supported system, [D-127](../DECISIONS.md)), the development environment from [`setup-and-tests.md`](setup-and-tests.md), and network access for the SBOM and the vulnerability scan (or a wheelhouse made with `python -m tools.vendor`).
- Every change since the last release is in `harness/CHANGELOG.md` under *Unreleased (after X.Y.Z)*.
- The pull request with the changes is merged, or you are working on the branch that will be.

## 1. Prepare the version

1. Choose the new number (semantic versioning). Change it in `pyproject.toml` and `src/harness_design_studio/__init__.py`.
2. In `CHANGELOG.md`, rename the *Unreleased* heading to the new version and date, and say there what changed and what is still open. The release check compares the changelog with the version and skips an *Unreleased* section.
3. Check the documents that quote the version or the release state: the root [`README.md`](../../../README.md), [`../../README.md`](../../README.md) (status section), [`../../compliance/SIGNOFF.md`](../../compliance/SIGNOFF.md), [`../OPEN_DECISIONS.md`](../OPEN_DECISIONS.md). A release candidate carries `rcN` in its version until the owner signs off (D-113).

**Why this matters for the documents:** `master` and the last release print the same version until you do this. The pages that describe features that are only on `master` carry a note ("not in the 0.1.0 packages"); update or remove those notes when the new version ships.

## 2. Run the automatic checks

From `harness/`:

```
python -m tools.release_check
```

It runs steps 1 to 11 in order and writes `dist/release-docs/release-report.md`. A quicker run for a change in progress:

```
python -m tools.release_check --quick
```

The full run builds the installer and the `.deb`, so it takes a long time and needs the Qt libraries (see [`../INSTALL.md`](../INSTALL.md)). With Docker, use the build container in `packaging/ubuntu/container/`.

Read `release-report.md`. It lists each step with its result and keeps the numbers (tests passed, packages scanned). Those numbers belong in the report, not in other documents.

## 3. The steps only a person can do

1. Run the packaged self-test on a clean Ubuntu 24.04 machine with the network switched off (step 12; waived for 0.1.0).
2. Hold usability sessions if the owner wants them (step 13; waived for 0.1.0).
3. The owner signs off (step 14). Record the sign-off in [`../../compliance/SIGNOFF.md`](../../compliance/SIGNOFF.md) in the owner's words, and record any waiver in [`../../compliance/DEVIATIONS.md`](../../compliance/DEVIATIONS.md). A waiver accepts that a requirement is not met; it does not meet it.
4. After the pull request is merged and CI is green on the merge commit (step 15): create the annotated tag `vX.Y.Z` on the merge commit, push it, publish the release page with the same wording as the tag message, attach the packages and `SHA256SUMS`, and compare the checksums with the ones recorded in `compliance/evidence/`.

## 4. After the release

- Copy the release report and the checksum list into `compliance/evidence/` as `release_X.Y.Z_report.md` and `release_X.Y.Z_SHA256SUMS`, as for earlier releases.
- Start a new *Unreleased* section in `CHANGELOG.md`.
- Check that the install page ([`../INSTALL.md`](../INSTALL.md)) still names the right place to get the packages.

## If a check fails

Fix the cause and run the check again. Never skip or disable a test to pass a release. [`setup-and-tests.md`](setup-and-tests.md) lists what to do when a test fails, and [`../RELEASE.md`](../RELEASE.md) says what each step proves.

Next: [`tools.md`](tools.md), [`docs-maintenance.md`](docs-maintenance.md).
