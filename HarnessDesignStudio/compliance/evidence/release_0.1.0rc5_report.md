# Release report

- PASS: Versions agree (pyproject, package, changelog) (0 s): __init__ 0.1.0rc5, pyproject 0.1.0rc5, CHANGELOG 0.1.0rc5
- PASS: Lint and types (0 s): ruff format, ruff check, mypy --strict clean
- PASS: Verifier clean on the reference projects (2 s): verifier and output verifier clean on mini3, sat15, sat15_full
- PASS: Performance targets on the stress project (69 s): stress project: generate 2.8 s (limit 10), verify 0.9 s, rules 1.2 s, outputs 40 s + check 23 s
- PASS: Soak test (3,000 random steps) (287 s): 3000 steps (1986 applied, 1014 rejected), 168 generations, 60 save/load round trips: all invariants held
- PASS: Fuzzing and security tests (300 examples per target) (64 s): 32 passed in 63.35s (0:01:03)
- PASS: Test suite and coverage gate (587 s): =========================== short test summary info ============================ | SKIPPED [1] tests/test_atomic_lock.py:59: needs POSIX non-root | 941 passed, 1 skipped in 583.25s (0:09:43)
- PASS: SBOM and licence report (15 s): 11 packages, 0 rejected
- PASS: Reproducible wheel (5 s): wheel builds identically twice
- PASS: Package (tar.gz, deb) and self-test (92 s): tarball and deb built; selftest ok
- PASS: Installed package runs (deb extracted) (4 s): extracted deb runs: selftest ok; harness 0.1.0rc5; examples present
- PASS: Configuration file and SHA-256 of the deliverables (0 s): 0.1.0rc5: 576 source files, 2 deliverables, integrity 91bfd1bcee7144f011ab40c43fdcaf3b38d917b1860794d5777831925a108a1e
