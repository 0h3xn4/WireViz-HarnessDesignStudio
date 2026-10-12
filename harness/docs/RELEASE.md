# Release checklist (Ubuntu 24.04 and newer, D-127)

This is the procedure for releasing the **tool** (a product release: a new version of Harness Design Studio). It is not how you release a harness in a project; that is described in the [user guide](guide/USER_GUIDE.md), section 9 (Review, release and revisions), and in [`HOWTO.md`](HOWTO.md).

Run `python -m tools.release_check` on the build host (Ubuntu 24.04; with Docker use `packaging/ubuntu/container/`). It performs the automated steps (1 to 11, with 7a, 8a and 11a) and writes `dist/release-docs/release-report.md`. Steps 12 to 15 are for people. Two different numbers are called "14" elsewhere in the records: the release check runs **14 automated steps** (1 to 11 plus 7a, 8a and 11a), whereas **step 14** is the owner's sign-off, a single step done by a person.

1. Versions agree in `pyproject.toml`, `harness_design_studio/__init__.py` and the top of `CHANGELOG.md` (the changelog entry says what changed and what is still open). Changes made after a release are collected under `## Unreleased`; at the next release rename that heading to the new version, and the check skips it until then.
2. `ruff format --check`, `ruff check` and `mypy --strict` are clean.
3. The independent verifiers are clean on `mini3`, `sat15` and `sat15_full`.
4. Performance targets on the stress project: generation under 10 s, no design rule errors; export and checks complete.
5. Fuzzing and security tests pass (`HARNESS_FUZZ_EXAMPLES=5000 pytest tests/test_fuzz.py` for the long search; findings in `docs/SECURITY.md`).
6. Soak test: 3,000 random editing steps with all invariants held (`python -m tools.soak 5000 <seed>` for the long run).
7. The full test suite passes with the 90% core coverage gate (docs, goldens, GUI journeys and accessibility audit included).
7a. The same suite passes again **without** coverage instrumentation (ECSS-Q-ST-80C 6.2.3.8); the release report keeps both results.
8. `python -m tools.gen_sbom` writes `sbom.cdx.json` and `licence-report.md` with nothing rejected (needs the wheelhouse from `python -m tools.vendor`, or network access, on the build host).
8a. `python -m tools.check_vulnerabilities`: no known vulnerabilities in the shipped dependencies (needs network access on the build host; output in `vulnerability-report.txt`). If the scan cannot run, the release check fails.
9. `python -m tools.check_reproducible`: the wheel builds identically twice.
10. `python -m tools.build_installer` then `python -m tools.build_deb`; `dist/harness-design-studio/harness-design-studio --selftest` prints `selftest ok` (generates, exports and verifies a project, starts the rule check helper process and creates a project from a bundled example, all inside the package).
11. The `.deb` is extracted with `dpkg-deb -x`; its program runs the self-test and its `harness new --list` shows the examples.
11a. `python -m tools.gen_scf` writes `scf.json` (version, commit, dependencies, SHA-256 of every source file, integrity value) and `SHA256SUMS` of the deliverables into `dist/release-docs`. Hand `SHA256SUMS` to the recipient; they check with `sha256sum -c SHA256SUMS` (ECSS-Q-ST-80C 6.2.4.10, 6.2.4.11).
12. *(Waived by the owner on 2026-10-09, `compliance/DEVIATIONS.md` T-30.)* Run the self-test on a clean Ubuntu VM with networking disabled, installing with `sudo apt install ./harness-design-studio_<version>_amd64.deb` and, separately, with `./install.sh` from the tarball.
13. *(Waived by the owner on 2026-10-09, `compliance/DEVIATIONS.md` T-27.)* Usability sessions held and triaged (`docs/usability/README.md`); priority bugs fixed or accepted by the owner in writing.
14. *(Not waived; only the owner can give it. Given for `0.1.0rc8` on 2026-10-09 with D-10, D-11, D-12 and D-15 still open: `compliance/SIGNOFF.md`; the condition on the open decisions was waived for 0.1.0 on 2026-10-09, `compliance/DEVIATIONS.md` T-31.)* Owner sign-off, including the open decisions D-10 and D-15, and confirmation that D-11 (derating and EMC values) and D-12 (approved parts list) have been supplied (see `docs/OPEN_DECISIONS.md`; D-20 is not needed). Remove `rcN` from the version only after sign-off.

15. *(A person's step, like 12 to 14.)* After the pull request is merged and CI is green on the merge commit: create the annotated tag `vX.Y.Z` on the merge commit (its message says which decisions are open and points to `compliance/SIGNOFF.md`), push it, and publish the release page with the same wording. Attach the `.tar.gz`, the `.deb` and the `SHA256SUMS` of that build, and compare the checksums with `compliance/evidence/release_X.Y.Z_SHA256SUMS`. Packages built by CI are built again on another machine, so their bytes can differ from the recorded ones; in that case say so in the release notes and use the `SHA256SUMS` that came with them.

Check the documentation too: `docs/GETTING_STARTED.md` must still work word for word on the release candidate (the tests run its commands on the example project, but read it once as a newcomer would). Do not release while any step fails. A release candidate with open decisions is labelled `rc` and says so in its changelog.
