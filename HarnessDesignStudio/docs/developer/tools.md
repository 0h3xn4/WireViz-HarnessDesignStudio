# The scripts in `HarnessDesignStudio/tools/`

This page lists every script in `HarnessDesignStudio/tools/` with what it does, so that you can tell which one to run; the first line of each script's own docstring is the source of the descriptions.

Run them from the `HarnessDesignStudio/` folder with the development environment active (see [`setup-and-tests.md`](setup-and-tests.md)), as `python -m tools.NAME`. Some need extra setup (Docker, network access, the standards' PDFs); the notes say so.

## Contents

- [Keep generated files up to date](#keep-generated-files-up-to-date)
- [Pictures](#pictures)
- [Build and release](#build-and-release)
- [Checks and measurements](#checks-and-measurements)
- [Compliance records](#compliance-records)
- [Usability sessions](#usability-sessions)

## Keep generated files up to date

A test fails when one of these outputs is stale. The table of outputs and tests is in [`docs-maintenance.md`](docs-maintenance.md).

| Script | What it does |
| --- | --- |
| `gen_cli_docs` | Writes `docs/CLI.md` (every `harness-design-studio` command with its arguments and examples) from the argument parser |
| `gen_rule_docs` | Writes `docs/RULES.md` (every design rule: what, why, how to fix, severity) |
| `build_guide` | Builds the offline user guide: `docs/guide/USER_GUIDE.md` to the HTML that opens with **F1** |
| `build_examples` | Rebuilds the example projects shipped with the tool (`harness-design-studio new --list`) |
| `build_prototype` | Assembles the single-file clickable prototype from the design tokens |
| `gen_output_goldens` | Regenerates the golden output digests on purpose. Review the diff. |

## Pictures

| Script | What it does |
| --- | --- |
| `gui_screenshots` | Renders 26 screenshots of the real editor (offscreen) into `docs/ux/qt`: the sample project and the views and dialogs on the flatsat example (about a minute) |
| `flatsat_screenshots` | Pictures of the flatsat diagram in the editor (overview and one unit in focus), for `docs/FLATSAT_EXAMPLE.md` and the README |
| `ux_screenshots` | Screenshots of the prototype's key screens into `docs/ux/screens` (needs Playwright; history only) |

## Build and release

| Script | What it does |
| --- | --- |
| `release_check` | Runs the release checklist and writes `dist/release-docs/release-report.md` ([`release.md`](release.md)) |
| `build_installer` | Builds a self-contained, offline package with PyInstaller (one folder) and archives it; fails when the package holds code other than the standard library and the declared runtime dependencies |
| `build_deb` | Builds the `.deb` from `dist/harness-design-studio` (run `build_installer` first) |
| `check_reproducible` | Builds the wheel twice with a fixed `SOURCE_DATE_EPOCH` and requires identical hashes |
| `vendor` | Downloads every pinned wheel into a local folder for offline installs (run on a connected host) |
| `gen_sbom` | Writes a CycloneDX software bill of materials and a licence report for the runtime dependencies |
| `licence_report` | Licence report for the installed runtime dependencies; fails on anything outside the allow-list |
| `collect_licences` | Collects the licence texts of the shipped runtime packages into a `LICENSES` folder |
| `check_vulnerabilities` | Checks the shipped dependencies for known vulnerabilities (needs network access) |
| `gen_scf` | Writes the software configuration file and the `SHA256SUMS` of a delivery |
| `release_notes` | Checks that a release tag fits the version and the changelog and writes the text of the GitHub release page (used by `.github/workflows/release.yml`) |

## Checks and measurements

| Script | What it does |
| --- | --- |
| `bench_gui` | Times editor interactions on a stress-size project (offscreen) |
| `bench_stress` | Times load, save, integrity check and transactions on a stress-size project (200 units, 2,000 interfaces) |
| `bench_generate` | Times generation on the stress project (target: under 10 seconds) |
| `soak` | Soak test: thousands of random editing steps through the command layer, checking the invariants all the way |

## Compliance records

| Script | What it does |
| --- | --- |
| `extract_requirements` | Extracts the requirements of the five standards into `compliance/requirements/*.csv` (needs the standards' PDFs, which are not in the repository, and `pdftotext`) |
| `build_compliance_matrix` | Builds `compliance/compliance_matrix.csv` from the requirement lists and the assessments |
| `trace` | Builds `compliance/traceability.csv`: tool requirement to source, verifying files and the tests that name it |
| `gen_sdd_components` | Builds `compliance/sdd_components.csv`: the components of the design and the requirements they serve (every module needs a docstring) |
| `metrics` | Basic software metrics (`compliance/metrics.json`) |

## Usability sessions

| Script | What it does |
| --- | --- |
| `usability_setup` | Creates the material for the usability tasks T1 to T8 in a folder ([`../usability/README.md`](../usability/README.md)) |
| `usability_summary` | Summarises usability sessions: success, time, wrong clicks, SUS score and the priority bugs |

Next: [`docs-maintenance.md`](docs-maintenance.md), [`release.md`](release.md).
