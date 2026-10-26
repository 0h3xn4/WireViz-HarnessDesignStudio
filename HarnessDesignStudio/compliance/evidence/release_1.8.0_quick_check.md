# Release report

- PASS: Versions agree (pyproject, package, changelog) (0 s): __init__ 1.8.0, pyproject 1.8.0, CHANGELOG 1.8.0
- PASS: Lint and types (1 s): ruff format, ruff check, mypy --strict clean
- PASS: Verifier clean on the reference projects (12 s): verifier and output verifier clean on mini3, sat15, sat15_full
- SKIPPED: Performance targets on the stress project
- SKIPPED: Soak test (3,000 random steps)
- SKIPPED: Fuzzing and security tests (300 examples per target)
- SKIPPED: Test suite and coverage gate
- SKIPPED: Test suite without instrumentation
- SKIPPED: SBOM and licence report
- SKIPPED: Known vulnerabilities in the dependencies
- SKIPPED: Reproducible wheel
- SKIPPED: Package (tar.gz, deb) and self-test
- SKIPPED: Installed package runs (deb extracted)
- SKIPPED: Configuration file and SHA-256 of the deliverables
