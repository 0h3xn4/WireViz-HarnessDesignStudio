# Software verification report (SVR)

DRD: ECSS-E-ST-40C Annex M. Covers the compliance audit (October 2026). Status: draft, not reviewed; produced by the developer assistant, **not independent** (action A-01).

## 1 to 3. Introduction, references, terms
`SVerP.md`.

## 4. Verification activities, reporting and monitoring
### 4.1 General
Evidence is stored in `../evidence/`. Dates are not recorded in generated data; the commits on the branch `compliance/ecss-esccc-audit` identify the states.

### 4.2 Software related system requirements process
The owner's needs are in `../../docs/SPEC.md`. The system-level requirement baseline (SSS) does not exist; verification not possible (G-01, A-02).

### 4.3 Requirements and architecture engineering
- 4.3.1 Traceability: `../traceability.csv`, 89 requirements; each names verifying files; 47 are named in at least one test, the rest by file only or by review (`REQ-I18N-01`); `tests/test_trace.py` fails if a requirement has neither a file that exists nor a review. A trace from requirement to design component is not complete (A-10).
- 4.3.2 Feasibility: demonstrated by the working tool.

### 4.4 Design and implementation engineering
- Static analysis: `ruff check`, `ruff format --check`, `mypy --strict` clean on each commit of the branch.
- Tests: baseline 839 passed, 1 skipped; after Phase 2b 902 passed, 1 skipped; final 910 passed, 1 skipped with and without coverage (4.7).
- Unit and integration test results: `../evidence/baseline_tests.txt`, `after_phase2b_tests.txt`, `after_phase2_coverage_run.txt`.
- Code coverage (ECSS-E-ST-40C 0860135, value agreed with the owner: 90 % on `core`): see `../metrics.json` for the final figures (core: 96.63 % statements, 93.16 % branches) (`../metrics.json`). The GUI is outside the measure.
- Generated outputs before and after: `../evidence/output_comparison.md` (592 of 595 identical; 3 DRC reports differ by design).

### 4.5 Delivery and acceptance
`python -m tools.gen_scf` produced `scf.json` and `SHA256SUMS` (`SCF.md`). Package build and self-test were run in earlier releases; not re-run in this audit (no packaging code changed except the added step in `tools/release_check.py`).

### 4.6 Validation process verification
Validation has not been executed by an independent person (`SValP_SVS.md`, A-01, A-12, A-13).

### 4.7 Quality requirements verification
- Problem found in this verification: `tests/test_gui_perf.py::test_loading_a_stress_project_is_reasonable` exceeded its 5 s limit once in the run with coverage instrumentation on this machine and passes alone (about 1.5 s) and in the run without instrumentation. The CI sets `HARNESS_TIME_FACTOR=3` for this reason. Not a regression of this audit (no code on that path changed); the final run with the factor set and the final run without instrumentation both pass (910 passed, 1 skipped; `../evidence/final_runs.md`).
- Problem found and corrected in the audit tools: the requirement extractor flagged two table requirements as deleted (30-11C 0140051, 0140058); corrected and recorded in `../gap_analysis.md`.

## 5. Margin and technical budget status
Editor edit time against the 100 ms target and generation time against 10 s: `../../tools/bench_gui.py`, `../../tools/bench_generate.py`, `../../tests/test_gui_perf.py`. The audit added no code to the edit path.

## 6. Numerical accuracy analysis
`../../tests/test_numerics.py` (REQ-NUM-01): AWG diameter and area against the defining points of the AWG scale; voltage drop and ampacity arithmetic against exact rational arithmetic. Result: the float arithmetic agrees to better than 1e-5 relative (the printed precision) and the AWG scale to 1e-12.

## 7. Interface timing analysis
Not applicable: no real-time interfaces.
