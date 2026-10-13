# Compliance audit, Phase 0: requirement extraction and criticality proposal

Branch `compliance/ecss-esccc-audit`. Status: **waiting for owner approval of the criticality category** (below). Nothing in the tool has been changed in Phase 0.

## Two kinds of compliance, kept apart

| Kind | Question | Standards |
| --- | --- | --- |
| **A. The tool as software** | Is the harness tool itself developed and verified the way the standards require? | ECSS-E-ST-40C Rev.1, ECSS-Q-ST-80C Rev.2 |
| **B. The tool as a checker of designs** | Can the tool check (or support a human checking) that a harness design meets the wire, cable and connector rules? | ECSS-Q-ST-30-11C Rev.2, ECSS-E-ST-20-07C Rev.2, ESCC 3901 Issue 4 |

Compliance of a *harness design* is never claimed by the tool: it can only report which rules it checked and which it could not.

## Source of the requirement IDs

No requirements matrix (EARM) was supplied. The IDs come from the PDFs themselves: the four ECSS documents print an ID above every requirement (`ECSS-Q-ST-30-11_0140052`). **ESCC 3901 prints none**, so its rows use the clause number as ID (`ESCC3901-9.5`) and are clause-based, not requirement-based. `tools/extract_requirements.py` rebuilds the CSV files from the PDFs (the PDFs are not stored in the repository).

## Extraction result (`compliance/requirements/*.csv`)

| Standard | Requirements | Deleted in this revision | Relevant to harness design | Automation proposed |
| --- | --- | --- | --- | --- |
| ECSS-E-ST-40C | 783 | 0 | n/a (process) | per criticality, cat_A to cat_D |
| ECSS-Q-ST-80C | 347 | 3 | n/a (process) | per criticality, cat_A to cat_D |
| ECSS-Q-ST-30-11C | 219 | 31 | 23 (clauses 5.3.2, 6.11, 6.12, 6.32) | 13 partial, 10 human |
| ECSS-E-ST-20-07C | 318 | 6 | 14 (clauses 4.2.10 to 4.2.13, 5.3.11) | 9 partial, 5 human |
| ESCC 3901 | 81 | 0 | 2 (4.4, 4.5) | 1 partial, 1 human |

Notes and limits:

- **No row is marked fully automatic.** Every checkable rule needs a number (derating factor, rating, separation distance) that comes from the project's own engineering data, so at best the tool checks it *partially*, once the data exist. Phase 1 may promote some rows (for example 0140052, power and return separated by an unassigned contact) after reading the code.
- Deleted requirements (`<<deleted>>`) are listed with `deleted = Y` and never counted.
- Process standards: the cat_A to cat_D columns come from ECSS-E-ST-40C Table R-1 and ECSS-Q-ST-80C Table D-2. Rows with no applicability row are marked `not listed`; document requirements in annexes are marked `DRD`; Q-ST-80C 6.2.9.* are `transversal` (security, applied whatever the category). These need a human look in Phase 1.
- ECSS-E-ST-20-07C clause 5 (EMC test methods) and ESCC 3901 clauses 5 to 12 (manufacturing and qualification tests of the cable) were judged **not** harness design requirements; the reason is in `overrides.csv` (`note`). This is a judgement. Please say if you want any of them back in scope.
- The extraction is automatic and was spot-checked, not proved. Requirement text is abbreviated; the PDF is authoritative.

## Proposed software criticality category: **C**

ECSS-Q-ST-80C Table D-1 ties the category to the highest-severity function the software is involved in and to compensating provisions. The severity categories I to IV are defined in ECSS-Q-ST-30, which was **not supplied**, so the reasoning below uses the Table D-1 wording only and needs your confirmation.

Reasoning:

1. The tool produces wire lists, pinouts and drawings from which a flight harness is built. A wrong output can reach flight hardware, and a harness fault may be severe (the tool is involved in functions that could be category I or II).
2. The tool is not in the spacecraft's control loop and nothing it does acts on flight hardware directly.
3. Compensating provisions exist: independent verifiers in the tool, human design review and release, and the manufacturing inspection and electrical test of the real harness (generated test tables). Table D-1 lists "an operational procedure" and "a hardware implementation" as accepted provisions, but they must meet ECSS-Q-ST-30 clause 5.4 and ECSS-Q-ST-40 clause 6.5.6.3, which I could not read.

With compensating provisions, category I functions give **B** and category II functions give **C**. I propose **C**, because the programme can take credit for the inspection and test of the manufactured harness. If you classify harness faults as category I (catastrophic) this becomes **B**; if you cannot credit the compensating provisions it is **A** for category I and **B** for category II. The choice changes the amount of work substantially (the applicability tables differ per category).

**Decision needed:** confirm C, or give the category (A, B, C or D) and, if you can, the ECSS-Q-ST-30 severity of harness faults.

## Premise correction

The brief assumed the tool builds on WireViz and Graphviz. It does not: it is a clean-room tool (`CLAUDE.md`), and WireViz YAML is only an *export* format. Graphviz is not used. WireViz itself is not touched. The reuse file should therefore cover the real dependencies (PySide6/Qt, pydantic, openpyxl, defusedxml, PyInstaller and the others listed by `python -m tools.gen_sbom`) and treat WireViz only as an export target.

## Baseline tests

Result before any change: `compliance/evidence/baseline_tests.txt`.
