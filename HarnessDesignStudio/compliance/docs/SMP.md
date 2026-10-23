# Software maintenance plan (SMP)

DRD: ECSS-E-ST-40C Annex T. Status: draft, not reviewed. Flight-software provisions (5.10.2) do not apply.

## 1 to 3. Introduction, references, terms
`SDP.md`.

## 5. Application of the plan, 6. General requirements
System: Harness Design Studio, ground engineering software. Status: the latest published release is `1.7.0` (2026-10-22); `1.0.0` was released on the owner's instruction and `1.1.0` to `1.7.0` followed, all with placeholder values and example parts (`SIGNOFF.md`). Support: the owner and the developer assistant on request. Maintainer organisation: to be named by the owner (action A-11). Contracts: none.

## 7. Maintenance concept
Corrective (problem reports), adaptive (new versions of Ubuntu and Windows, new library versions; macOS is no longer maintained, D-168), perfective (owner requests). Support period: not set (A-11). Tailoring: the full maintenance process of the standard is reduced to the steps below.

## 8. Maintenance activities, 10. Maintenance process
1. Analysis: reproduce the problem or understand the request; write the SPR or change request (`PROBLEM_REPORTING.md`).
2. Design: update `SDD.md` references if the architecture changes; record a decision in `../../docs/DECISIONS.md`.
3. Implementation: test first; follow `STANDARDS.md`; branch and pull request (`CMP.md`).
4. Acceptance: CI green; owner merges.
5. Delivery: `../../docs/RELEASE.md`, `SCF.md`, `SRelD.md`.

## 9. Resources, methods and standards
As `STANDARDS.md`.

## 11. Training
None.

## 12. Product assurance and 13. Configuration management
`SPAP.md`, `CMP.md`.

## 14. Records and reports
SPRs (GitHub issues), `../../CHANGELOG.md`, git history.

## 15. Request form
`../templates/problem_report.md`.

Migration and retirement: projects carry a schema version; migrations keep the original files (REQ-MIGRATE-01). A retirement plan and notification are not written (action A-11).
