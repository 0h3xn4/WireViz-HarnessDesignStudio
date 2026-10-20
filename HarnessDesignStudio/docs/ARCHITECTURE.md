# Architecture

> **Status.** Sections 1, 4, 5 and 6 are the original proposal, written before the tool was built, and were only partly re-checked since. The platform remarks in them are historical: the tool was first Ubuntu only (D-110, D-127) and has run on Ubuntu 24.04 and newer, Windows 10 and 11 and macOS 13 and newer since 1.2.0 (D-149, which supersedes both). The design rule check runs in a helper process (D-128). **Section 2 was rewritten from the source tree for version 1.3.0** (folders and module docstrings; the user interface of 1.3.0 is the one of the UI overhaul, D-150 to D-159) and is the current layout; the project folder format is in [`FILE_FORMAT.md`](FILE_FORMAT.md). The look of the editor and the rules for its code are in [`DESIGN.md`](DESIGN.md).

## Contents

- [1. Stack comparison (the original proposal)](#1-stack-comparison-the-original-proposal)
- [2. Layering](#2-layering)
- [3. Project folder format](#3-project-folder-format)
- [4. Key mechanisms](#4-key-mechanisms)
- [5. Testing architecture](#5-testing-architecture)
- [6. Risks](#6-risks)

## 1. Stack comparison (the original proposal)

This table and the choice below are the proposal as it was written. The choice was A and the tool was built that way.

| | A. Python + PySide6 (chosen) | B. Rust core + Tauri (web UI) | C. Electron + TypeScript |
| --- | --- | --- | --- |
| Offline packaging | PyInstaller one-folder; ~150-250 MB; proven on locked-down hosts | Small binaries (~10 MB) but needs OS WebView2/WebKitGTK, which may be missing or outdated on RHEL 8 / locked Windows | Bundles Chromium (~150 MB); works everywhere; large npm supply chain to vendor |
| Licences | Python/Qt LGPL OK | Rust crates mostly MIT/Apache; WebKit LGPL | MIT; many transitive npm licences to audit |
| Canvas editor | QGraphicsView: mature, high-DPI, offscreen screenshots | Custom canvas/SVG in JS | Same as Tauri |
| PDF/SVG | reportlab + own SVG writer | Strong (printpdf, svg) but fewer drafting helpers | JS libs, heavier |
| Testing the GUI | pytest-qt, offscreen | Playwright-style, more infra | Same |
| Team ramp-up / Claude Code velocity | Fastest; one language for core, CLI, GUI | Two languages | Two ecosystems |
| Supply chain / SBOM | pip: small, vendorable | cargo vendor + npm | npm: very large |

**Choice: A.** It fits the air-gapped constraint (no system WebView dependency), has the best-supported desktop canvas, and keeps a single language. Cost: bigger installer and slower startup than Tauri. Performance risk (20,000 wires) is handled by keeping the core pure and algorithmically indexed, and by rendering only visible items in the canvas; if profiling in M3 shows the generator misses the 10 s target, hot spots can move to a compiled extension without changing the API.

## 2. Layering

The layout of `HarnessDesignStudio/src/harness_design_studio/`. The one-line descriptions are the first lines of each module's docstring. The generated table of every module, with the requirements it serves, is [`compliance/sdd_components.csv`](../compliance/sdd_components.csv) (see [`compliance/docs/SDD.md`](../compliance/docs/SDD.md)).

```
HarnessDesignStudio/src/harness_design_studio/
  __init__.py      offline spacecraft harness design tool
  core/            headless: no GUI, CLI or network imports (enforced by tests/test_architecture.py)
  cli/             the `harness-design-studio` command
  gui/             PySide6 editor; depends on core, the core never depends on it
  resources/       bundled offline user guide, example projects and templates, fonts
```

Rules: `gui` and `cli` depend on `core`; `core` depends on nothing in `gui` or `cli`. The GUI never changes the model directly; every change is a list of operations run by `core/commands.py` as one transaction (all or nothing, with undo and redo).

### `core/`: the project and its rules

| Module | What it does |
| --- | --- |
| `model/` | the model objects: `base` (base class and field types), `logical` (what must be connected), `physical` (connectors, pins, wires, shields, harnesses), `library` (parts), `config` (rule configuration, defaults are placeholders), `generation` (record of the last generation), `review` (layout and waivers), `project` (the one mutable in-memory container) |
| `commands.py` | transactions with undo and redo; all model changes are lists of operations applied atomically |
| `edit.py` | editing operations for the block diagram (pure functions that build lists of operations) |
| `ids.py`, `units.py`, `errors.py` | identifier rules; SI helpers (AWG with mm² alongside); explicit error types |
| `integrity.py` | referential integrity of a project; runs on every load, save and transaction |
| `issues.py` | findings reported by loading, integrity checking and `harness-design-studio validate` / `check` |
| `checks.py` | logical-layer findings shown in the Problems tab (with its to-do list) |
| `recovery.py` | autosave journal of an open project, kept inside the project folder |
| `schemas.py` | JSON Schemas of the project files, made from the model itself |
| `samples.py`, `starter.py`, `templates.py` | reference projects for tests and the first-run sample; starter library and interface types (example data only); the example projects and import templates shipped with the tool |
| `standard_profiles.py`, `configcheck.py` | optional value profiles from the supplied standards (D-131); check and fill in the engineering configuration (D-11) |
| `devices.py`, `pinout_import.py` | custom devices down to each pin: the plans the Devices view and the pinout import call (connectors, pins, pasted rows, the state of a device); import of a device's pinout from CSV or XLSX as a plan |
| `wires.py` | the plans behind the *Edit wire* tab (1.4.0): edit a wire (gauge, type, colour, length lock it; label and note are always kept), reset, draw a wire, move its ends, delete, group (twist or shield), set the harness and connector labels (D-161 to D-163) |
| `device_library.py` | device library files: devices with their pinouts, parts and interface types saved outside a project and added to another (D-165) |
| `wirecolours.py`, `routing.py`, `describe.py` | the IEC 60757 wire colours; link-drawing rules that do not need Qt; plain-language captions for links and connectors, the link tooltip, the picture of a unit |
| `usedby.py`, `why.py`, `generation_status.py` | where a unit, link, part or interface type is used; why an object is the way it is (reads the generation record); whether the harness plans match the design |
| `imports.py`, `library_import.py`, `kicad.py` | CSV/TSV/JSON/XLSX tables and the import of interfaces; import of an approved-parts list (D-12; also an InvenTree export file, D-165); reading unit connector pinouts from a KiCad netlist (D-123) |
| `io/` | project folder input and output: `canonical` (canonical JSON), `fs` (atomic writes, safe names, lock), `layout` (memory to folder mapping), `loader`, `saver`, `migrate` (schema migrations) |

### `core/`: generation, checks, outputs, change control

| Module | What it does |
| --- | --- |
| `generate/` | harness generation: `engine` (interfaces in, harnesses out, as a previewable plan), `segmentation` (which interfaces share a harness), `pins` (pin allocation for a box connector), `wiring` (which signal connects to which), `sizing` (wire sizing), `lengths` (lengths from segments, CSV import), `mass`, `naming` (naming schemes), `explain` (the recorded reasons behind generated objects) |
| `drc/` | design rule check (35 rules): `base` (rule building blocks), `rules` (the rules, one function each), `standard_rules` (rules that apply the supplied standards), `report` (the report), `by_rule` (one result per rule: pass, fail, not checked, pending), `worker` (the child process that runs the check) |
| `verify.py` | independent output verifier: a separate code path from `generate/` that shares no logic with it |
| `outputs/` | `build` (build, write and check the output set), `canvas` (small deterministic SVG and PDF drawing model), `drawing` (the harness drawing), `system` (block diagram and harness overview), `tables`, `errors` (the builder's errors in plain language), `exports` (WireViz-style YAML, JSON, XLSX), `xlsx_env` (turns lxml off before openpyxl is imported, so workbooks are identical on every machine), `provenance`, `stamp` (tool version and model hash on every file), `verify` (output verifier: re-reads the finished files) |
| `vcs/` | change control: `release` (review, release, new revision), `locks` (locks on released items), `snapshot`, `diff`, `hashing`, `gitinfo` (the last commit of the Git repository around the project folder, read from the `.git` files without starting `git`, D-164), `consistency` (released harnesses against their baselines), `lockview` (what a release locks and why, which fields stay editable), `timeline` (the change log as rows, differences grouped by kind), `report` (change log and revision report) |

### `cli/` and `gui/`

| Module | What it does |
| --- | --- |
| `cli/main.py` | the `harness-design-studio` entry point (`harness` is an alias) |
| `cli/start.py`, `cli/data.py`, `cli/changes.py` | getting started (`new`, `templates`); outside data (`config`, `import-parts`, `import-lengths`, `import-netlist`, `import-pinout`, `import-devices`, `export-pinout`, `export-devices`); change control (`review`, `release`, `revise`, `diff`, `compare`, `log`) |

The editor (`gui/`) has these parts. The window is a navigation rail (Home, Model, Checks, Drawings, Outputs, Revisions, Settings), one top bar with the three steps Generate, Check and Release, the open area, a project panel on the left, the inspector on the right, a Problems panel at the bottom and a status bar. An area is a view onto the six main tabs (Diagram, Devices, Checks, Harness, Lists, Releases); Home and Settings are pages of their own.

| Module | What it does |
| --- | --- |
| `gui/app.py`, `gui/main_window.py` | GUI entry point; the main window: menus, actions, the slots views plug into, settings, the layout kept per project |
| `gui/areas.py`, `gui/rail.py`, `gui/shell.py` | the areas and which tabs each holds (no Qt); the navigation rail; building blocks of the window (tabs with slots, banners, empty states, the status chip rule) |
| `gui/topbar.py`, `gui/workflow.py`, `gui/jobs.py`, `gui/problems_panel.py` | the top bar; the Generate, Check and Release steps worked out from the facts (no Qt); the job indicator of the status bar with Cancel; the Problems list at the bottom |
| `gui/pages.py`, `gui/settings_page.py`, `gui/licences.py`, `gui/recent.py` | the Home page; the Settings page (Appearance, Editing, Project, Keyboard shortcuts, About, Licences); the licence texts the About page shows; recent projects |
| `gui/controller.py` | `EditorController`: the only object that changes the project |
| `gui/canvas.py`, `gui/glyphs.py`, `gui/legend.py`, `gui/canvas_state.py`, `gui/canvas_badges.py` | the diagram canvas (zone lanes, units, links, overview map); pictograms for links and connectors; the legend overlay; the index of problems, pending values and locks per object; the badges and the corner chip |
| `gui/project_tree.py`, `gui/inspector.py`, `gui/why_panel.py` | the project tree, the inspector (fields, used in, lock banner) and the Why panel |
| `gui/harness_view.py`, `gui/lists_panel.py`, `gui/outputs_files.py`, `gui/checks_panel.py`, `gui/releases_panel.py`, `gui/plan_table.py` | the Drawings, Outputs, Checks and Revisions views (the tabs Harness, Lists, Checks, Releases); the list of exported files with their SHA-256; the table of the generate plan |
| `gui/devices_view.py`, `gui/devices_pin_table.py`, `gui/devices_dialogs.py` | the Devices tab: one unit down to each pin, its editable pin table and its small dialogs |
| `gui/interface_table.py`, `gui/unit_table.py`, `gui/sheet.py`, `gui/empty_state.py` | the Interfaces and Units tables of the left panel; the spreadsheet behaviour they share (paste from Excel, bulk edit, Enter to edit); what a table without rows says |
| `gui/export_dialog.py`, `gui/export_docs.py`, `gui/import_wizard.py`, `gui/import_kinds.py`, `gui/new_project_dialog.py`, `gui/config_dialog.py`, `gui/lock_tree.py`, `gui/notice.py` | the export window and the names of the documents it lists; the import wizard and what it can import (no Qt in the kinds); the new project window; the engineering values form; the tree of what a release locks; inline notices |
| `gui/tables.py`, `gui/states.py`, `gui/icons.py`, `gui/background.py`, `gui/timing.py` | shared tables, state chips, icons painted in code, background jobs, the optional timing log (`HARNESS_UI_TIMING=1`) |
| `gui/panels.py`, `gui/dialogs.py`, `gui/preview.py`, `gui/tour.py`, `gui/command_palette.py`, `gui/appicon.py` | the properties form and the inspector's problems cards (the to-do lines); other dialogs; the zoomable drawing preview; the first-run tour; the Ctrl+K overlay; the logo painted in code |
| `gui/drc_process.py` | runs the design rule check in a separate, long-lived process |
| `gui/strings.py` | all user-visible text |
| `gui/theme/` | the theme package. `tokens.py` is the one source of every colour, type size, gap, radius and duration (light and dark themes); `palette.py` maps tokens to Qt palette roles; `qss.py` is the application style sheet, which names palette roles and holds no colour; `style.py` is the widget style (Fusion, with check boxes and radio buttons drawn from the palette); `fonts.py` loads the bundled Inter and JetBrains Mono; `manager.py` is the theme manager (System, Light, Dark; interface size; reduce motion). `tests/test_theme_scan.py` fails when a colour, font family or font size is written outside this package |

The files `gui/tokens.py`, `gui/theme.py`, `gui/fonts.py` and `gui/indicators.py` of version 1.2.0 and older no longer exist (D-150): the IBM Carbon colours and the IBM Plex fonts they held are gone. The mapping of every old tab, menu and dialog to its new place is in [`ui/UI_OVERHAUL_PLAN.md`](ui/UI_OVERHAUL_PLAN.md), section 4.

### `resources/`

`guide/index.html` is the offline user guide, built from `docs/guide/USER_GUIDE.md` by `tools/build_guide.py`. `examples/projects/` holds the example projects (built by `tools/build_examples.py`) and `examples/templates/` the import templates, CI scripts, checklist, worksheet and demo values. `fonts/` holds the bundled fonts (Inter and JetBrains Mono, with their SIL OFL texts).

## 3. Project folder format

The folder layout, the file shapes and the rules for IDs, saving and migration are described once, in [`FILE_FORMAT.md`](FILE_FORMAT.md). The design properties from the proposal still hold: stable key ordering, stable IDs, one file per subsystem so Git merges rarely conflict, and an atomic save (write a temporary file, flush, rename, keep a `.bak`).

## 4. Key mechanisms

- **Determinism:** generation is a pure function `(model, config, library) -> physical model + provenance`. Sorting by stable IDs everywhere; no reliance on dict/set order or timestamps; hash of canonical JSON is the `model_hash`. Property test: regenerate twice and compare bytes.
- **Locks and overrides:** user-edited pins/wires carry `locked: true` or `override` records. Regeneration runs in "merge" mode and returns a `RegenReport` (kept / changed / conflicts) shown before applying.
- **Explain:** every generator decision appends a provenance record `{object_id, rule_id, inputs, reason}`. The "Explain" action and the DRC fix text read these.
- **Verifier:** `core/verify.py` (the model) and `core/outputs/verify.py` (the finished files) read only emitted artefacts (CSV/JSON/SVG data) and the model, and recomputes expected end-to-end connectivity with its own simple implementation (no shared code with `generate/` beyond model types). Release command refuses on any verifier error. The model verifier also compares each wire's signal label and its cable-side pin table with the unit connector pinout. Stale detection: each artefact stores `model_hash`; GUI/CLI compare it with the current hash.
- **DRC process:** the background check runs in a long-lived helper process (`gui/drc_process.py` starts `core/drc/worker.py`; a packaged program is started with `--drc-worker`), because a thread shared the interpreter lock with the editor and stalled edits. The project and the findings cross the pipes in small pieces. If the helper cannot start it falls back to a thread (D-128).
- **DRC:** each rule is a `Rule` record with `id`, `severity`, `topic`, `why`, `how` and a `check(project)` function that yields hits (`core/drc/base.py`); a rule that can be fixed automatically offers a fix label (`drc.fix_ops`). Rules and thresholds come from config. Waivers are keyed by (rule id, object id, hash of finding) with mandatory justification.
- **Recovery mode:** loader validates per file; broken files are quarantined into a `RecoveryReport`, the rest loads; nothing is dropped silently and originals are never overwritten.
- **Offline guarantee:** test 1 scans all source and imported modules for `socket`, `http`, `urllib`, `requests`, `ssl`, `QtNetwork` etc.; test 2 patches `socket.socket` to raise and runs the CLI and a GUI smoke test; GUI build excludes QtNetwork/QtWebEngine.
- **Logging:** structured, local, allow-listed fields only (event name, error type, counts). Object names and values are never logged by default.
- **Performance:** model holds ID indexes; DRC is incremental (re-check only affected objects); generation parallelisable per harness group; canvas uses item culling. A larger stress project is built in code (`stress_project()` in `core/samples.py`) and timed by `tools/bench_stress.py`.

## 5. Testing architecture

pytest + hypothesis (property tests, fuzzing loaders/importers/generator), pytest-cov (>= 90% core gate), mypy strict, ruff, pytest-qt for journeys (and, for the user interface of 1.3.0, tests that walk every area in both themes: `tests/test_ui_*.py`, `tests/test_theme_scan.py`, `tests/test_tokens.py`), golden-file tests per output type on the reference projects `mini3` and `sat15` (folders in `tests/fixtures/projects`; the larger `stress_project()` is built in code for performance tests), soak test (random edits/undo/redo/save/reload with invariants + verifier), offline test, migration fixtures per schema version, CI on Ubuntu 24.04, and from 1.2.0 the whole suite also on Windows and macOS runners (`harness-platforms.yml`).

## 6. Risks

1. Pin allocation is the hardest algorithm: start with a constraint-ordered greedy allocator with explicit rule list and provenance; keep it replaceable.
2. Real derating/EMC numbers are missing (D-11); generator and DRC must run with placeholders and mark every result "uses placeholder rules" until replaced.
3. Installer size and PyInstaller: build each package on its own operating system in CI (Ubuntu 24.04, Windows, macOS; D-149).
4. Locked-down hosts may block unsigned executables; code signing is configurable (D-19).
5. UX sign-off is a gate: no full editor before the prototype review (spec UX process step 2).

Next: [`DECISIONS.md`](DECISIONS.md), [`SECURITY.md`](SECURITY.md), [`developer/README.md`](developer/README.md).
