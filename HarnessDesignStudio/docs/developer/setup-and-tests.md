# Set up a development environment and run the tests

This page shows how to set up a place to work on Harness Design Studio, run the tests and checks that CI runs, and know which tests read the documentation.

## Contents

- [What you need](#what-you-need)
- [1. Set up](#1-set-up)
- [2. Run the tests](#2-run-the-tests)
- [3. Check the style and the types](#3-check-the-style-and-the-types)
- [4. The tests that read the documents](#4-the-tests-that-read-the-documents)
- [5. Golden files](#5-golden-files)
- [6. What CI runs](#6-what-ci-runs)
- [When something fails](#when-something-fails)

## What you need

- Ubuntu 24.04 or newer, 64-bit. Windows and macOS are not supported (decision D-127 in [`DECISIONS.md`](../DECISIONS.md)).
- Python 3.12 or newer (`python3 --version`), with `python3-venv`, and Git.
- For Qt, the system libraries `libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0`. CI installs a few more (`libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0`) and `poppler-utils`. On a machine without a screen the tests use Qt's `offscreen` mode, so no display is needed. The apt line was copied from `CLAUDE.md` and the CI file. It was not run for this page, because the libraries were already present on the machine used.
- Work in the `HarnessDesignStudio/` folder. The WireViz code at the repository root is a separate program ([`CONTRIBUTING.md`](../../../CONTRIBUTING.md)).

## 1. Set up

```
cd HarnessDesignStudio
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[gui,dev]"
```

This took about 40 seconds with a network connection and ended without errors. The extras:

| Extra | What it adds |
| --- | --- |
| (none) | The program and its libraries: `pydantic`, `openpyxl`, `defusedxml`. This is all the command line needs. |
| `gui` | `PySide6-Essentials` (Qt), for the editor. |
| `dev` | Test and build tools: `pytest`, `pytest-cov`, `pytest-qt`, `hypothesis`, `mypy`, `ruff`, `cyclonedx-bom`, `pip-licenses`, `pip-audit`, `pyinstaller`, `playwright`. |

Versions are pinned in `pyproject.toml`. A new dependency needs its name, version and licence recorded in [`DECISIONS.md`](../DECISIONS.md).

Check it:

```
harness-design-studio --version
```

```
harness 1.0.0
```

Start the editor with `harness-design-studio-gui`.

The prototype tests drive a Chromium browser. `playwright` is installed by `dev`, but the browser is not. CI runs `python -m playwright install --with-deps chromium`. Without a browser those tests are skipped.

## 2. Run the tests

```
pytest
```

The whole suite has about 1,000 tests (1,026 when this page was checked) and took about 11 minutes with coverage on the machine used: 1,024 passed and 1 was skipped (the test that needs a normal user; the run was as root). One speed test failed because `HARNESS_TIME_FACTOR` was not set (see the table). Qt runs offscreen by itself, because `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`.

| Command | What it does |
| --- | --- |
| `pytest -q tests/test_docs.py tests/test_docs_links.py` | Only the tests that read the documents (a minute or less). |
| `pytest tests/test_gui_journeys.py` | The editor journeys, driven like a user. |
| `pytest --cov` | The tests with coverage. The gate is 90 % on `harness_design_studio.core`; the run prints `Required test coverage of 90.0% reached`. The same run had 95.7 %. The GUI is outside the measure. |
| `pytest -k wire_colours` | Only tests whose name matches. |
| `HARNESS_TIME_FACTOR=3 pytest tests/test_gui_perf.py` | The speed tests with limits three times as generous. On a slow or shared machine one or two of them can fail without the factor. CI sets 3. |
| `HARNESS_FUZZ_EXAMPLES=5000 pytest tests/test_fuzz.py` | The long fuzzing run (the default is 40 examples). |
| `HARNESS_REQUIRE_BROWSER=1 pytest tests/test_prototype.py` | Fail instead of skipping when no Chromium is found. CI sets it. |

Notes:

- A test that needs a normal user (`tests/test_atomic_lock.py`) is skipped when you run as root. Run the suite as a normal user in CI.
- Every bug fix gets a regression test, and tests come first. See the conventions in [`../../CLAUDE.md`](../../CLAUDE.md).
- The GUI tests need no screen: `QT_QPA_PLATFORM=offscreen pytest tests/test_gui_journeys.py`.

## 3. Check the style and the types

```
ruff format --check .
ruff check .
mypy
```

```
331 files already formatted
All checks passed!
Success: no issues found in 202 source files
```

(The file counts change as files are added.) `ruff format .` rewrites files into the standard layout; run it before you commit. With the pinned ruff (0.16.10) it also formats the code in fenced `python` blocks inside Markdown files under `HarnessDesignStudio/`. A block that is not in ruff's layout fails `ruff format --check .` in CI, so run `ruff format .` after you edit a page that holds Python code. `mypy` runs in strict mode over `src`, `tests` and `tools`. Settings are in `pyproject.toml`: line length 100, rules `E F W I B UP SIM S`.

## 4. The tests that read the documents

A change that only touches Markdown can still break a test. Know these:

| Test file | What it enforces |
| --- | --- |
| `tests/test_docs_links.py` | Every relative link and every `#anchor` in the listed files resolves. The list: `HarnessDesignStudio/README.md`, `CLAUDE.md`, `CHANGELOG.md`, every `docs/*.md` (not the sub-folders), `docs/guide/USER_GUIDE.md` and the templates `README.md`. Links inside code fences are not checked. The anchor rule is GitHub's. |
| `tests/test_docs.py` | The in-app guide (`resources/guide/index.html`) equals what `tools.build_guide` makes from `docs/guide/USER_GUIDE.md`; every `harness-design-studio` command is named in the guide; the buttons the guide names exist in `gui/strings.py`; no paragraph of the guide is longer than 700 characters; `docs/RULES.md` and `docs/CLI.md` equal what their generators write; every config key is in `docs/CONFIG.md`; the commands of `docs/GETTING_STARTED.md` and of `HarnessDesignStudio/README.md` are run in order in a scratch folder with the expected exit codes; the model hash quoted in `GETTING_STARTED.md` equals the one the first `export` prints; the **F1** key opens the guide. |
| `tests/test_examples.py` | The example projects equal what `tools.build_examples` writes; the design worksheet names only real unit kinds and interface types; the numbers in `docs/FLATSAT_EXAMPLE.md` match the `flatsat` example. |
| `tests/test_compliance_matrix.py`, `test_trace.py`, `test_sdd_components.py`, `test_metrics.py`, `test_scf.py`, `test_family_group_mapping.py`, `test_profiles.py`, `tests/test_drc.py::test_cited_requirements_exist_in_the_extracted_lists` | The generated compliance files are current (matrix, traceability, component table), no matrix row claims compliance, every module has a docstring, and every cited requirement ID exists. |

The sub-folders `docs/user-manual/` and `docs/developer/`, the root `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md` and `HarnessDesignStudio/compliance/**/*.md` are not in the link test. Check them with the offline link checker in [`docs-maintenance.md`](docs-maintenance.md#check-the-links).

When only Markdown under `HarnessDesignStudio/` changes, CI runs just the `docs` job: `test_docs.py`, `test_docs_links.py` and the compliance tests above (decision D-138).

## 5. Golden files

A golden file is a stored, reviewed result that a test compares with a fresh one. Changing one on purpose is allowed. Changing one to make a test pass without reading the difference is not.

| Golden | Where | Regenerate on purpose |
| --- | --- | --- |
| Digests of every output file for `mini3`, `sat15`, `sat15_full`, and the readable `mini3` text outputs | `tests/fixtures/outputs/` | `PYTHONPATH=. python -m tools.gen_output_goldens`, then review the diff |
| The `mini3` project (made by hand) | `tests/fixtures/projects/mini3` | the command in `CLAUDE.md` ("Core layout") |
| The `sat15` project (generated) | `tests/fixtures/projects/sat15` | the command in `CLAUDE.md` ("Generation layout"); delete the folder first |
| The `sat15` design rule report | `tests/fixtures/drc/sat15.md` | `python -m harness_design_studio.cli.main drc tests/fixtures/projects/sat15 > tests/fixtures/drc/sat15.md` |
| The example projects | `src/harness_design_studio/resources/examples/projects/` | `python -m tools.build_examples` |
| The tutorial's model hash | `docs/GETTING_STARTED.md` | edit the hash when the first export prints a new one |

## 6. What CI runs

`.github/workflows/harness-ci.yml` runs on Ubuntu 24.04 with Python 3.12. After the Qt libraries and `pip install -e ".[gui,dev]"` and Chromium, it runs `ruff check .`, `ruff format --check .`, `mypy`, `pytest --cov`, `python -m tools.check_reproducible`, `python -m tools.build_installer`, `python -m tools.build_deb`, the self-test of the frozen program (`dist/harness-design-studio/harness-design-studio-gui --selftest`) and `python -m tools.gen_sbom`. It uploads the packages and the SBOM as an artifact. A second job (`package-on-24-04`) installs the packages on a fresh machine without the source tree. `python -m tools.release_check --quick` runs only the first three checks locally (versions, lint and types, the verifiers); it is not a release check ([`release.md`](release.md)).

## When something fails

- **`qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`**: a Qt system library is missing. Install the apt line above, or use `QT_QPA_PLATFORM=offscreen`.
- **A speed test fails** but nothing else: use `HARNESS_TIME_FACTOR=3`.
- **A test about a generated file fails** ("run: python -m tools.gen_..."): run the generator the message names, then read the diff before you commit.
- **`test_docs_links.py` fails**: the message names the file, the link and whether the file or the heading is missing.
- **The suite is slow**: run only the file you changed, then the whole suite once before you push.

Next: [architecture](architecture.md), [docs maintenance](docs-maintenance.md)
