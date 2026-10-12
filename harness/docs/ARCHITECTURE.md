# Architecture

> **Status.** Sections 1, 4, 5 and 6 are the original proposal, written before the tool was built. Since then the platform has been narrowed to Ubuntu 24.04 and newer only (D-110, D-127), so the Windows and RHEL remarks below are historical, and the design rule check runs in a helper process (D-128). **Section 2 was rewritten from the source tree** (folders and module docstrings) and is the current layout; the project folder format is in [`FILE_FORMAT.md`](FILE_FORMAT.md). A few statements in sections 4 and 5 were corrected where the code differs; the rest was not re-checked line by line.

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

The layout of `harness/src/harness_design_studio/`. The one-line descriptions are the first lines of each module's docstring. The generated table of every module, with the requirements it serves, is [`compliance/sdd_components.csv`](../compliance/sdd_components.csv) (see [`compliance/docs/SDD.md`](../compliance/docs/SDD.md)).

```
harness/src/harness_design_studio/
  __init__.py      offline spacecraft harness design tool
  core/            headless: no GUI, CLI or network imports (enforced by tests/test_architecture.py)
  cli/             the `harness` command
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
| `issues.py` | findings reported by loading, integrity checking and `harness validate` / `check` |
| `checks.py` | logical-layer findings shown in the Problems panel and the to-do list |
| `recovery.py` | autosave journal of an open project, kept inside the project folder |
| `schemas.py` | JSON Schemas of the project files, made from the model itself |
| `samples.py`, `starter.py`, `templates.py` | reference projects for tests and the first-run sample; starter library and interface types (example data only); the example projects and import templates shipped with the tool |
| `standard_profiles.py`, `configcheck.py` | optional value profiles from the supplied standards (D-131); check and fill in the engineering configuration (D-11) |
| `wirecolours.py`, `routing.py`, `describe.py` | the IEC 60757 wire colours; link-drawing rules that do not need Qt; plain-language captions for links and connectors |
| `imports.py`, `library_import.py`, `kicad.py` | CSV/XLSX import of interfaces; import of an approved-parts list (D-12); reading unit connector pinouts from a KiCad netlist (D-123) |
| `io/` | project folder input and output: `canonical` (canonical JSON), `fs` (atomic writes, safe names, lock), `layout` (memory to folder mapping), `loader`, `saver`, `migrate` (schema migrations) |

### `core/`: generation, checks, outputs, change control

| Module | What it does |
| --- | --- |
| `generate/` | harness generation: `engine` (interfaces in, harnesses out, as a previewable plan), `segmentation` (which interfaces share a harness), `pins` (pin allocation for a box connector), `wiring` (which signal connects to which), `sizing` (wire sizing), `lengths` (lengths from segments, CSV import), `mass`, `naming` (naming schemes), `explain` (the recorded reasons behind generated objects) |
| `drc/` | design rule check: `base` (rule building blocks), `rules` (the rules, one function each), `standard_rules` (rules that apply the supplied standards), `report` (the report), `worker` (the child process that runs the check) |
| `verify.py` | independent output verifier: a separate code path from `generate/` that shares no logic with it |
| `outputs/` | `build` (build, write and check the output set), `canvas` (small deterministic SVG and PDF drawing model), `drawing` (the harness drawing), `system` (block diagram and harness overview), `tables`, `exports` (WireViz-style YAML, JSON, XLSX), `xlsx_env` (turns lxml off before openpyxl is imported, so workbooks are identical on every machine), `provenance`, `stamp` (tool version and model hash on every file), `verify` (output verifier: re-reads the finished files) |
| `vcs/` | change control: `release` (review, release, new revision), `locks` (locks on released items), `snapshot`, `diff`, `hashing`, `consistency` (released harnesses against their baselines), `report` (change log and revision report) |

### `cli/` and `gui/`

| Module | What it does |
| --- | --- |
| `cli/main.py` | the `harness` entry point |
| `cli/start.py`, `cli/data.py`, `cli/changes.py` | getting started (`new`, `templates`); outside data (`config`, `import-parts`, `import-lengths`, `import-netlist`); change control (`review`, `release`, `revise`, `diff`, `compare`, `log`) |
| `gui/app.py`, `gui/main_window.py` | GUI entry point; main window: palette (left), diagram (centre), properties (right), problems and tables (bottom) |
| `gui/controller.py` | `EditorController`: the only object that changes the project |
| `gui/canvas.py`, `gui/glyphs.py`, `gui/legend.py` | the diagram canvas (zone lanes, units, links, overview map); pictograms for links and connectors; the key under the diagram |
| `gui/panels.py`, `gui/dialogs.py`, `gui/preview.py`, `gui/tour.py` | side and bottom panels; dialogs; drawing preview; the first-run tour |
| `gui/drc_process.py` | runs the design rule check in a separate, long-lived process |
| `gui/strings.py`, `gui/tokens.py`, `gui/theme.py`, `gui/fonts.py` | all user-visible text; design tokens (colours, type, spacing); theme (light, dark, UI scale); bundled IBM Plex fonts |

### `resources/`

`guide/index.html` is the offline user guide, built from `docs/guide/USER_GUIDE.md` by `tools/build_guide.py`. `examples/projects/` holds the example projects (built by `tools/build_examples.py`) and `examples/templates/` the import templates, CI scripts, checklist, worksheet and demo values. `fonts/` holds the bundled fonts.

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

pytest + hypothesis (property tests, fuzzing loaders/importers/generator), pytest-cov (>= 90% core gate), mypy strict, ruff, pytest-qt for journeys, golden-file tests per output type on the reference projects `mini3` and `sat15` (folders in `tests/fixtures/projects`; the larger `stress_project()` is built in code for performance tests), soak test (random edits/undo/redo/save/reload with invariants + verifier), offline test, migration fixtures per schema version, CI on Ubuntu 24.04 (the supported platform).

## 6. Risks

1. Pin allocation is the hardest algorithm: start with a constraint-ordered greedy allocator with explicit rule list and provenance; keep it replaceable.
2. Real derating/EMC numbers are missing (D-11); generator and DRC must run with placeholders and mark every result "uses placeholder rules" until replaced.
3. Installer size and PyInstaller: build on the supported OS (Ubuntu 24.04) in CI.
4. Locked-down hosts may block unsigned executables; code signing is configurable (D-19).
5. UX sign-off is a gate: no full editor before the prototype review (spec UX process step 2).

Next: [`DECISIONS.md`](DECISIONS.md), [`SECURITY.md`](SECURITY.md), [`developer/README.md`](developer/README.md).
