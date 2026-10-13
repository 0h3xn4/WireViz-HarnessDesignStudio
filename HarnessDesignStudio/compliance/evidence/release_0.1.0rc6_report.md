# Release report

- PASS: Versions agree (pyproject, package, changelog) (0 s): __init__ 0.1.0rc6, pyproject 0.1.0rc6, CHANGELOG 0.1.0rc6
- PASS: Lint and types (0 s): ruff format, ruff check, mypy --strict clean
- PASS: Verifier clean on the reference projects (2 s): verifier and output verifier clean on mini3, sat15, sat15_full
- PASS: Performance targets on the stress project (60 s): stress project: generate 3.6 s (limit 10), verify 0.9 s, rules 1.4 s, outputs 34 s + check 18 s
- PASS: Soak test (3,000 random steps) (265 s): 3000 steps (1986 applied, 1014 rejected), 168 generations, 60 save/load round trips: all invariants held
- PASS: Fuzzing and security tests (300 examples per target) (64 s): 32 passed in 63.82s (0:01:03)
- PASS: Test suite and coverage gate (509 s): =========================== short test summary info ============================ | SKIPPED [1] tests/test_atomic_lock.py:59: needs POSIX non-root | 952 passed, 1 skipped in 505.47s (0:08:25)
- PASS: Test suite without instrumentation (392 s): =========================== short test summary info ============================ | SKIPPED [1] tests/test_atomic_lock.py:59: needs POSIX non-root | 952 passed, 1 skipped in 388.47s (0:06:28)
- PASS: SBOM and licence report (16 s): 11 packages, 0 rejected
- PASS: Known vulnerabilities in the dependencies (1 s): no known vulnerabilities in 10 packages
- PASS: Reproducible wheel (4 s): wheel builds identically twice
- PASS: Package (tar.gz, deb) and self-test (97 s): tarball and deb built; selftest ok
- PASS: Installed package runs (deb extracted) (4 s): extracted deb runs: selftest ok; harness 0.1.0rc6; examples present
- PASS: Configuration file and SHA-256 of the deliverables (0 s): 0.1.0rc6: 591 source files, 2 deliverables, integrity 863ae47839811ab94f64da063db188ded094ebc0f8e5bfd551db46c8eb202ff6
