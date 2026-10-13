# Organisation, resources, training, audits and process assessment (A-03)

For ECSS-Q-ST-80C 5.1.1 to 5.1.5, 5.2.3, 5.7. **Every name, date and signature below is empty on purpose**: these are facts about people that only the owner can enter. The developer assistant has filled in only the role descriptions that follow from the project's documents. ECSS-Q-ST-10 and ECSS-M-ST-80 (referred to by 5.2.3 and 5.3.1) were not supplied (A-18).

## 1. Roles (5.1.1, 5.1.2.1, 5.1.4.1)
| Role | Task and authority | Held by | Since |
| --- | --- | --- | --- |
| Owner: customer and supplier | Decides requirements, criticality, tailoring and waivers; chairs reviews; accepts the product and the outputs for a harness | | |
| Developer (assistant, AI) | Writes code, tests and the first versions of the documents under the owner's review; presents at reviews; decides nothing that the plans reserve for people | not a person; sessions are recorded in the repository history | |
| Software product assurance engineer | Proposes and maintains the product assurance programme; has the authority and independence the standard describes (5.1.4.2), including access to the project manager | | |
| Independent verifier and validator | Did not write the design, code or tests; reviews the evidence (`templates/independent_review_brief.md`, A-01) | | |
| Maintainer organisation | Support, migration, retirement (A-11) | | |
| Reviewer of audits | Not directly involved in the work reviewed (5.1.3.2) | | |

With one owner who is customer and supplier, the independence required by 5.1.3.2 and 5.1.4.2 can only be met by naming other people (deviation T-02). If that is not possible, record the deviation and its reason in `DEVIATIONS.md`.

## 2. Interfaces to other organisations (5.1.2.2, 5.1.2.3)
| Organisation | Interface | Documented in |
| --- | --- | --- |
| Open-source libraries (handled as reused software, T-05) | Versions pinned; SBOM and licence report at each release | `docs/SRF.md`, `SBOM` |
| Source hosting (GitHub) | Repository, issues as problem reports, CI | `docs/PROBLEM_REPORTING.md` |
| Lower-level suppliers | none; no software work is delegated | |
| Customer interface for nonconformances | to be named (A-04) | |

## 3. Resources (5.1.3.1, 5.1.5.1)
| Question | Answer (owner) |
| --- | --- |
| Which people and how much time are available for development, product assurance and review? | |
| Which tools and machines are needed (Ubuntu 24.04 build host, a clean VM for the install test, a computer with Orca)? | |
| Which skills are needed that are not yet available (parts engineering for A-16, safety analysis for A-07, screen-reader testing for A-12)? | |

## 4. Training records (5.1.5.2 to 5.1.5.4)
The training subjects follow from the tools and methods used: the harness tool itself (`../docs/GETTING_STARTED.md`), ECSS-E-ST-40C and ECSS-Q-ST-80C at category C, the review and problem-reporting procedures (`SRevP.md`, `PROBLEM_REPORTING.md`), and security awareness for the people who sign and publish packages (5.1.5.4 b, `SECURITY_DOCS.md`).

| Person | Subject | Date | Evidence (certificate, course, supervised use) | Entered by |
| --- | --- | --- | --- | --- |
| | | | | |

## 5. Audits (5.1.3.2, 5.2.3)
The first audit is proposed after the first independent review (A-01). Audits cover the process (is `../docs/RELEASE.md` followed; are problem reports handled as `PROBLEM_REPORTING.md` says; are plans current) and the product (does the delivered package match `SCF.md`). The auditor is not involved in the work audited.

| Audit | Scope | Auditor | Date | Findings (RIDs) | Closed |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## 6. Process assessment (5.7)
Not done. 5.7.2 asks for a documented assessment model and method that conform to ISO/IEC 33002:2015, a competent assessor, and a customer who sets the scope. The owner decides whether a formal process assessment is wanted for a tool of this size; if not, record the deviation with the reason in `DEVIATIONS.md`. The metrics the project collects today (`python -m tools.metrics`, defect counts from the issue list) are the inputs a later assessment would use.

| Item | Entry (owner) |
| --- | --- |
| Assessment wanted? (yes / no, with reason) | |
| Model and method | |
| Assessor | |
| Scope and date | |
