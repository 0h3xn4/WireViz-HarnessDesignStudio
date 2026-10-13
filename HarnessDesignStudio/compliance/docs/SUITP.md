# Software unit and integration test plan (SUITP)

DRD: ECSS-E-ST-40C Annex K. Status: draft, not reviewed.

## 1 to 4. Introduction, references, terms, overview
See `SDP.md`.

## 5. Unit and integration testing
- **Organization, schedule, resources, responsibilities:** automated, run by CI on every push (`.github/workflows/harness-ci.yml`) and by the developer before every commit.
- **Tools, techniques, methods:** pytest with hypothesis (property tests), pytest-qt (GUI offscreen), fixtures in `tests/fixtures/`, golden files for outputs.
- **Personnel and training:** none specific.
- **Risks and contingencies:** timing tests on slow machines; limits scale with `HARNESS_TIME_FACTOR` (CI sets 3); counting tests replace timing where possible.

## 6. Control procedures
Failing tests block a release (`../../docs/RELEASE.md`).

## 7. Approach
- **Strategy:** every function that holds logic has unit tests; modules are integrated in tests that run the whole chain (generate, check, export, verify), for example `tests/test_generate.py` and `tests/test_outputs.py`; the GUI journeys test the editor end to end offscreen.
- **Items and features tested:** all of `core`, `cli`, and the editor controller and panels. **Not tested:** pixel-exact rendering, the OS integration of the installed package beyond the self-test.
- **Pass/fail criteria:** all tests pass; coverage of `core` at least 90 % (statement and branch), enforced by `pyproject.toml`.
- **Generated code:** none.

## 8 to 10. Test design, cases, procedures
One test function is one test case; its name and docstring state the purpose, and the requirement ID it serves where there is one. Inputs are in the test or in `tests/fixtures`; expected outputs are asserted in the test. The procedure is `pytest` (all tests) or `pytest tests/<file>`. The list of test cases is the output of `pytest --collect-only -q` (the 906 collected tests at the time of writing, plus the long runs `HARNESS_FUZZ_EXAMPLES=5000 pytest tests/test_fuzz.py` and `python -m tools.soak 5000 <seed>`).

## 11. Additional information
`../traceability.csv` links requirements to the test files.
