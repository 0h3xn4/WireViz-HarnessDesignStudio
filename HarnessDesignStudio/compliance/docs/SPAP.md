# Software product assurance plan (SPAP)

DRD: ECSS-Q-ST-80C Annex B. Software: Harness Design Studio `0.1.0` (the plan has been applied to every release since, the latest being `1.4.0`; the owner approved it on 2026-10-08 and has not approved it again for a later version; this document was not changed for 1.0.0 to 1.4.0 except this line and the build hosts in 5.3). Criticality: C. Status: approved by the owner on 2026-10-08 (approval given in the working session; the owner is also customer and supplier, so no independent reviewer, see A-01).

## 1. Introduction
Purpose: define how product assurance is done for the harness design tool. Applicable: ECSS-Q-ST-80C Rev.2 with ECSS-E-ST-40C Rev.1, tailored for category C (Table D-2 and Table R-1, evaluated in `../requirements/`).

## 2. Applicable and reference documents
`../gap_analysis.md`, `../compliance_matrix.csv`, `CRITICALITY.md`, `STANDARDS.md`, `CMP.md`, `PROBLEM_REPORTING.md`, `SDP.md`, `SVerP.md`, `SValP_SVS.md`, `../../docs/SPEC.md`. Not supplied and therefore not claimed: ECSS-Q-ST-10, -10-09, -20, -30, -40, ECSS-M-ST-40, ECSS-Q-ST-60-15.

## 3. Terms
As in ECSS-S-ST-00-01 where used; "owner" is the person who is customer and supplier.

## 4. System overview
An offline desktop tool in which a user draws a spacecraft system (units and interfaces); the tool generates harnesses and checks and documents them (`../../docs/SPEC.md`). It is a ground engineering tool; it runs no flight code. Its outputs are used to manufacture flight harnesses, which is why the product is category C (`CRITICALITY.md`).

## 5. Software product assurance programme implementation
- **5.1 Organization, 5.2 Responsibilities:** one owner (customer, supplier, approval authority), one developer assistant (writes code and documents under the owner's instruction). Independent product assurance and independent verification are **not in place** (action A-01). The assistant is not an independent party.
- **5.3 Resources:** the repository, CI (`.github/workflows/harness-ci.yml`), Ubuntu 24.04 build host (`docs/RELEASE.md`); since 1.2.0 also the Windows build job of the release workflow and the test run on that system (macOS jobs existed from 1.2.0 to 1.5.0, removed in D-168) (`.github/workflows/harness-platforms.yml`).
- **5.4 Reporting:** milestone report `SPAMR.md`, `CHANGELOG.md`, problem reports (`PROBLEM_REPORTING.md`).
- **5.5 Quality models:** not defined (gap G-05); metrics are collected by `tools/metrics.py` (size, complexity, coverage, tests); a quality model with targets is proposed in `SVerP.md` section 6.3.
- **5.6 Risk management:** open decisions and placeholders are the risk list (`../../docs/OPEN_DECISIONS.md`, `../../docs/PLACEHOLDERS.md`); the register is `../RISK_REGISTER.md` (started; ratings and owners are for people, action A-03).
- **5.7 Supplier selection and control:** no lower-level suppliers; third-party software in `SRF.md`.
- **5.8 Methods and tools:** `STANDARDS.md`.
- **5.9 Process assessment and improvement:** none (action A-03).
- **5.10 Operations and maintenance:** `SMP.md`.

## 6. Software process assurance
- **6.1 Development cycle:** milestones M0 to M9, audit, compliance audit (`SDP.md`).
- **6.2 Plans:** `SDP.md`, `SRevP.md`, `SVerP.md`, `SValP_SVS.md`, `SUITP.md`, `CMP.md`, `SMP.md`, `SECURITY_DOCS.md`.
- **6.3 Dependability and safety:** classification in `CRITICALITY.md`; the formal dependability and safety analysis is open (action A-07).
- **6.4 Security:** `SECURITY_DOCS.md`.
- **6.5 Documentation and configuration management:** `CMP.md`, `SCF.md`.
- **6.6 Process metrics:** `../metrics.json`, `tools/metrics.py`.
- **6.7 Reuse:** `SRF.md`.
- **6.8 Planning for individual processes:** in the plans above.
- **6.9 Procedures and standards:** `STANDARDS.md`, `PROBLEM_REPORTING.md`, `../../docs/RELEASE.md`.

## 7. Software product quality assurance
Product quality requirements: `SRS.md` section 5.10. Assurance: tests (`../../tests/`), independent output verifier (`core/verify.py`, `core/outputs/verify.py`), static analysis (ruff, mypy strict), reproducible builds.

## 8. Compliance matrix to software product assurance
`../compliance_matrix.csv` (rows of kind A for ECSS-Q-ST-80C). Statuses: partial, gap, human, na. No row says compliant; compliance is a decision of the owner after the reviews in `../OPEN_ACTIONS.md`.
