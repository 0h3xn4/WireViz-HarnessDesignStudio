# Compliance records

This folder holds the project's self-assessment against the ECSS and ESCC standards; this page says what is in it, so that you can find a record without reading them all.

**It makes no claim of compliance with any standard.** It is a record of what the standards ask for, what was done, what was not, and what the owner waived.

## Contents

- [Status in five lines](#status-in-five-lines)
- [The records](#the-records)
- [The data files](#the-data-files)
- [The folders](#the-folders)
- [Who this is for](#who-this-is-for)

## Status in five lines

1. The latest published release is version `1.8.0` (2026-10-26, the workshop feedback: connections pin by pin with the pinout first, editing a connector, a group and all wires, a library folder that a team shares, two roles; tag `v1.8.0` on commit `1f7431e`, release workflow run 40390285619). Before it came `1.7.0` (2026-10-22, a build workbook for every harness, the build data a technician needs and a simple workspace; tag `v1.7.0` on commit `e5d8b1e`, created by the owner on the GitHub release page), `1.6.0` (2026-10-21, no macOS and a clearer start for a blank project; tag `v1.6.0` on commit `21f4716`), `1.5.0` (2026-10-21, a harness made by hand and a clearer start on Linux; tag `v1.5.0` on commit `4365368`), `1.4.0` (2026-10-20, the AIT feedback: wire editing, hand-drawn wires, a function on every pin, labels, the last commit, a device library; tag `v1.4.0` on commit `1427aad`), `1.3.0` (2026-10-20, the new user interface; tag `v1.3.0` on commit `e7cf531`), `1.2.0` (2026-10-19, packages for Windows and macOS, D-149; macOS was removed after 1.5.0, D-168) and `1.1.0` (2026-10-18), and `1.0.0` was released on the repository owner's instruction on 2026-10-12. Nobody has signed off 1.1.0, 1.2.0, 1.3.0, 1.4.0, 1.5.0, 1.6.0, 1.7.0 or 1.8.0 as the owner, and no row of the matrix was re-assessed for them. Version `0.1.0` (2026-10-09) had been released with four engineering decisions open: the harness boundary rule (D-10), the real derating and EMC values (D-11), the approved parts list (D-12) and the title block (D-15). For 1.0.0 the assistant recorded defaults for them under the owner's delegation (D-142 to D-145, `DEVIATIONS.md` T-32): no standard or part data was supplied, so results still rest on placeholders and example parts. [`SIGNOFF.md`](SIGNOFF.md) is the record, with the publication of each release from 1.0.0 to 1.8.0 and its checksums.
2. The owner waived the actions that need other people: an independent review, the formal reviews, usability sessions, a screen-reader pass, and a clean-machine installation test. These are waivers T-18 to T-31 in [`DEVIATIONS.md`](DEVIATIONS.md). A waiver accepts that a requirement is not met; it does not meet it.
3. The packages (Ubuntu and Windows; the macOS images of 1.2.0 to 1.5.0 too) are not signed, and the default branch is not technically protected (T-19, T-18). macOS support was removed after 1.5.0 (D-168): 1.6.0 and later (1.7.0 and 1.8.0 too) have no macOS packages (the releases 1.2.0 to 1.5.0 still carry theirs on GitHub, not maintained or tested any more).
4. No person other than the owner has reviewed the tool, and the tool was written mainly by an AI assistant (Claude, through Claude Code). [`ORGANISATION.md`](ORGANISATION.md) leaves every name and signature empty on purpose.
5. The open actions that only people can do are in [`OPEN_ACTIONS.md`](OPEN_ACTIONS.md); the risks are in [`RISK_REGISTER.md`](RISK_REGISTER.md).

## The records

| File | What it is |
| --- | --- |
| [`SUMMARY.md`](SUMMARY.md) | The summary report of the audit: standards used, criticality category, the numbers, what was done in each phase |
| [`SIGNOFF.md`](SIGNOFF.md) | What the owner signed off and released, with the decisions that stayed open, and the publication records of 1.0.0 to 1.8.0 |
| [`DEVIATIONS.md`](DEVIATIONS.md) | Tailoring, deviations and waivers (T-01 to T-32), each with the clause, the reason and the status |
| [`OPEN_ACTIONS.md`](OPEN_ACTIONS.md) | Actions that need a person, and the requirements each one blocks |
| [`RISK_REGISTER.md`](RISK_REGISTER.md) | The risks the project already documents; likelihood, severity and owner are empty on purpose |
| [`ORGANISATION.md`](ORGANISATION.md) | Roles, resources, training, audits and process assessment; names and dates are empty on purpose |
| [`gap_analysis.md`](gap_analysis.md) | The gap analysis (phase 1): what the standards ask for and what was missing |
| [`PHASE0.md`](PHASE0.md) | Phase 0: extraction of the requirements and the criticality proposal |
| [`FAMILY_GROUP_MAPPING.md`](FAMILY_GROUP_MAPPING.md) | How the family-group codes of ECSS-Q-ST-30-11C relate to the tool's part classes |
| [`docs/`](docs/README.md) | The 21 documents asked for by ECSS-E-ST-40C and ECSS-Q-ST-80C (plans, requirements, design, verification, release, security, problem reporting), written for this project |

## The data files

| File | What it is |
| --- | --- |
| [`compliance_matrix.csv`](compliance_matrix.csv) | Every requirement of the five standards, with its assessment and the evidence |
| [`traceability.csv`](traceability.csv) | Each requirement of the tool, the code that serves it, and the tests that name it |
| [`sdd_components.csv`](sdd_components.csv) | The components of the software design and the requirements they serve |
| [`family_group_mapping.csv`](family_group_mapping.csv) | The data behind `FAMILY_GROUP_MAPPING.md` |
| [`metrics.json`](metrics.json) | Basic software metrics: a snapshot taken at the audit milestone, not regenerated since (it does not describe the current tree) |

These files are produced by scripts in `HarnessDesignStudio/tools/` (see [`../docs/developer/tools.md`](../docs/developer/tools.md)); tests fail when they are out of date.

## The folders

| Folder | What is in it |
| --- | --- |
| [`requirements/`](requirements) | The requirements extracted from the five standards, one CSV file each, and the overrides |
| [`assessment/`](assessment) | The assessments that feed the matrix (design, process rules, overrides) |
| [`evidence/`](evidence) | Test runs, the release reports for 0.1.0 and its release candidates, the SHA-256 checksums of every release from 0.1.0 to 1.8.0 (no release report for 1.0.0 to 1.8.0 is kept here) and the vulnerability scans of 0.1.0 and its candidates |
| [`templates/`](templates) | Blank forms: problem report, review record, independent review brief, real-harness acceptance, dependability input sheet |

## Who this is for

Auditors, reviewers and the owner. If you want to use the tool, you do not need any of this: start with the [documentation map of the tool](../docs/README.md). If you want to report a problem with the tool, see [`docs/PROBLEM_REPORTING.md`](docs/PROBLEM_REPORTING.md). The standards' own documents are not in the repository, only the requirements extracted from them.

Next: [`SUMMARY.md`](SUMMARY.md), then [`DEVIATIONS.md`](DEVIATIONS.md).
