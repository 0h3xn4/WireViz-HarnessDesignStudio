# CLAUDE.md: spacecraft harness design tool (`HarnessDesignStudio/`)

Clean-room project inside the WireViz repo. **Never copy or import code from `../src/wireviz` (GPL-3.0).** Specification: `docs/SPEC.md`; decisions: `docs/DECISIONS.md`; architecture: `docs/ARCHITECTURE.md`; plan: `docs/PLAN.md`.

## Status
Where the tool stands, release by release (versions, tags, commits, what each carried): `docs/STATUS.md`. The former text of this section, word for word, is in `docs/developer/CLAUDE_HISTORY.md`. What an agent needs to keep in mind:
- Latest published release `1.10.0` (2026-10-29, tag `v1.10.0` on `6f87980`; before it `1.9.0`, 2026-10-28, `1.8.1`, 2026-10-28, and `1.8.0`, 2026-10-26; the release workflow makes a release when a tag `vX.Y.Z` is pushed, or when a release is published on GitHub that creates the tag, `.github/workflows/release.yml`, `docs/RELEASE.md` step 15); `1.8.1` holds the fixes of the audit of 1.8.0 (`docs/AUDIT_1.8.0.md`, D-177); `1.9.0` is release 1.9 (`docs/ait/RELEASE_1.9_PLAN.md`, D-178 to D-180) and `1.10.0` is release 1.10 (`docs/ait/RELEASE_1.10_PLAN.md`, D-182 to D-185); `1.11.0` (D-186 to D-189) is prepared and not yet published; what their release texts list under *Not in this release* is open. No release is signed off by the owner (`compliance/SIGNOFF.md`).
- 39 design rules. Ubuntu 24.04 and newer and Windows 10/11 (D-149); no macOS build, test or package since D-168. Python 3.14 or newer only.
- The tool ships no derating or EMC values (D-11) and no approved parts list (D-12); each project supplies them, and nobody has. Generation runs on placeholders until a project supplies values, and results must say so. The licence stays the placeholder `LicenseRef-Proprietary` (D-02, D-143); the tool is used internally and never shared (D-186). The owner waived the people-dependent compliance actions (`compliance/DEVIATIONS.md` T-20 to T-30; a waiver accepts a deviation and does not meet the requirement).
- Not built: stage S4 of the simple workspace, command-line versions of the new edits, a lock per pin. No screen was watched on a real display by a person.

## Commands (run from `HarnessDesignStudio/`)
- Setup (Python 3.14 or newer): `python3.14 -m venv .venv && . .venv/bin/activate && pip install -e ".[gui,dev]"` (Linux also needs libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 for Qt; the full list that CI and the `.deb` use is in `docs/INSTALL.md`, "If the app does not start")
- Test: `pytest` (Qt runs offscreen via tests/conftest.py); coverage: `pytest --cov` (90% gate on core, enforced). In parallel (pytest-xdist, D-148): `pytest -n auto -m "not perf"` (pull requests also leave out `-m slow`, the 11 tests of about 10 s or more; `master` and `tools.release_check` run them), then the tests with a wall-clock limit alone: `pytest -m perf` (they carry `@pytest.mark.perf`; `tests/test_parallel_safety.py` fails if one does not). CI runs both steps with `--cov`/`--cov-append`. Tests use `tmp_path` and never a fixed path, so workers do not share files.
- Lint/type: `ruff format . && ruff check . && mypy`
- CLI: `harness-design-studio --version | new FOLDER [--template NAME] | templates FOLDER | schema FOLDER | validate DIR | check DIR | migrate DIR | merge-fix DIR | generate DIR | verify DIR | drc DIR | export DIR [--drawings] | verify DIR --outputs | review/release/revise/diff/log DIR HARNESS | compare OLD NEW | config DIR | library DIR | import-parts/import-lengths/import-build-data/import-netlist/import-pinout/import-devices/import-subsystem DIR FILE | export-pinout/export-devices/export-subsystem` (`harness-design-studio COMMAND --help` for the options; `docs/CLI.md` is generated from the parser); GUI: `harness-design-studio-gui` (the source install takes only `--version`; the packaged editor, `packaging/gui_entry.py`, also takes `--selftest [--selftest-out FILE]` and `--check-system`); `harness` and `harness-gui` are kept as aliases
- GUI tests: `QT_QPA_PLATFORM=offscreen pytest tests/test_gui_journeys.py` (conftest sets it); timings: `python -m tools.bench_gui`; screenshots of the real editor: `python -m tools.gui_screenshots` (docs/ux/qt, 26 pictures, about a minute) and `python -m tools.flatsat_screenshots` (docs/img)
- Prototype: edit `prototype/template.html` / `prototype/app.js` or `gui/theme/tokens.py`, then `python -m tools.build_prototype` (a test fails if `index.html` is stale); screenshots: `python -m tools.ux_screenshots`; journeys: `pytest tests/test_prototype.py` (needs Chromium, skips otherwise)
- Stress benchmarks: `python -m tools.bench_stress`, `python -m tools.bench_generate`, `python -m tools.bench_incremental` (one edit, the autosave journal, export and an undo step at 200 devices)
- Output goldens: `PYTHONPATH=. python -m tools.gen_output_goldens` (on purpose; review the diff)
- Package (Ubuntu): `python -m tools.build_installer`, `python -m tools.build_deb`, then `dist/harness-design-studio/harness-design-studio-gui --selftest` (and `--check-system`; `gui/startup_help.py` names the three system libraries the package needs and words the fix, D-167; the smoke tests run packages with `clean_env()`, no Python in the environment)
- Package (Windows, on Windows): `python -m tools.build_windows` (zip and Inno Setup installer); test the finished file: `python -m tools.smoke_package windows-setup|windows-zip FILE`. CI: `.github/workflows/harness-packages.yml` (branches `pkg/**`, never publishes); signing is optional and needs repository secrets (docs/RELEASE.md)
- Release checklist: `python -m tools.release_check [--quick]`; soak: `python -m tools.soak 5000 <seed>`
- Docs that must stay in sync (tests fail otherwise): `python -m tools.build_guide` (in-app guide), `python -m tools.gen_rule_docs` (`docs/RULES.md`), `python -m tools.gen_cli_docs` (`docs/CLI.md`), `python -m tools.build_examples` (example projects). `tests/test_docs.py` also runs the commands of `docs/GETTING_STARTED.md` and `README.md`, and `tests/test_docs_links.py` checks every relative link and anchor; usability: `python -m tools.usability_setup DIR`, `python -m tools.usability_summary results.csv sus.csv`
- SBOM + licence report: `python -m tools.gen_sbom`; reproducible check: `python -m tools.check_reproducible`
- Offline wheelhouse: `python -m tools.vendor`

## Conventions
- `core` must not import `gui`, `cli` or any network module. Offline guarantee is tested.
- All model changes go through commands/transactions; GUI never mutates the model directly.
- Deterministic everywhere: sort by stable IDs, no timestamps in generated data, canonical JSON.
- Never invent standard values (derating, current ratings, mass). Use `PLACEHOLDER` config values and list them for the owner.
- No design data in logs. UI strings in one module.
- The screen says *device*, the files say *unit* (`Unit`, `units`, `logical/units/`, `unit_id`, and the finding texts that reach a written output file); the command line has `--device` and keeps `--unit`; the one exception is the connection list (`system/connections.csv` and `.xlsx`, new in 1.9), whose headings say *device* (owner decision); a wording change on screen must not change a generated file (`python -m tools.output_hashes --check docs/ui/OUTPUT_HASHES_BASELINE.json`).
- Every new dependency: record name, version, licence in `docs/DECISIONS.md`.
- Tests first; every bug fix gets a regression test.
- End each session with: done, tested, next, UX targets met/open.

## Where the rest is

The area notes were moved word for word out of this file on 2026-10-29 so that every session loads about a third of what it did (decision D-182). Read the one that matches the work before you start; nothing else in them has changed.

- Core, generation, the design rules, wires, connections, the library, the KiCad import: [`docs/developer/agent/core.md`](docs/developer/agent/core.md)
- The editor (window, panels, roles, Next step page, Systems engineer path): [`docs/developer/agent/gui.md`](docs/developer/agent/gui.md)
- Written files, the independent verifier, the goldens, the build workbook: [`docs/developer/agent/outputs.md`](docs/developer/agent/outputs.md)
- Revisions, baselines, the release freeze, review: [`docs/developer/agent/change-control.md`](docs/developer/agent/change-control.md)
- Examples, templates, documents that tests read, the compliance set: [`docs/developer/agent/examples-and-docs.md`](docs/developer/agent/examples-and-docs.md)
- What the user sees (colours, fonts, spacing, theme, accessibility): [`docs/developer/agent/ui-design-rules.md`](docs/developer/agent/ui-design-rules.md)
