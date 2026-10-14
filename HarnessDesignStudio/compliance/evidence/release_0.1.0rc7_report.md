# Release report

- PASS: Versions agree (pyproject, package, changelog) (0 s): __init__ 0.1.0rc7, pyproject 0.1.0rc7, CHANGELOG 0.1.0rc7
- PASS: Lint and types (0 s): ruff format, ruff check, mypy --strict clean
- PASS: Verifier clean on the reference projects (2 s): verifier and output verifier clean on mini3, sat15, sat15_full
- PASS: Performance targets on the stress project (57 s): stress project: generate 3.4 s (limit 10), verify 0.8 s, rules 1.1 s, outputs 33 s + check 18 s
- PASS: Soak test (3,000 random steps) (244 s): 3000 steps (1986 applied, 1014 rejected), 168 generations, 60 save/load round trips: all invariants held
- PASS: Fuzzing and security tests (300 examples per target) (58 s): 32 passed in 57.94s
- PASS: Test suite and coverage gate (485 s): =========================== short test summary info ============================ | SKIPPED [1] tests/test_atomic_lock.py:59: needs POSIX non-root | 957 passed, 1 skipped in 481.79s (0:08:01)
- PASS: Test suite without instrumentation (382 s): =========================== short test summary info ============================ | SKIPPED [1] tests/test_atomic_lock.py:59: needs POSIX non-root | 957 passed, 1 skipped in 378.43s (0:06:18)
- PASS: SBOM and licence report (10 s): 11 packages, 0 rejected
- PASS: Known vulnerabilities in the dependencies (1 s): no known vulnerabilities in 10 packages
- PASS: Reproducible wheel (4 s): wheel builds identically twice
- PASS: Package (tar.gz, deb) and self-test (87 s): tarball and deb built; selftest ok
- PASS: Installed package runs (deb extracted) (3 s): extracted deb runs: selftest ok; harness 0.1.0rc7; examples present
- PASS: Configuration file and SHA-256 of the deliverables (0 s): 0.1.0rc7: 594 source files, 2 deliverables, integrity 465246128b16242538143ea2a01c93c3ef5e5ed67258b66e0b01e982d64b43dc
