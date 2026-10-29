# Set up a development environment and run the tests

This page shows how to set up a place to work on Harness Design Studio, run the tests and checks that CI runs, and know which tests read the documentation.

## Contents

- [What you need](#what-you-need)
- [1. Set up](#1-set-up)
- [2. Run the tests](#2-run-the-tests)
- [3. Check the style and the types](#3-check-the-style-and-the-types)
- [4. The tests that read the documents](#4-the-tests-that-read-the-documents)
- [The tests of the user interface](#the-tests-of-the-user-interface)
- [The tests of the 1.4.0 and later features](#the-tests-of-the-140-and-later-features)
- [5. Golden files](#5-golden-files)
- [6. What CI runs](#6-what-ci-runs)
- [When something fails](#when-something-fails)

## What you need

- Ubuntu 24.04 or newer, 64-bit, for development and the release check. The tool itself also runs on Windows 10/11 from 1.2.0 (decision D-149 in [`DECISIONS.md`](../DECISIONS.md); macOS was removed after 1.5.0, D-168); the package and the tests for it run on GitHub's Windows runner (`harness-packages.yml`, `harness-platforms.yml`).
- Python 3.14 or newer (`python3.14 --version`; Ubuntu 24.04 does not have it in its archive, `uv python install 3.14` is one way to get it), and Git.
- For Qt, the system libraries `libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0`. CI installs a few more (`libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0`) and `poppler-utils`. On a machine without a screen the tests use Qt's `offscreen` mode, so no display is needed. The apt line was copied from `CLAUDE.md` and the CI file. It was not run for this page, because the libraries were already present on the machine used.
- Work in the `HarnessDesignStudio/` folder. The WireViz code at the repository root is a separate program ([`CONTRIBUTING.md`](../../../CONTRIBUTING.md)).

## 1. Set up

```
cd HarnessDesignStudio
python3.14 -m venv .venv && . .venv/bin/activate
pip install -e ".[gui,dev]"
```

This took about 40 seconds with a network connection and ended without errors. The extras:

| Extra | What it adds |
| --- | --- |
| (none) | The program and its libraries: `pydantic`, `openpyxl`, `defusedxml`. This is all the command line needs. |
| `gui` | `PySide6-Essentials` (Qt), for the editor. |
| `dev` | Test and build tools: `pytest`, `pytest-cov`, `pytest-qt`, `pytest-xdist`, `hypothesis`, `mypy`, `ruff`, `cyclonedx-bom`, `pip-licenses`, `pip-audit`, `pyinstaller`, `playwright`. |

Versions are pinned in `pyproject.toml`. A new dependency needs its name, version and licence recorded in [`DECISIONS.md`](../DECISIONS.md).

Check it:

```
harness-design-studio --version
```

```
harness 1.9.0
```

Start the editor with `harness-design-studio-gui`.

The prototype tests drive a Chromium browser. `playwright` is installed by `dev`, but the browser is not. CI runs `python -m playwright install --with-deps chromium`. Without a browser those tests are skipped.

## 2. Run the tests

```
pytest
```

The whole suite has 4,737 tests in 236 files (`pytest --collect-only -q`, counted on 2026-10-28 for version 1.9.0). A full run with coverage was not repeated for this page, so there is no run time or coverage figure here: CI took about 30 minutes for version 1.1.0 (`CHANGELOG.md`) and the workflow's comment says about 25 minutes on a 4-core machine; a single process takes much longer. Qt runs offscreen by itself, because `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`.

The markers (declared in `pyproject.toml`, and `--strict-markers` is on, so an unknown one is an error):

| Marker | Tests (1.9.0) | Meaning |
| --- | --- | --- |
| `gui` | 1,491 | Needs Qt (run with `QT_QPA_PLATFORM=offscreen`, which `conftest.py` sets). `pytest -m gui` runs only these. |
| `ux` | 33 | Drives the clickable prototype in a Chromium browser (playwright). |
| `perf` | 53 | Asserts a wall-clock limit. CI runs these alone, after the parallel run. A new timing test must carry it, or `tests/test_parallel_safety.py` fails. |
| `slow` | 11 | Needs about 10 s or more on its own (measured on a loaded machine). Pull requests leave these out (`-m "not perf and not slow"`); the run on `master`, the Windows run on `master` and `python -m tools.release_check` run them. Mark a test that takes this long with `@pytest.mark.slow`; a test that is quick on its own does not need it. |

| Command | What it does |
| --- | --- |
| `pytest -q tests/test_docs.py tests/test_docs_links.py` | Only the tests that read the documents (a minute or less). |
| `pytest tests/test_gui_journeys.py` | The editor journeys, driven like a user. |
| `pytest -q tests/test_ui_*.py tests/test_theme_scan.py tests/test_tokens.py tests/test_fonts.py tests/test_output_hashes.py` | The tests of the user interface of 1.3.0 (see [The tests of the user interface](#the-tests-of-the-user-interface)). Some of them carry the `perf` marker, so add `-m "not perf"` for a loaded machine. |
| `pytest --cov` | The tests with coverage. The gate is 90 % on `harness_design_studio.core`; the run prints `Required test coverage of 90.0% reached` and the percentage it reached (not repeated here, it changes). The GUI is outside the measure. |
| `pytest -m "not perf"` | Everything except the timing tests, in one process. |
| `pytest -n auto -m "not perf and not slow"` | What a pull request runs in the parallel step: the suite without the timing tests and without the `slow` ones. |
| `pytest -n auto -m "not perf"` | The suite in parallel, one worker per core (pytest-xdist, D-148). The tests that assert a wall-clock limit carry the marker `perf` and are left out, because a loaded machine makes them fail for no reason. |
| `pytest -m perf` | Those timing tests alone, one at a time, with the default time factor of 2 (each limit twice what the test says; on an idle machine they pass, and on a slow or busy one set `HARNESS_TIME_FACTOR`, see below). Run it after the parallel run; the two commands together are the whole suite. Add `--cov --cov-append` to both when you want one coverage number. |
| `pytest -k wire_colours` | Only tests whose name matches. |
| `HARNESS_TIME_FACTOR=3 pytest tests/test_gui_perf.py` | The speed tests with limits three times as generous. Without the variable every limit is already twice what is written in the test (the factor is 2 by default, so `pytest -m perf` alone passes on an idle machine); on a slow or shared machine raise it. CI sets 3. A failing speed test prints the measured value, the limit and the factor. |
| `HARNESS_FUZZ_EXAMPLES=5000 pytest tests/test_fuzz.py` | The long fuzzing run (the default is 40 examples). |
| `HARNESS_REQUIRE_BROWSER=1 pytest tests/test_prototype.py` | Fail instead of skipping when no Chromium is found. CI sets it. |

Notes:

- A test that needs a normal user (`tests/test_atomic_lock.py`) is skipped when you run as root. Run the suite as a normal user in CI.
- Every bug fix gets a regression test, and tests come first. See the conventions in [`../../CLAUDE.md`](../../CLAUDE.md).
- GUI tests do not have to close their windows: `tests/conftest.py` deletes the top-level widgets a test left open (an autouse fixture). Without it every later test in the process got slower and the process grew to gigabytes.
- Parallel runs: every test must use its own `tmp_path` (never a fixed path such as `/tmp/x`) and must not write into the source tree, because the workers run at the same time. `tests/conftest.py` gives each worker its own settings folder. A new test that asserts a time limit (`time_limit`, `perf_counter`) gets `@pytest.mark.perf`; `tests/test_parallel_safety.py` fails until it has.
- The GUI tests need no screen: `QT_QPA_PLATFORM=offscreen pytest tests/test_gui_journeys.py`.

## 3. Check the style and the types

```
ruff format --check .
ruff check .
mypy
```

```
639 files already formatted
All checks passed!
Success: no issues found in 477 source files
```

(Run on 2026-10-28 for version 1.9.0; the file counts change as files are added.) `ruff format .` rewrites files into the standard layout; run it before you commit. With the pinned ruff (0.16.10) it also formats the code in fenced `python` blocks inside Markdown files under `HarnessDesignStudio/`. A block that is not in ruff's layout fails `ruff format --check .` in CI, so run `ruff format .` after you edit a page that holds Python code. `mypy` runs in strict mode over `src`, `tests` and `tools`. Settings are in `pyproject.toml`: line length 100, rules `E F W I B UP SIM S`.

## 4. The tests that read the documents

A change that only touches Markdown can still break a test. Know these:

| Test file | What it enforces |
| --- | --- |
| `tests/test_docs_links.py` | Every relative link and every `#anchor` in the listed files resolves. The list: `HarnessDesignStudio/README.md`, `CLAUDE.md`, `CHANGELOG.md`, every Markdown file under `docs/` **including all sub-folders** (`user-manual/`, `developer/`, `guide/`, `examples/`, `ui/`, `releases/`, ...) and the templates `README.md`. Links inside code fences are not checked. The anchor rule is GitHub's. |
| `tests/test_docs.py` | The in-app guide (`resources/guide/index.html`) equals what `tools.build_guide` makes from `docs/guide/USER_GUIDE.md`; every `harness-design-studio` command is named in the guide; the buttons the guide names exist in `gui/strings.py`; no paragraph of the guide is longer than 700 characters; `docs/RULES.md` and `docs/CLI.md` equal what their generators write; every config key is in `docs/CONFIG.md`; the commands of `docs/GETTING_STARTED.md` and of `HarnessDesignStudio/README.md` are run in order in a scratch folder with the expected exit codes; the counts and output lines quoted in `docs/examples/README.md` are those of a real run; the model hash quoted in `GETTING_STARTED.md` equals the one the first `export` prints; the **F1** key opens the guide. |
| `tests/test_examples.py` | The example projects equal what `tools.build_examples` writes; the design worksheet names only real device kinds and interface types; the numbers in `docs/FLATSAT_EXAMPLE.md` match the `flatsat` example. |
| `tests/test_compliance_matrix.py`, `test_trace.py`, `test_sdd_components.py`, `test_metrics.py`, `test_scf.py`, `test_family_group_mapping.py`, `test_profiles.py`, `tests/test_drc.py::test_cited_requirements_exist_in_the_extracted_lists` | The generated compliance files are current (matrix, traceability, component table), no matrix row claims compliance, every module has a docstring, and every cited requirement ID exists. |

The repository's root `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md` and `AUDIT.md`, the Markdown files in the root `docs/` and `HarnessDesignStudio/compliance/**/*.md` are not in the link test. Check them with the offline link checker in [`docs-maintenance.md`](docs-maintenance.md#check-the-links).

When only Markdown under `HarnessDesignStudio/` changes, CI runs just the `docs` job: `test_docs.py`, `test_docs_links.py` and the compliance tests above (decision D-138).

## The tests of the user interface

The editor of 1.3.0 (the UI overhaul, D-150 to D-159) has its own tests. All run offscreen and need no screen:

| Tests | What they check |
| --- | --- |
| `tests/test_tokens.py` | The design tokens (`gui/theme/tokens.py`): every text token reaches 4.5:1 on every surface in the light and the dark theme, outlines and the focus ring 3:1, and the diagram category colours stay apart under simulated colour blindness (REQ-UX-01). |
| `tests/test_theme_scan.py` | An AST scan: no `#RRGGBB` colour, `QColor` with numbers, font family or font size is written in `gui/` outside `gui/theme/` (D-150). A new colour is a new token. (`tests/test_ux_foundation.py` checks that no module directly in `gui/` calls `setStyleSheet`.) |
| `tests/test_fonts.py` | The interface uses the bundled Inter and JetBrains Mono, their licence texts ship, nothing is fetched (REQ-UX-04). |
| `tests/test_ui_areas.py`, `test_ui_shell.py`, `test_ui_home.py`, `test_ui_workflow.py` | The areas and the navigation rail, the top bar, the job indicator and the Problems panel, Home with recent projects, the steps Generate, Check and Release over every combination of facts, the lock banner. |
| `tests/test_ui_sheets.py`, `test_ui_import.py`, `test_ui_checks.py`, `test_ui_outputs.py`, `test_ui_settings.py` | The spreadsheet tables (paste from Excel is one undo step), the import wizard and a large file read in the background, the Problems panel and Checks tab, the list of exported files with their SHA-256, the Settings page and its sections. |
| `tests/test_ui_final.py` | Walks every area, tab, Settings section and the Problems panel in both themes: no Qt warning, an accessible name on every control, a tooltip on every icon-only button, the Tab key visits every control and returns to where it started, keyboard focus is visible. |
| `tests/test_ui_timing.py` | The optional timing log (`HARNESS_UI_TIMING=1`). |
| `tests/test_ui_checks_perf.py`, `test_ui_preview_perf.py`, `test_ui_sheets_perf.py`, `test_ui_state_index_scale.py` | Time limits at stress size (200 devices, 2,000 interfaces, about 82,000 findings): an edit after a rule check, a frame of the drawing, a paste of 500 rows. They carry `perf`, so CI runs them alone, with `HARNESS_TIME_FACTOR=3`. |
| `tests/test_output_hashes.py` | All 612 files the four packaged examples write (with the drawings on, as the reference was made) have the SHA-256 in the baseline (`docs/ui/OUTPUT_HASHES_BASELINE.json`; until 1.9.0 the files of release 1.2.0), apart from the version stamp: a change of the interface must not change a written file. The baseline is renewed on purpose when a release changes a written file for good (D-183). |

Pictures of the result are made with `tools.ui_screenshots`, timings with `tools.ui_perf` ([`tools.md`](tools.md)).

## The tests of the 1.4.0 and later features

Version 1.4.0 (the AIT feedback, D-160 to D-165), version 1.5.0 (a harness made by hand, D-166, and the start check, D-167), version 1.6.0 (the start screen of a blank project) and version 1.7.0 (the build workbook, D-169; the build data, D-170; the simple workspace, D-171) added these tests, and the workshop feedback after it (D-172 to D-176) more. The ones that open the editor run offscreen and carry `gui`.

| Tests | What they check |
| --- | --- |
| `tests/test_wires.py` | `SparseEntity` (a default field is not written), editing, locking and resetting a wire, generation keeping label and note, a released harness refusing, the wire list columns *Label* and *Note*, and the independent verifier on them. |
| `tests/test_manual_wires.py` | Drawing, moving and deleting a wire, several wires on one pin (the rule `pin-shared`, the verifier's `pin_shared` warning), groups (twist, shield, ungroup), generation keeping all of it and naming what it cannot keep. |
| `tests/test_pin_function.py`, `tests/test_ui_pin_function.py` | A pin's function and a connector's or harness's label: edit, paste, pinout import, generation, the optional output columns *Function* and *Termination*, the Devices tab. |
| `tests/test_gitinfo.py`, `tests/test_ui_authorship.py` | The commit reader on real repositories (loose, packed, detached, worktree, damaged, size bombs) and the line in the Revisions area. It does not start `git`. |
| `tests/test_device_library.py`, `tests/test_device_library_cli.py`, `tests/test_ui_device_library.py` | Device library files: export, merge, read, adding with renamed IDs, parts and types kept as the project has them, files that are not libraries, the CLI commands and the Devices tab buttons. |
| `tests/test_inventree_import.py` | An InvenTree export (CSV, TSV, JSON) in the parts import: the IPN as part ID, categories, JSON that is not a flat list. |
| `tests/test_startup_help.py` | The Linux start check (missing graphics libraries, no desktop session, the message and the `sudo apt` line), `--check-system`, the `install.sh` warning, and the smoke test's environment without a Python (D-167). |
| `tests/test_manual_harness.py` | A harness made by hand (1.5.0): new harness, free-standing and plugging-in connectors, pin function and termination, delete connector, naming pattern, Generate leaving it alone, released and generated harnesses refusing, undo. |
| `tests/test_ui_from_scratch.py` | The Connectors tab, the New harness button and action, the journey from a blank project in the window, and (1.6.0) the **Add a device** button of the empty diagram. |
| `tests/test_ui_wire_editor.py` | The Edit wire tab: selection, apply, reset, several wires, the new wire form, groups, the labels form. |
| `tests/test_build_workbook.py` | The build workbook (D-169): eight sheets, the same bytes for the same model, no formulas, text that looks like a formula stored as text, the layout, the cut order and colours, every pin in a block, the empty result columns, the readiness lines; the drawings optional (`drawings=False`), a set with the drawings of only some harnesses reported, the folder remembering whether it had drawings; a mutation test for each check of the independent verifier. |
| `tests/test_build_data.py` | The build data (D-170): the plans for strip lengths, contacts, crimp tools and accessories (a released harness refuses, a value outside its range is refused), what generation keeps and what it reports as lost, the Devices pin edit, `import-build-data` (the kind found from the headings, a refused row stops the whole import, `--dry-run`, the shipped templates) and the parts import column *Tool*. |
| `tests/test_build_data_outputs.py` | The build data in the outputs: optional table columns and `accessories.csv` only where used, always in the build workbook, the BOM lines of contacts and accessories, and a mutation test for each check of the independent verifier. |
| `tests/test_ui_build_data.py` | The build data in the editor: strip lengths in *Edit wire*, the *Cable contact* column of the Devices tab, the contact in the *Connectors* tab, the *Accessories* tab and the crimp tool in the Inspector; one undo step each, controls off with the reason for a released harness or a read-only project. |
| `tests/test_next_step.py` | The one next step of the Next step page (D-171, stage S1) over every combination of facts. No Qt. |
| `tests/test_roles.py` | The two roles (D-176, REQ-GUI-14, REQ-GUI-15), pure logic: `default_role`, the carry-over of the 1.7.0 workspace, stored value cleaning, the keys of the layout, the rail of each role. No Qt. |
| `tests/test_ui_next_page.py`, `tests/test_ui_role_layout.py` | The Next step page and the role setting (S1); the Systems engineer role showing less until the person asks: rail without Home, Drawings and Outputs, closed panels, reduced tool row, *Show panels*, a layout kept for each role (S2; `test_ui_role_layout.py` was `test_ui_simple_workspace.py` before milestone M5). |
| `tests/test_ui_roles.py` | The roles on screen (D-176, REQ-GUI-14, REQ-GUI-15): the question of the first start (only without stored values and without the hook), the silent role of an existing user, switching in both directions with each role's layout kept, every area the rail leaves out still reachable, both themes, names and tooltips. |

The proof that existing work is unchanged is `tests/test_output_hashes.py` (above): the 612 files of the four examples still match the baseline apart from the version stamp (until 1.9.0 the baseline was release 1.2.0; since 1.10 it is renewed on purpose, D-183).

## 5. Golden files

A golden file is a stored, reviewed result that a test compares with a fresh one. Changing one on purpose is allowed. Changing one to make a test pass without reading the difference is not.

| Golden | Where | Regenerate on purpose |
| --- | --- | --- |
| Digests of every output file for `mini3`, `sat15`, `sat15_full`, and the readable `mini3` text outputs | `tests/fixtures/outputs/` | `PYTHONPATH=. python -m tools.gen_output_goldens`, then review the diff |
| The `mini3` project (made by hand) | `tests/fixtures/projects/mini3` | the command in [`agent/core.md`](agent/core.md) ("Core layout") |
| The `sat15` project (generated) | `tests/fixtures/projects/sat15` | the command in [`agent/core.md`](agent/core.md) ("Generation layout"); delete the folder first |
| The `sat15` design rule report | `tests/fixtures/drc/sat15.md` | `python -m harness_design_studio.cli.main drc tests/fixtures/projects/sat15 > tests/fixtures/drc/sat15.md` |
| The example projects | `src/harness_design_studio/resources/examples/projects/` | `python -m tools.build_examples` |
| The tutorial's model hash | `docs/GETTING_STARTED.md` | edit the hash when the first export prints a new one |

## 6. What CI runs

`.github/workflows/harness-ci.yml` runs on Ubuntu 24.04 with Python 3.14. After the Qt libraries and `pip install -e ".[gui,dev]"` and Chromium, it runs `ruff check .`, `ruff format --check .`, `mypy`, `pytest -n auto -m "not perf and not slow" --cov` on a pull request (`-m "not perf"` on `master`, so the `slow` tests run there) and then `pytest -m perf --cov --cov-append` (the timing tests alone; the 90 % gate is applied by the second step), `python -m tools.check_reproducible`, `python -m tools.build_installer`, `python -m tools.build_deb`, the self-test of the frozen program (`dist/harness-design-studio/harness-design-studio-gui --selftest`) and `python -m tools.gen_sbom`. It uploads the packages and the SBOM as an artifact. When only Markdown under `HarnessDesignStudio/` changed, only the `docs` job runs (end of section 4). A second job (`package-on-24-04`) installs the packages on a fresh machine without the source tree. From 1.2.0 two more workflows exist: `harness-platforms.yml` runs the whole suite on `windows-latest` (offscreen, `HARNESS_TIME_FACTOR=8`, a time limit per test so that a hang names the test), and `harness-packages.yml` builds and smoke-tests the Windows packages on branches `pkg/**` (it never publishes); `release.yml` builds and publishes all packages when a tag is pushed ([`release.md`](release.md)). `python -m tools.release_check --quick` runs only the first three checks locally (versions, lint and types, the verifiers); it is not a release check ([`release.md`](release.md)).

## When something fails

- **`qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`**: a Qt system library is missing. Install the apt line above, or use `QT_QPA_PLATFORM=offscreen`.
- **A speed test fails** but nothing else: run it alone (`pytest -m perf`), not next to parallel workers; the message names the measured value, the limit and the factor (2 unless `HARNESS_TIME_FACTOR` is set). On a slow machine use `HARNESS_TIME_FACTOR=3`; if it still fails by a wide margin, that is a real slowdown.
- **A test about a generated file fails** ("run: python -m tools.gen_..."): run the generator the message names, then read the diff before you commit.
- **`test_docs_links.py` fails**: the message names the file, the link and whether the file or the heading is missing.
- **The suite is slow**: run only the file you changed, then the whole suite once before you push (`pytest -n auto -m "not perf"` uses all cores).

Next: [architecture](architecture.md), [docs maintenance](docs-maintenance.md)
