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
| Steps 12 to 14: a test on a clean machine, usability sessions, the owner's sign-off | People. The owner waived 12 and 13 for 0.1.0 (T-30, T-27) and waived the condition of 14 (T-31); the publication records of 1.0.0 to 1.8.0 in `compliance/SIGNOFF.md` say that these waivers stand, and nobody has signed off 1.1.0 to 1.8.0 as the owner. | [`../RELEASE.md`](../RELEASE.md), [`../../compliance/DEVIATIONS.md`](../../compliance/DEVIATIONS.md) |
| Step 15: tag the merge commit | A person | [`../RELEASE.md`](../RELEASE.md) step 15 |
| Building the packages and publishing the release page | The workflow `.github/workflows/release.yml`, started by pushing the tag | [`../RELEASE.md`](../RELEASE.md) step 15 |

Pushing the tag `vX.Y.Z` (or publishing a release that creates the tag on GitHub) starts `.github/workflows/release.yml`. It checks that the tag matches the version and the changelog. Then one job for each platform builds its packages and runs a smoke test on the finished files: Linux (the `.tar.gz` and the `.deb`, with the packaged self-test) and Windows (the setup program and the portable `.zip`). The last job, which alone publishes, writes one `SHA256SUMS` over all four files and creates the GitHub release page with them attached (with `workflow_dispatch` and the tag name you can run it again; it then replaces the files). A failed build or smoke test on any platform stops the release before anything is published. The tag is still a person's step. The packages are not signed: the signing steps run only when the certificate secrets exist (`../RELEASE.md`, *Windows packages*), and none exist.

"Step 14" means the owner's sign-off. "14 steps" in the evidence reports means the number of automatic checks. They are not the same.

## Before you start

- You need Ubuntu 24.04 for `tools.release_check` (the Windows packages are built by the release workflow, see [`RELEASE.md`](../RELEASE.md), [D-149](../DECISIONS.md)), the development environment from [`setup-and-tests.md`](setup-and-tests.md), and network access for the SBOM and the vulnerability scan (or a wheelhouse made with `python -m tools.vendor`).
- Every change since the last release is in `HarnessDesignStudio/CHANGELOG.md` under `## Unreleased`.
- The pull request with the changes is merged, or you are working on the branch that will be.

## 1. Prepare the version

1. Choose the new number (semantic versioning). Change it in `pyproject.toml` and `src/harness_design_studio/__init__.py`.
2. In `CHANGELOG.md`, rename the `## Unreleased` heading to the new version and date, say there what changed and what is still open, and put a fresh empty `## Unreleased` above it. The release check compares the changelog with the version, skips the *Unreleased* section and fails while it has text.
3. Check the documents that quote the version or the release state: the root [`README.md`](../../../README.md), [`../../README.md`](../../README.md) (status section), [`../../CLAUDE.md`](../../CLAUDE.md) (status), [`../../compliance/SIGNOFF.md`](../../compliance/SIGNOFF.md), [`../OPEN_DECISIONS.md`](../OPEN_DECISIONS.md), and the pages that print the version (`harness 1.8.1` in [`../INSTALL.md`](../INSTALL.md) and [`setup-and-tests.md`](setup-and-tests.md)). Search all the documents for the old version number and read each hit; the dated records (changelog, decisions, release pages, audits) keep their old numbers on purpose. A change of the interface must leave the written files alone: run `python -m tools.output_hashes --check docs/ui/OUTPUT_HASHES_1.2.0.json`. It maps the current version stamp to `1.2.0` only when both strings have the same length, so a version such as `1.10.0` needs `tools/output_hashes.py` and its test looked at first. A release candidate carries `rcN` in its version until the owner signs off (D-113).

**Why this matters for the documents:** until you do this, `master` prints the version of the last release. Pages that describe something that is only under `## Unreleased` should say so; remove those notes when the new version ships. The tool version is part of every project's model hash, so the quoted hashes in the documents change with the version (the tests tell you which).

## 2. Run the automatic checks

From `HarnessDesignStudio/`:

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

1. Run the packaged self-test on a clean Ubuntu 24.04 machine with the network switched off (step 12; waived for 0.1.0, and not done for any release since).
2. Hold usability sessions if the owner wants them (step 13; waived for 0.1.0, and not held for any release since).
3. The owner signs off (step 14). Record the sign-off in [`../../compliance/SIGNOFF.md`](../../compliance/SIGNOFF.md) in the owner's words, and record any waiver in [`../../compliance/DEVIATIONS.md`](../../compliance/DEVIATIONS.md). A waiver accepts that a requirement is not met; it does not meet it.
4. After the pull request is merged and CI is green on the merge commit (step 15): create the annotated tag `vX.Y.Z` on the merge commit and push it. That starts the release workflow, which builds the packages and publishes the release page. **If you cannot push a tag from where you work** (HTTP 403 on tag pushes: the assistant's working session got it for 1.0.0 and for 1.3.0 to 1.7.0, as the publication records in `compliance/SIGNOFF.md` say), the owner creates the release on the GitHub page instead: GitHub > Releases > Draft a new release > *Choose a tag*: type `vX.Y.Z` and select *Create new tag on publish* > target `master` > Publish. The tag push starts `release.yml`, which fills in the files and notes (the tag is then a plain tag without a message; `../RELEASE.md` step 15 describes it, and [`../../compliance/SIGNOFF.md`](../../compliance/SIGNOFF.md) records how each version was published). When the workflow has finished, open the release page and check that all four packages and `SHA256SUMS` are attached: `harness-design-studio_X.Y.Z_amd64.deb`, `harness-design-studio-X.Y.Z-linux-x86_64.tar.gz`, `harness-design-studio-X.Y.Z-windows-x86_64-setup.exe`, and `harness-design-studio-X.Y.Z-windows-x86_64.zip`. Compare the checksums with the ones in `compliance/evidence/release_X.Y.Z_SHA256SUMS` (a build on another machine can differ in bytes; the release notes say so).

## 4. After the release

- Copy the checksum list that is on the release page into `compliance/evidence/` as `release_X.Y.Z_SHA256SUMS` (for 1.0.0 to 1.8.0 that is the only evidence file that was kept; the release report `release_X.Y.Z_report.md` and the vulnerability report `release_X.Y.Z_vulnerability_report.txt` exist for 0.1.0 and its candidates, for 1.7.0 the full `release_check` was not run (its section in `SIGNOFF.md` says that the checks were those of the pull requests and of the workflow run), and for 1.8.0 the repository does not say whether it was run). Add a section *Publication of X.Y.Z* to [`../../compliance/SIGNOFF.md`](../../compliance/SIGNOFF.md) that says who made the tag and when, which run built the packages, and the checksums. It is a record, not a statement of compliance.
- Keep the empty `## Unreleased` section at the top of `CHANGELOG.md` for the next changes.
- Check that the install page ([`../INSTALL.md`](../INSTALL.md)) still names the right place to get the packages.

## If a check fails

Fix the cause and run the check again. Never skip or disable a test to pass a release. [`setup-and-tests.md`](setup-and-tests.md) lists what to do when a test fails, and [`../RELEASE.md`](../RELEASE.md) says what each step proves.

Next: [`tools.md`](tools.md), [`docs-maintenance.md`](docs-maintenance.md).
