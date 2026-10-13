# Release report

- PASS: Versions agree (pyproject, package, changelog) (0 s): __init__ 0.1.0rc8, pyproject 0.1.0rc8, CHANGELOG 0.1.0rc8
- PASS: Lint and types (0 s): ruff format, ruff check, mypy --strict clean
- PASS: Verifier clean on the reference projects (2 s): verifier and output verifier clean on mini3, sat15, sat15_full
- PASS: Performance targets on the stress project (58 s): stress project: generate 3.6 s (limit 10), verify 0.8 s, rules 1.4 s, outputs 33 s + check 19 s
- PASS: Soak test (3,000 random steps) (254 s): 3000 steps (1986 applied, 1014 rejected), 168 generations, 60 save/load round trips: all invariants held
- PASS: Fuzzing and security tests (300 examples per target) (60 s): 32 passed in 59.79s
- PASS: Test suite and coverage gate (520 s): =========================== short test summary info ============================ | SKIPPED [1] tests/test_atomic_lock.py:59: needs POSIX non-root | 964 passed, 1 skipped in 515.95s (0:08:35)
- PASS: Test suite without instrumentation (395 s): =========================== short test summary info ============================ | SKIPPED [1] tests/test_atomic_lock.py:59: needs POSIX non-root | 964 passed, 1 skipped in 391.80s (0:06:31)
- PASS: SBOM and licence report (18 s): 11 packages, 0 rejected
- PASS: Known vulnerabilities in the dependencies (1 s): no known vulnerabilities in 10 packages
- PASS: Reproducible wheel (4 s): wheel builds identically twice
- PASS: Package (tar.gz, deb) and self-test (94 s): tarball and deb built; selftest ok
- PASS: Installed package runs (deb extracted) (3 s): extracted deb runs: selftest ok; harness 0.1.0rc8; examples present
- PASS: Configuration file and SHA-256 of the deliverables (0 s): 0.1.0rc8: 597 source files, 2 deliverables, integrity e9dadb0a75f3ac372bd3b2a8aa2181b3d89288bd2360e4fc87bb1ba81bd70e9c
