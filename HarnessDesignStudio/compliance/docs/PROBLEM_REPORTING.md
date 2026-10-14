# Software problem reporting and nonconformance handling

Addresses ECSS-Q-ST-80C 5.2.5.1 to 5.2.5.4 and 5.2.6.1 (gap G-04). Status: **in use from 2026-10-08 (GitHub issues adopted by the owner); the board and the customer interface still need people** (see `OPEN_ACTIONS.md`).

## 1. What is a problem

Any behaviour of the tool, a document or a test that differs from the specification, or a defect found in the process. Every problem gets a **software problem report (SPR)**, even if it is fixed in minutes.

## 2. Where reports live

One GitHub issue per SPR, created from `compliance/templates/problem_report.md` (copy the text into the issue). The issue number is the SPR identifier (`SPR-<number>`). A problem found while working with an assistant session is entered by the person who accepts the fix; commit messages name the SPR.

## 3. Content of a report (5.2.5.2)

The template asks for: identification of the software item and version (`harness --version`, model hash if a project is involved), date, reporter, environment (Ubuntu version, install method), a description with steps to reproduce, the **effect** (what goes wrong for the user, or for a harness built from the output), the **severity** (below), the requirement ID it violates if known, and later the analysis, the correction (commit), the regression test and the verification result.

## 4. Severity

| Level | Meaning |
| --- | --- |
| 1 | A wrong output that could reach a harness unnoticed (wrong pin, wrong gauge, a check that passes when it should fail) |
| 2 | A wrong output that is noticed by a verifier or a review, or loss of user data |
| 3 | A defect with a work-around, or a missing "not checked" message |
| 4 | Cosmetic, documentation |

## 5. Handling (5.2.5.1, 5.2.5.4)

1. Log the SPR. Level 1 or 2: stop releasing until it is analysed.
2. Analyse: reproduce, find the cause, list affected releases and the affected requirement.
3. Correct with a test that fails before and passes after (project rule: every bug fix gets a regression test).
4. Verify: full test suite and the checks of `docs/RELEASE.md`; for levels 1 and 2 also check whether projects released with the faulty version need re-checking and tell the owner (the model hash on every output identifies the version).
5. Close the issue with the commit and test named. Record it in `CHANGELOG.md`.

## 6. Interface with nonconformance handling (5.2.5.3, 5.2.6.1)

A problem that means the delivered software or a process step does not meet a requirement is also a **nonconformance (NCR)**: label the issue `nonconformance`. The nonconformance review board (NRB) of 5.2.6.1 b to d has to be formed by the owner (`OPEN_ACTIONS.md`, action A-04); until then the owner disposes each NCR in writing in the issue. ECSS-Q-ST-10-09, referred to by 5.2.6.1 a, was not supplied; this procedure does not claim to meet it.

## 7. Metrics

Defect counts by severity and by release are taken from the issue list when a milestone report is written (`SPAMR`); fault density is defects per 1000 source lines (`python -m tools.metrics`).
