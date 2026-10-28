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
| `gui_screenshots` | Renders 26 screenshots of the real editor (offscreen, as the Electrical / AIT engineer) into `docs/ux/qt`: the sample project and the views and dialogs on the flatsat example (about a minute) |
| `ui_screenshots` | Pictures of every area, tab, panel, menu and dialog of the editor on the flatsat example, in the light and the dark theme (offscreen), for the UI overhaul: `python -m tools.ui_screenshots OUT`. The sets are `docs/ui/screenshots/before/` (release 1.2.0) and `docs/ui/screenshots/after/` (release 1.3.0), compared in [`../ui/BEFORE_AFTER.md`](../ui/BEFORE_AFTER.md). **Always give a folder:** without one the script writes into `docs/ui/screenshots/before/`, the 1.2.0 baseline. It runs each theme and part (`--theme light\|dark`, `--part main\|extra`) in a process of its own, because two themes in one process crash Qt's offscreen platform; one picture that fails is listed at the end and does not stop the others |
| `flatsat_screenshots` | Pictures of the flatsat diagram in the editor (overview and one device in focus), for `docs/FLATSAT_EXAMPLE.md` and the README |
| `tab_screenshots` | Fifteen pictures for the user manual, in `docs/img` (`python -m tools.tab_screenshots [OUT]`, offscreen): the *Edit wire* tab with a wire selected, the *Devices* tab and the *Connectors* tab of a harness made by hand (1760 x 1000, Systems engineer role), the three Next step pictures and the windows of the two roles, `systems-engineer.png` and `electrical-engineer.png` (1440 x 900), the *Accessories* tab, and the Export window before and after an export (1.7.0), and, since milestone M1 of D-172, the *Add device* window with a name typed and the *View* menu with *Show problem notices* (`add-device-dialog.png`, `problem-notices-setting.png`), and, since milestone M2 (D-173), the *Link connectors* window and the diagram with two connections beside the *Connections* group of the tree (`link-connectors-window.png`, `connections-diagram.png`, on a small three-device project with named pins built in the tool), and, since milestone M5 (D-176), the question of the first start and the View menu with the Role submenu (`role-question.png`, `role-menu.png`; `python -m tools.tab_screenshots OUT roles` makes only the pictures that show a role); the last run took about 7 minutes on a machine that was also busy with other work |
| `ux_screenshots` | Screenshots of the prototype's key screens into `docs/ux/screens` (needs Playwright; history only) |

## Build and release

| Script | What it does |
| --- | --- |
| `release_check` | Runs the release checklist and writes `dist/release-docs/release-report.md` ([`release.md`](release.md)) |
| `build_installer` | Builds a self-contained, offline package with PyInstaller (one folder) and archives it; fails when the package holds code other than the standard library and the declared runtime dependencies |
| `build_deb` | Builds the `.deb` from `dist/harness-design-studio` (run `build_installer` first) |
| `build_windows` | On Windows: builds the editor and the command line tool with PyInstaller, the portable `.zip` and the Inno Setup installer (`packaging/windows/`); signs when `HARNESS_SIGN_PFX` is set |
| `make_icons` | Draws the logo of `gui/appicon.py` offscreen into an `.ico` (Windows) or a PNG |
| `smoke_package` | Tests a finished Windows setup program or `.zip` (`windows-setup FILE`, `windows-zip FILE`): install, run the command line walk-through (bytes compared with the source install) and the editor's `--selftest`, uninstall. `folder DIR` runs the program checks on an unpacked program folder, Linux or Windows. The programs run without any Python in their environment (D-167) |
| `check_reproducible` | Builds the wheel twice with a fixed `SOURCE_DATE_EPOCH` and requires identical hashes |
| `vendor` | Downloads every pinned wheel into a local folder for offline installs (run on a connected host) |
| `gen_sbom` | Writes a CycloneDX software bill of materials and a licence report for the runtime dependencies |
| `licence_report` | Licence report for the installed runtime dependencies; fails on anything outside the allow-list |
| `collect_licences` | Collects the licence texts of the shipped runtime packages, and of the bundled fonts (Inter, JetBrains Mono) and icons, into a `LICENSES` folder; fails when a licence text is missing |
| `check_vulnerabilities` | Checks the shipped dependencies for known vulnerabilities (needs network access) |
| `gen_scf` | Writes the software configuration file and the `SHA256SUMS` of a delivery |
| `release_notes` | Checks that a release tag fits the version and the changelog and writes the text of the GitHub release page: download table, highlights from `docs/releases/<version>.md`, folded changelog, install steps, checksums (used by `.github/workflows/release.yml`) |

## Checks and measurements

| Script | What it does |
| --- | --- |
| `bench_gui` | Times editor interactions on a stress-size project (offscreen) |
| `ui_perf` | Start-up, tab switch, theme switch, interface size and selection timings of the editor on the flatsat example (offscreen; no arguments). The numbers of 1.2.0 and 1.3.0 are in [`../ui/PERF_BASELINE.md`](../ui/PERF_BASELINE.md) |
| `output_hashes` | The SHA-256 of every file the tool writes for each of the four packaged examples (a workbook by its members), to show that a change of the interface left the written files alone: `--check docs/ui/OUTPUT_HASHES_1.2.0.json` compares with release 1.2.0 (apart from the version stamp), `--write FILE` stores, no argument prints. It writes the examples with the harness drawings on (as the reference was made) and leaves out of the comparison a file kind that did not exist in 1.2.0, the build workbook `*_build.xlsx`. `tests/test_output_hashes.py` runs the comparison. Run it after any change in `gui/` that could reach a writer |
| `bench_stress` | Times load, save, integrity check and transactions on a stress-size project (200 devices, 2,000 interfaces) |
| `bench_generate` | Times generation on the stress project (target: under 10 seconds) |
| `bench_incremental` | What one edit costs on a project of 200 devices (`History.execute`, with the integrity checks it runs), what the autosave journal costs the GUI thread and how long it takes to reach the disk, the export of the flatsat example and the memory an undo step keeps. Medians of `--repeat` runs (default 5); run it three times on a shared machine. The numbers of release 1.9 are in [`../ui/PERF_BASELINE.md`](../ui/PERF_BASELINE.md) |
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
