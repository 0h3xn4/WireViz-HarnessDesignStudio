# Criticality classification of the software and its components

Addresses ECSS-Q-ST-80C 5.4.4, 6.2.2.1 to 6.2.2.10, 6.2.3.1 to 6.2.3.8 (gap G-03). Status: the plan and the component classification are approved by the owner on 2026-10-08 (approval given in the working session; the owner is also customer and supplier, so no independent reviewer, see A-01); product category **C approved by the owner** (conversation of 2026-10-08, recorded in `PHASE0.md`). The component classification below is **proposed** and needs the owner's approval.

## 1. Product category

Category **C**. Basis: ECSS-Q-ST-80C Table D-1: software involved in category II functions with compensating provisions is category C (software involved in category I functions with compensating provisions would be B). The severity categories I to IV of ECSS-Q-ST-30 and the rules of ECSS-Q-ST-40 clause 6.5.6.3 were not supplied; the compensating provisions credited are the independent verifiers inside the tool, the human design review and release of every harness, and the inspection and electrical test of the manufactured harness.

## 2. Components

Clause 6.2.2.10: if it cannot be prevented that components cause failures of higher criticality components (failure propagation, shared resources), all involved components take the highest category among them. The product category is the ceiling; no component is above C.

| Component (path) | What it does | Category | Reason |
| --- | --- | --- | --- |
| `core/generate`, `core/verify.py` | decides connectors, pins, wires and checks them independently | C | a wrong result reaches the harness definition |
| `core/drc` | design rule check | C | a missed finding reaches the harness definition |
| `core/outputs` and its verifier | wire lists, pinouts, drawings, labels, test tables | C | these are what is built from |
| `core/vcs`, `core/io`, `core/model`, `core/commands.py` | release, baselines, files, model, undo | C | corruption or a wrong release state is carried into outputs |
| `core/units.py`, `core/generate/sizing.py` | unit conversion, wire sizing | C | numerical results used for sizing |
| `core/edit.py`, `core/checks.py`, `core/imports.py`, `core/kicad.py`, `core/library_import.py` | editing, logical checks, imports | C | wrong input is passed on; imports are previewed and verified |
| `cli` | commands | C | exposes the above |
| `gui` | editor | D | display and input only; propagation to C components is prevented because every change goes through the transaction layer, the integrity check and the verifiers (6.2.2.10); the owner is asked to confirm this reasoning |
| `resources/examples`, `resources/guide` | examples and help text | D | learning material; labelled demo values |
| `tools/` | build, release, documentation tools | D | not delivered to users except `release_check` evidence; failures show up in the release checks |
| `tests/` | verification | C | a wrong test hides a defect (treated like the code it checks) |

## 3. Measures for critical software (6.2.3.2, 6.2.3.3)

Defined measures, all applied to C components: the independent verifier (no shared code with the generator; enforced by review only, `tests/test_architecture.py` checks the layering of `core` against `gui` and `cli` and not the verifier independence); mutation tests for every output check; positive and negative tests for every rule (`tests/test_drc.py`); property and soak tests (`tests/test_soak.py`); strict typing (`mypy --strict`); deterministic outputs with golden files; "not checked" instead of silence when data are missing. Regression testing is the full suite (6.2.3.4, run after every change in CI); validation tests are run on the uninstrumented code (6.2.3.8: CI runs `pytest --cov`, which instruments the code; the baseline and final runs of this audit were done without coverage, and the release check should run the suite once without `--cov`: open action A-09).

## 4. Dependability analysis (6.2.2.2 to 6.2.2.9)

Not done as a formal analysis. A software failure mode review of the C components is a task for the safety side of the owner's project; it needs the system-level analyses (ECSS-Q-ST-30/40) that were not supplied. Listed as open action A-07; the input sheet with the proposed failure modes is `../templates/dependability_input_sheet.md`.
