# Release report

- PASS: Versions agree (pyproject, package, changelog) (0 s): __init__ 0.1.0, pyproject 0.1.0, CHANGELOG 0.1.0
- PASS: Lint and types (1 s): ruff format, ruff check, mypy --strict clean
- PASS: Verifier clean on the reference projects (2 s): verifier and output verifier clean on mini3, sat15, sat15_full
- PASS: Performance targets on the stress project (63 s): stress project: generate 2.8 s (limit 10), verify 1.1 s, rules 1.6 s, outputs 36 s + check 20 s
- PASS: Soak test (3,000 random steps) (291 s): 3000 steps (1986 applied, 1014 rejected), 168 generations, 60 save/load round trips: all invariants held
- PASS: Fuzzing and security tests (300 examples per target) (65 s): 32 passed in 63.90s (0:01:03)
- PASS: Test suite and coverage gate (562 s): =========================== short test summary info ============================ | SKIPPED [1] tests/test_atomic_lock.py:59: needs POSIX non-root | 964 passed, 1 skipped in 557.64s (0:09:17)
- PASS: Test suite without instrumentation (432 s): =========================== short test summary info ============================ | SKIPPED [1] tests/test_atomic_lock.py:59: needs POSIX non-root | 964 passed, 1 skipped in 428.57s (0:07:08)
- PASS: SBOM and licence report (10 s): 11 packages, 0 rejected
- PASS: Known vulnerabilities in the dependencies (1 s): no known vulnerabilities in 10 packages
- PASS: Reproducible wheel (5 s): wheel builds identically twice
- PASS: Package (tar.gz, deb) and self-test (93 s): tarball and deb built; selftest ok
- PASS: Installed package runs (deb extracted) (3 s): extracted deb runs: selftest ok; harness 0.1.0; examples present
- PASS: Configuration file and SHA-256 of the deliverables (2 s): 0.1.0: 601 source files, 8 deliverables, integrity 41a81fd655023f03569eddece3699976bc791b3aa2f33eacd3970c98b5bd8e15
