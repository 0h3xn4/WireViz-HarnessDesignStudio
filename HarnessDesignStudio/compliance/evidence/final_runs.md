# Final runs of the audit

| Run | Command | Result |
| --- | --- | --- |
| Baseline, before any change | `pytest -q` | 839 passed, 1 skipped (`baseline_tests.txt`) |
| After the design-check features | `pytest -q` | 902 passed, 1 skipped (`after_phase2b_tests.txt`) |
| With coverage, first attempt | `pytest -q --cov` | 906 passed, 1 skipped, 1 failed: `test_loading_a_stress_project_is_reasonable` exceeded its 5 s limit under instrumentation on this machine (`after_phase2_coverage_run.txt`) |
| Final, without instrumentation (ECSS-Q-ST-80C 6.2.3.8) | `pytest -q` | **910 passed, 1 skipped** |
| Final, with coverage as CI runs it (`HARNESS_TIME_FACTOR=3`) | `pytest -q --cov` | **910 passed, 1 skipped**; core coverage 96.63 % statements, 93.16 % branches (95.62 % combined, gate 90 %) |

The skipped test needs a non-root user. Static checks (`ruff check`, `ruff format --check`, `mypy --strict`) were clean on every commit of the branch.
