# ECSS/ESCC compliance audit: summary report

Status of 2026-10-09 (version 0.1.0, on `master`); the audit itself was done on the branch `compliance/ecss-esccc-audit`. Software criticality category **C** (owner). Standards: ECSS-E-ST-40C Rev.1, ECSS-Q-ST-80C Rev.2 (the tool as software); ECSS-Q-ST-30-11C Rev.2, ECSS-E-ST-20-07C Rev.2, ESCC 3901 Issue 4 (the tool's ability to check harness designs). WireViz was not touched.

**The tool is not claimed to comply with anything.** The matrix records what exists and what evidence there is; compliance is a decision of the owner after the reviews in `OPEN_ACTIONS.md`.

## Status of 2026-10-09
This section was added after the audit; the sections below describe the audit and are otherwise unchanged. The matrix statuses below were **not** re-assessed after the audit (the figures are the same as at the end of phase 4).

**Done since the audit**
- Owner decisions recorded with their date in `DEVIATIONS.md` and `OPEN_ACTIONS.md`: coverage target (T-07) and the controls on AI assistance (T-08) approved; the plans and standards (SPAP, SDP, STANDARDS, CMP, CRITICALITY) approved, without an independent reviewer; the standard value profiles accepted as a whole, without a value-by-value check by a second person; GitHub issues adopted as problem reports. **Waived** by the owner, without a stated reason: protection of the default branch (T-18) and signing of packages (T-19). The owner will not supply the standards that were referred to and not supplied (T-09).
- Release gates (D-135, D-136): a harness cannot be released while a configuration file is a placeholder or while it uses parts that are not approved, unless the releaser gives a written reason, which is kept in the change log and the baseline.
- Release check: a second test run without coverage instrumentation, a scan of the shipped dependencies for known vulnerabilities (D-134), and a generated component table with a requirement-to-component trace for the SDD (`sdd_components.csv`).
- Prepared for people, with nothing filled in on their behalf: the independent-review brief, the review record, the family-group worksheet, the organisation record, the risk register, the dependability input sheet, the usability schedule, the screen-reader checklist and the real-harness acceptance checklist (see `OPEN_ACTIONS.md`).
- The product was renamed Harness Design Studio. Version 0.1.0 was released on 2026-10-09 (tag `v0.1.0`, GitHub release "Harness Design Studio 0.1.0"): 964 tests passed, 1 skipped, with the coverage gate and again without instrumentation; no known vulnerabilities in the 10 shipped packages (`evidence/release_0.1.0_report.md`; package checksums in `SIGNOFF.md`).

**Waived by the owner on 2026-10-09** (`DEVIATIONS.md` T-20 to T-30), because no further feedback from people will come: the independent verifier and validator (A-01), the reviews (A-02), organisation, training, audits and process assessment (A-03), the review board and customer interface (A-04), the dependability and safety analysis (A-07), the review of the security analysis (A-08), the maintainer organisation and support period (A-11), the usability sessions and the screen-reader pass (A-12), the acceptance of the outputs for a real harness (A-13), the mapping of family-group codes (A-16), and the clean-VM installation test of the release procedure.

**What a waiver means here.** It records that the owner accepts the deviation. It does not meet the requirement, and no document, matrix row or report treats it as met: the statuses in the matrix stay *partial*, *human*, *gap* or *na*, and none says compliant. The prepared templates stay available if a person ever does the work.

**Signed off and released by the owner on 2026-10-09:** release candidate 0.1.0rc8 was signed off, and 0.1.0 was then released with the engineering decisions still open, by the owner's waiver of the step 14 condition (`SIGNOFF.md`, `DEVIATIONS.md` T-31). It is not a statement of compliance. **Not waived, and not done:** the real derating and EMC values (D-11), the approved parts list (D-12), the answers on the harness boundary rule (D-10) and the title block (D-15), and the review of the profile values in each project's config files (A-17). Until they exist the tool must be used as it is labelled: results rest on placeholders and example parts unless a person has reviewed them (a release then needs a written reason, D-135, D-136), the packages are unsigned (T-19), a release candidate is labelled *not signed off by the owner*, and no compliance with any standard is claimed.

## What was done
| Phase | Result |
| --- | --- |
| 0 | Requirements extracted from the five PDFs into `requirements/*.csv` (ECSS-E-ST-40C 783, ECSS-Q-ST-80C 347 (344 in the matrix, see the note under the matrix table), ECSS-Q-ST-30-11C 219, ECSS-E-ST-20-07C 318, ESCC 3901 81 rows); criticality proposal; baseline tests |
| 1 | Gap analysis, compliance matrix, remediation plan (`gap_analysis.md`); owner approval |
| 2 | Process tools and documents; 11 new design rules, optional standard value profiles, Table 6-41 bundle factor in sizing, power/return separation in pin allocation, EMC class on wire lists and labels |
| 3 | Tests before and after; outputs compared before and after; coverage and metrics |
| 4 | Draft DRD documents in `docs/`; deviations; open actions |

## Matrix after phase 4 (`compliance_matrix.csv`)
Kind A (software), statuses are *partial* (something exists), *human*, *gap*, *na*:

| Standard | Rows | partial | human | gap | na | Baseline: partial / gap |
| --- | --- | --- | --- | --- | --- | --- |
| ECSS-E-ST-40C | 783 | 645 | 120 | 0 | 18 | 163 / 482 |
| ECSS-Q-ST-80C | 344 | 261 | 47 | 2 | 34 | 151 / 112 |

ECSS-Q-ST-80C has 347 requirement rows in `requirements/ECSS-Q-ST-80C.csv` but 344 in the matrix: three rows of the standard's table are marked `<<deleted>>` (IDs `ECSS-Q-ST-80_0720092`, `ECSS-Q-ST-80_0720093`, `ECSS-Q-ST-80_0720214`) and are left out of the matrix.

**Read "partial" with care.** For the 556 rows that are document-content requirements, "partial" means a draft document with the DRD's headings now exists; no one has checked each content requirement of the DRD against it, and no draft has been reviewed. For other rows it means the tool, a test or a procedure serves the clause; the assessment is by clause (`DEVIATIONS.md` T-11). The two remaining gaps are quality-model clauses of ECSS-Q-ST-80C 5.2.7.

Kind B (design checking), 41 requirements, after phase 2 (`assessment/design_assessment.csv`):

| Standard | Rows | Automatic | Partial | Human only |
| --- | --- | --- | --- | --- |
| ECSS-Q-ST-30-11C | 25 | 3 | 13 | 9 |
| ECSS-E-ST-20-07C | 14 | 1 | 6 | 7 |
| ESCC 3901 | 2 | 0 | 1 | 1 |

"Automatic" means the tool reports a violation by itself once the project data are supplied. Every rule is silent without its numbers and the report lists what it could not check.

## Evidence (`evidence/`)
- Tests before the audit: 839 passed, 1 skipped. After the design-check features: 902 passed, 1 skipped. Final runs of the audit: 910 passed, 1 skipped, without instrumentation and with coverage (`evidence/final_runs.md`). Latest: 964 passed, 1 skipped (`evidence/release_0.1.0rc8_report.md`).
- Outputs before and after for three reference projects: 592 of 595 files identical; the 3 that differ are the design rule reports (`evidence/output_comparison.md`, `evidence/output_differences.md`). Drawings and BOMs are unchanged.
- Coverage of `core`: 96.63 % statements, 93.16 % branches (`metrics.json`).
- Traceability: `traceability.csv` (78 tool requirements, `tools/trace.py`); `sdd_components.csv` (94 modules; 60 reached by a requirement directly, 79 directly or indirectly; the file is generated by `python -m tools.gen_sdd_components`, so its rows are the count).

## Changes to the tool
Everything is opt-in or silent by default. Projects that do not use the new settings behave as before, except that the design rule report says `Rules run: 33` and cites a requirement ID in findings of the rules that serve one. See `CHANGELOG.md` and `docs/DECISIONS.md` D-131.

## Where the tool is weakest against the standards
1. No independent verification or validation and no recorded reviews (A-01, A-02; waived, T-20, T-21); the review board and customer interface are not named (A-04; waived, T-23).
2. Wire surface temperature under load, the partial-load factor L, bundle spacing, multipactor, bond resistances and the "family-group code" mapping cannot be checked by the tool (T-14 to T-16, checklist).
3. No specialist has reviewed the security analysis (A-08; waived, T-25); packages are unsigned by the owner's waiver (T-19). Dependencies are scanned for known vulnerabilities at each release.
4. Standards referred to by the supplied ones were not supplied, so many "shall apply" clauses are marked *human* (T-09).

## Files
`PHASE0.md`, `gap_analysis.md`, `compliance_matrix.csv`, `traceability.csv`, `sdd_components.csv`, `family_group_mapping.csv`, `FAMILY_GROUP_MAPPING.md`, `ORGANISATION.md`, `RISK_REGISTER.md`, `metrics.json`, `DEVIATIONS.md`, `OPEN_ACTIONS.md`, `docs/` (drafts; five approved), `requirements/`, `assessment/`, `evidence/`, `templates/`.
