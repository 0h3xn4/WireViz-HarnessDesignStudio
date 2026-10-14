# Software verification plan (SVerP)

DRD: ECSS-E-ST-40C Annex I. Status: draft, not reviewed.

## 1 to 3. Introduction, references, terms
See `SDP.md`.

## 4. Software verification process overview
- **4.1 General:** every output of development is verified before use; verification is by review, analysis, inspection and test.
- **4.2 Organization:** the developer assistant verifies its own work with automated checks; the owner reviews. An independent verifier is required by ECSS-E-ST-40C for category C (Table R-1) and is not appointed: **action A-01**.
- **4.3 Master schedule:** at each review (`SRevP.md`) and with every commit (CI).
- **4.4 Resources:** CI runners, Ubuntu 24.04 build host.
- **4.5 Responsibilities:** developer: run the checks; owner: review, accept.
- **4.6 Risks and independence:** same author for code and tests is a known weakness; mitigations are the independent output verifier (code-separate from the generators), mutation tests for every output check, property and soak tests, fuzzing.
- **4.7 Tools, techniques, methods:** pytest, hypothesis, pytest-qt, coverage, mypy strict, ruff, `tools/check_reproducible.py`, `tools/trace.py`, `tools/metrics.py`.

## 5. Control procedures for the verification process
Problems found are logged as SPRs (`PROBLEM_REPORTING.md`); changes follow `CMP.md`.

## 6. Verification activities
- **6.1 General:** the activities and their evidence are listed in `SVR.md`.
- **6.2 Process verification:** by `../compliance_matrix.csv` and the review of plans.
- **6.3 Quality requirements verification (ECSS-Q-ST-80C 7.1):**
  - 6.3.1 Activities: tests, static analysis, metrics, coverage.
  - 6.3.2 Inputs: source, requirements (`../../docs/REQUIREMENTS.md`).
  - 6.3.3 Outputs: test results, `../metrics.json`, `../traceability.csv`.
  - 6.3.4 Methods, tools, facilities: as 4.7.
  - Proposed quality targets, to be agreed (decision 3 of the owner): 90 % statement and branch coverage on `core`; zero mypy and ruff findings; no known severity 1 or 2 problem at release; every requirement traced to at least one test or a named review.
