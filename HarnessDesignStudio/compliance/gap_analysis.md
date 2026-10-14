# Compliance audit, Phase 1: gap analysis

Branch `compliance/ecss-esccc-audit`. Criticality category **C** (approved by the owner). Status: **waiting for owner approval of the remediation plan** (section 6) and three decisions (section 7).

> **Phase 2 to 4 update (October 2026):** the plan below was approved and carried out. The state afterwards is in `SUMMARY.md`, `compliance_matrix.csv` (columns `status_after_phase2`, `evidence_after_phase2`), `DEVIATIONS.md` and `OPEN_ACTIONS.md`. This file is the Phase 1 baseline and is not rewritten.

Files: `compliance_matrix.csv` (one row per applicable requirement, rebuilt by `python -m tools.build_compliance_matrix`), `requirements/*.csv` (extracted requirements), `assessment/*.csv` (the judgements behind the matrix, each with a rationale), this file.

Nothing here says the tool *complies*. The status words are an assessment of what exists today; Phase 3 collects evidence, and a person decides compliance.

## 1. Two kinds of compliance

| Kind | Standards | What is assessed | Basis of the assessment |
| --- | --- | --- | --- |
| **A. The tool as software** | ECSS-E-ST-40C Rev.1, ECSS-Q-ST-80C Rev.2 | the development process and products of this repository | **clause level**: every requirement inherits the assessment of its clause (about 1100 rows). Requirements that differ have their own row in `assessment/process_overrides.csv`. |
| **B. The tool as a checker of designs** | ECSS-Q-ST-30-11C Rev.2, ECSS-E-ST-20-07C Rev.2, ESCC 3901 Issue 4 | what the tool does today about each wire, cable, connector, contact and harness requirement | **requirement level**: 41 requirements, each read and compared with the code (`assessment/design_assessment.csv`) |

The clause-level basis for kind A is a limit of this audit. It is enough to plan the work and to see where the large gaps are; it is not enough to claim anything on a single requirement. Where Phase 2 produces a document or a check, the rows it touches are re-assessed one by one in Phase 3.

## 2. Results: kind A (software), category C

Status words: **partial** = something exists that serves the requirement; **gap** = nothing exists; **human** = needs a person or the organisation (review, independence, signature, training); **na** = not applicable (category C table or tailoring, reason given).

| Standard | Applicable rows | partial | gap | human | na |
| --- | --- | --- | --- | --- | --- |
| ECSS-E-ST-40C | 783 | 163 | 482 | 120 | 18 |
| ECSS-Q-ST-80C | 344 | 151 | 112 | 47 | 34 |

- 505 of the 783 ECSS-E-ST-40C rows (and 51 of the Q-80C rows) are *document content* requirements from the DRD annexes (SRS, SDD, SVerP ...). They are a gap because the documents do not exist in DRD form. One piece of work closes most of them: Phase 4.
- No row is "evidence-candidate" yet: even where tests or tools exist, nothing is cross-referenced to a requirement ID (gap G-02).
- Honest summary: the project has strong engineering practice (839 tests, strict typing, linting, reproducible builds, a security review, recorded decisions) and almost none of the formal process records the two standards ask for (plans, reviews, reports, problem reporting, metrics, independence).

> Update during Phase 2: the extractor wrongly dropped two requirements that are tables (30-11C Table 6-10 and 6-11, IDs 0140051 and 0140058) because a table row said `<<deleted>>`. Fixed; the count of relevant 30-11C requirements is 25, kind B has 41.

## 3. Results: kind B (design checking), 41 requirements

Columns: what the tool does today and what is realistic as a target. "Automatic" means the tool can report a violation by itself once the project data are supplied; "partial" means it checks part of the requirement or needs data the model does not hold; "human" means a person must decide, and the tool can only remind (review checklist) or say *not checked*.

| Standard | Relevant | Today: partial | Today: none | Target: automatic | Target: partial | Target: human |
| --- | --- | --- | --- | --- | --- | --- |
| ECSS-Q-ST-30-11C | 25 | 6 | 19 | 3 | 13 | 9 |
| ECSS-E-ST-20-07C | 14 | 4 | 10 | 1 | 6 | 7 |
| ESCC 3901 | 2 | 1 | 1 | 0 | 1 | 1 |

No requirement is fully automatic **today**. Details per requirement are in `compliance_matrix.csv`; the important ones:

- **Wire derating (30-11C 6.32.4 to 6.32.5.2).** The tool has one bundle factor and one temperature factor for the whole project. The standard gives a bundle factor K that depends on the number of wires (Table 6-41: 1 for 1 wire, 0,9 for 2, 0,81 for 3 ... 0,12 for 300) and an extra factor L for partly loaded bundles (Table 6-42), 50 % voltage derating and a wire surface temperature 50 °C below the manufacturer maximum. None of these are checked: the tool has no wire voltage rating or temperature rating.
- **Power and return separated by an unassigned contact (30-11C 6.11.3 a).** Not checked. The pin allocator only has a generic power-to-signal gap.
- **Mating cycles (6.11.3 e, 6.12.3 c).** Not modelled.
- **Connector derating (6.11.2 a, Table 6-10: 50 % current, voltage 25 % of withstand voltage or 75 % of rated, temperature 30 °C below maximum).** Only the contact current factor exists.
- **EMC wiring (20-07C 4.2.13).** Interface categories, EMC classes and shield end concepts exist. Not covered: same-category wires in one bundle, shield not used as a current-carrying conductor (except coax), EMC category marked on wires and labels, 5 cm separation of bundles of different categories (the model holds no routing geometry, so this stays human).
- **ESCC 3901.** Almost all of it is manufacturer qualification and test. The tool can only record the specification a wire part claims and warn when it is not approved (`part-unapproved` exists).

Rules that already serve a requirement but do not cite it: `mate-mismatch`, `connector-lookalike` (30-11C 6.11.3 c), `shield-wrong-end` (20-07C 4.2.13.2 d, e), `category-mixed`, `emc-mixed` (20-07C 4.2.13.1), `part-unapproved` (ESCC 3901 4.4). Citing the requirement in the rule and in the report is cheap and is part of the plan (B-12).

## 4. Gap register: kind A

| Gap | What is missing | Rows | Kind of work |
| --- | --- | --- | --- |
| G-01 | The required documents and plans in DRD form (SPAP, SPAMR, SDP, SRevP, SRS, SDD, ICD, SVerP, SValP, SVS, SUITP, SVR, SUM, SRelD, SMP ...) | 577 | write (Phase 4) |
| G-02 | Requirement numbering and traceability: requirement to design to test | 84 | tool + data (Phase 2) |
| G-03 | Criticality classification of software components, measures for critical software | 17 | write (Phase 2) |
| G-04 | Problem reporting, nonconformance handling, alerts, work-around handling | 21 | procedure + issue template (Phase 2); board is human |
| G-05 | Metrics (size, complexity, defects, test coverage) and quality model | 17 | tool (Phase 2) |
| G-06 | Written design, coding and tool standards; justification of tools | 23 | write (Phase 2) |
| G-07 | Software configuration file, integrity values for deliveries, installation report | 48 | tool (Phase 2) |
| G-08 | Reuse file with assessment of the third-party software | 32 | generated from the SBOM (Phase 2, Phase 4) |
| G-09 | Security plan, analysis and risk treatment; vulnerability watching | 66 | write (Phase 2/4); watching is human |
| G-10 | Independent verification and validation | 12 | **human** |
| G-11 | Reviews (SRR, PDR, CDR, QR, AR), test readiness, delivery and security review boards | 55 | **human** (the tool side: review packages and checklists) |
| G-12 | Organisation, personnel, training, audits, process assessment, risk register | 26 | **human** |
| G-13 | Numerical accuracy estimate (voltage drop, derating) | 1 | test (Phase 2) |
| G-14 | Configuration management plan (what is a baseline) | 12 | write (Phase 2) |
| G-17 | Whether AI assistance in writing the code counts as an "automatic code generation tool" (Q-80C 6.2.8) | 7 | **human decision** |
| G-18 | Maintenance, migration and retirement plans and records; operation | 75 | write (Phase 4) |
| G-19 | Tailoring and deviation record | 2 | write (Phase 4), approval is human |

## 5. Gap register: kind B

| Gap | Requirement(s) | What the tool needs | Effort |
| --- | --- | --- | --- |
| B-01 | 30-11C 0140002, 0140179, 0140213 to 0140220 | wire part ratings (rated voltage, maximum temperature); K and L as tables in the derating config; share of loaded wires per bundle; rules for 50 % voltage, 50 °C temperature margin, bundle current | large |
| B-02 | 30-11C 0140052 | rule and pin allocator: unassigned contact between power and return on power connectors | medium |
| B-03 | 30-11C 0140056, 0140061 | connector part rating `max_mating_cycles`, rule against the 50 cycle limit | small |
| B-04 | 30-11C 0140050, 0140051, 0140057, 0140058 | connector voltage and temperature margins (Table 6-10, 6-11) | medium |
| B-05 | 30-11C 0140055 | rule: connector and its parts from one manufacturer | small |
| B-06 | 30-11C 0140054 | cite the requirement in `mate-mismatch` and `connector-lookalike` | small |
| B-07 | 30-11C 0140060, 0140215, 0140221 to 0140223 | "not checked" entries stating that multipactor and thermal analyses are outside the tool | small |
| B-08 | 20-07C 0080033 to 0080042 | EMC wiring rules: shield on external cables, same-class wires in one bundle, shield not a conductor (except coax), shield bonded at both ends via connector body | medium |
| B-09 | 20-07C 0080036 | needs routing geometry; stays a checklist item and a "not checked" line | none (human) |
| B-10 | 20-07C 0080037 | EMC class in wire list and labels | small |
| B-11 | ESCC 3901 4.4 | wire part cites its ESCC detail specification; rule warns when it does not | small |
| B-12 | all of the above | every rule names the requirement IDs it serves, in `docs/RULES.md`, the DRC report and the matrix; a test checks that every matrix reference is a real rule | small |
| B-13 | all numbers above | see decision D-131 below | policy |
| B-14 | 14 human-only requirements | review checklist for harness design, with the requirement IDs | small |

## 6. Remediation plan (proposal)

Order is chosen so that the cheap, high-value items come first and every step keeps the existing tests green. Each step is a small commit that names its requirement or gap IDs, and the suite is run before and after each phase; generated diagrams and BOMs are compared against the goldens and any difference is reported.

**Phase 2a, process foundations (no behaviour change)**
1. Requirement identifiers for the tool's own requirements and a test-to-requirement link (G-02): `REQ-nnn` in `docs/REQUIREMENTS.md`, a marker in tests, `tools/trace.py` that builds `compliance/traceability.csv` and fails when a requirement has no test.
2. Metrics tool (G-05): size, complexity, coverage (statement and branch), tests, open problems. Standard library only.
3. Software configuration file and integrity values (G-07): `tools/gen_scf.py` writes versions, hashes and the SBOM into the release, and the `.deb` gets a SHA-256 file.
4. Problem report and nonconformance procedure with a GitHub issue template (G-04).
5. Component criticality classification, design and coding standards, configuration management plan (G-03, G-06, G-14), written as short documents under `compliance/docs/`.
6. Numerical accuracy test for voltage drop and derating (G-13).

**Phase 2b, design-checking features (behaviour change, new tests, goldens regenerated and reported)**
7. B-12 and B-06 first (citation of requirement IDs), then B-03, B-05, B-11, B-10, B-02, B-04, B-08, B-01 in that order. B-01 is the largest and comes last. Each new rule stays silent (and is listed as *not checked*) until its data exist, as today.
8. Review checklist (B-14) and *not checked* entries for the human items (B-07, B-09).

**Phase 3, verification and validation**: tests for every new rule (positive and negative), mutation checks where the tool has them, traceability report, coverage against the target agreed in decision 3, before and after run of the whole suite and of the generated outputs.

**Phase 4, documents** (under `compliance/docs/`, DRD headings kept, tailored to a single-owner tool): SPAP (with the compliance matrix), SPAMR, SDP, SRevP, SRS, SDD, ICD, SVerP, SValP with SVS, SVR, SRF, SUM (points to the user guide), SRelD, SCF, SMP, security set (SSMP, SSAR, SRTP). Plus the final deliverables: compliance matrix, traceability matrix, deviations and waivers list, open human actions, summary report.

**Not done by me, listed as human actions at the end:** independent verification, all reviews and review boards, acceptance, training records, process assessment, audits, the agreement of coverage targets, vulnerability watching, signatures.

## 7. Decisions needed from you

1. **D-131, standard values in the tool.** Until now the tool contained no number from any standard, because none had been supplied (rule: never invent standard values). The tables you supplied (30-11C Tables 6-10, 6-11, 6-41, 6-42 and the 50 %/50 °C rules) are real, citable values. Proposal: ship them as an **optional profile** `ecss-q-st-30-11c` that a project switches on with a command, never as a default, with every value carrying its requirement ID, still marked as needing engineer review (`"placeholder": true` stays until a person sets it to false). The existing placeholder mechanism and the "not checked" behaviour are unchanged for everyone who does not switch it on. Without this the B-01, B-04 steps cannot be done. *Recommended: yes.*
2. **AI assistance (G-17).** The code of this tool was written with an AI assistant and reviewed by you. Q-80C 6.2.8 is about automatic code generation tools. Should I treat the assistant as a code generation tool (then the verification and validation of its output must be addressed explicitly, which this project largely does by testing everything) or record that clause as not applicable? *Recommended: treat it as applicable and document the controls: tests first, review of every diff, strict static analysis.*
3. **Code coverage target (E-40C 0860135).** For category C the standard writes "TBA": statement and decision coverage values must be agreed with the customer. Today the gate is 90 % statement and branch coverage on `core`, nothing on the GUI. Which target do you want to agree as customer? *Proposal: 90 % branch coverage on `core` (today's gate), measured and reported, and justified exclusions for the GUI.*

## 8. Ambiguities and limits found in the standards

- ESCC 3901 has no requirement IDs; its rows use the clause number. Several clauses bundle many requirements, so counts are indicative.
- ECSS-E-ST-40C marks 15 rows `Ytba` or `Y/Ytba` ("some DRD information may be missing if justified and agreed by the customer", annex R legend). I treat them as applicable; the agreement is a human action.
- ECSS-Q-ST-80C has 14 rows with no entry in Table D-2 (clause 6.2.9 security rows, 6.2.10, 6.3.8.2). The standard says security requirements apply independently of criticality for 6.2.9; I treat all 14 as applicable.
- ECSS-Q-ST-30-11C refers to "family-group codes" (02-01, 13-01 ...) defined in documents that were not supplied. Which tool part classes belong to which family is therefore a human mapping, recorded as an assumption when B-01/B-04 are implemented.
- The vacuum current formula (30-11C 6.32.4 b) has conditions and symbols that I abbreviated in the CSV; Phase 2 must read the PDF text before any implementation.
- Severity categories I to IV (ECSS-Q-ST-30) and compensating-provision rules (ECSS-Q-ST-40) were not supplied; the choice of category C rests on your confirmation.
- Clause-level assessment for kind A (section 1).
