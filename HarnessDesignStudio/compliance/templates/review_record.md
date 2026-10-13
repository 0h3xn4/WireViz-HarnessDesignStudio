# Review record: <SRR / PDR / CDR / QR / AR, or "combined: ...">

Form of the software review plan (`compliance/docs/SRevP.md`, ECSS-E-ST-40C Annex P). Copy to `compliance/reviews/<tag>-<name>.md` for each review. Dates are entered by the people who hold the review; nothing here is filled in by the tool.

## 1. Identification
- Review held (type and whether combined, and the owner's reason for combining):
- Subject: tag `review-<name>`, commit, version (`harness --version`):
- Date held:
- Chair (owner):
- Reviewer, not the developer (A-01), and the independence statement given on the brief:
- Present: developer assistant (presents, does not decide); others:
- Material sent on (at least a week before, SRevP 8):

## 2. Documents submitted
List every document with its version or commit (all documents of `compliance/docs/` at the first review, SRevP 10):

| Document | Commit or version | Reviewed by | Result (accepted / accepted with RIDs / rejected) |
| --- | --- | --- | --- |
| | | | |

## 3. Objectives of this review (SRevP 6) and conclusion
| Objective | Met? (yes / no / partly) | Basis |
| --- | --- | --- |
| SRR: system context and requirements baseline agreed (`SRS.md`) | | |
| PDR: architecture agrees with requirements (`SDD.md`, `sdd_components.csv`) | | |
| CDR: design, tests and plans agree; code verified | | |
| QR: validation complete (`SValP_SVS.md`) | | |
| AR: acceptance by the owner | | |

Only the objectives of this review need an answer.

## 4. RIDs (review item discrepancies)
| RID | Document and clause | Finding | Severity (blocking / major / minor) | Proposed action | Answer (developer) | Closure (reviewer initials, date) |
| --- | --- | --- | --- | --- | --- | --- |
| RID-01 | | | | | | |

A RID that is blocking stops the review from closing. A finding that the tool or a document does not meet a requirement is also a problem report (`compliance/docs/PROBLEM_REPORTING.md`): open an issue, label it, and write its number in the answer.

## 5. Decisions
Waivers granted or refused (add them to `compliance/DEVIATIONS.md` with name and date), changes to the plan, actions with owner and date:

| Decision | Who | Date |
| --- | --- | --- |
| | | |

## 6. What was not checked
(and why; for example standards not supplied, A-18)

## 7. Closure
- All blocking RIDs closed on:
- Review closed by the owner (name, signature, date):
- Reviewer's signature and date:

After closing: update the Status line of each reviewed document in `compliance/docs/` with the review name and date, and `compliance/OPEN_ACTIONS.md`. A document counts for nothing until its review is recorded (`compliance/docs/README.md`).
