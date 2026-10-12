# CLAUDE.md: spacecraft harness design tool (`harness/`)

Clean-room project inside the WireViz repo. **Never copy or import code from `../src/wireviz` (GPL-3.0).** Specification: `docs/SPEC.md`; decisions: `docs/DECISIONS.md`; architecture: `docs/ARCHITECTURE.md`; plan: `docs/PLAN.md`.

## Status
M0 to M9 done (`docs/demos/`), then the October audit (`docs/AUDIT.md`); version 0.1.0 (released by the owner on 2026-10-09 with the engineering decisions still open, compliance/SIGNOFF.md). Platform: Ubuntu 24.04 and newer only (D-110, D-127). The owner waived the people-dependent compliance actions on 2026-10-09 (`compliance/DEVIATIONS.md` T-20 to T-30; a waiver accepts a deviation and does not meet the requirement). The owner signed off 0.1.0rc8 and released 0.1.0 on 2026-10-09 (compliance/SIGNOFF.md; DEVIATIONS.md T-31, the owner's explicit waiver of the condition of RELEASE.md step 14), with the following still open and not done: the harness boundary rule (D-10) and title block (D-15), the real derating/EMC values (D-11) and approved parts list (D-12). D-20 is not needed. Generation runs on placeholders until then; results must say so.

## Commands (run from `harness/`)
- Setup: `python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[gui,dev]"` (Linux also needs libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 for Qt)
- Test: `pytest` (Qt runs offscreen via tests/conftest.py); coverage: `pytest --cov` (90% gate on core, enforced)
- Lint/type: `ruff format . && ruff check . && mypy`
- CLI: `harness --version | new FOLDER [--template NAME] | templates FOLDER | validate DIR | check DIR | migrate DIR | generate DIR | verify DIR | drc DIR | export DIR | verify DIR --outputs | review/release/revise/diff/log DIR HARNESS | compare OLD NEW | config DIR | import-parts/import-lengths/import-netlist DIR FILE`; GUI: `harness-gui`
- GUI tests: `QT_QPA_PLATFORM=offscreen pytest tests/test_gui_journeys.py` (conftest sets it); timings: `python -m tools.bench_gui`; screenshots of the real editor: `python -m tools.gui_screenshots` (docs/ux/qt)
- Prototype: edit `prototype/template.html` / `prototype/app.js` or `gui/tokens.py`, then `python -m tools.build_prototype` (a test fails if `index.html` is stale); screenshots: `python -m tools.ux_screenshots`; journeys: `pytest tests/test_prototype.py` (needs Chromium, skips otherwise)
- Stress benchmarks: `python -m tools.bench_stress`, `python -m tools.bench_generate`
- Output goldens: `PYTHONPATH=. python -m tools.gen_output_goldens` (on purpose; review the diff)
- Package (Ubuntu): `python -m tools.build_installer`, `python -m tools.build_deb`, then `dist/harness-design-studio/harness-design-studio --selftest`
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
- Every new dependency: record name, version, licence in `docs/DECISIONS.md`.
- Tests first; every bug fix gets a regression test.
- End each session with: done, tested, next, UX targets met/open.

## Core layout (M1)
`core/model` (immutable strict models), `core/integrity.py`, `core/commands.py` (History: transactions, undo/redo), `core/io` (layout, loader, saver, migrate, fs), `core/starter.py`, `core/samples.py` (`mini3`). Format: `docs/FILE_FORMAT.md`; placeholders: `docs/PLACEHOLDERS.md`.
- Edit model objects only with `evolve()` and `History.execute`; never mutate `Project` directly outside commands/loader.
- Regenerate the golden fixture only on purpose: `python -c "from harness_design_studio.core.samples import mini3; from harness_design_studio.core.io.saver import save_project; save_project(mini3(), 'tests/fixtures/projects/mini3')"` and review the diff.
- Tests that run as root skip the read-only folder test; run the suite as a normal user in CI.

## GUI layout (M2)
`gui/controller.py` (EditorController: the only thing that changes the project; Delta signals), `canvas.py` (scene, items, view, minimap), `panels.py`, `dialogs.py`, `tour.py`, `main_window.py`, `theme.py`, `tokens.py`, `strings.py` (all UI text). Edit logic is headless in `core/edit.py`, `core/checks.py`, `core/imports.py`, `core/recovery.py`; add new editor features there first, with tests, and keep the GUI thin.
- Never name a widget attribute `palette` (it hides `QWidget.palette()`); it is `palette_panel`.
- Panels that are not visible refresh lazily (on show). Tests that read a tab's widgets must switch to that tab first.
- Dialog hooks (`run_dialog`, `ask_folder`, `ask_text`, `ask_choice`, `ask_file`) exist so tests can drive the UI without blocking.
- Diagram drawing rules that need no Qt live in `core/routing.py` (edge a link leaves from, orthogonal trunk routing of all links, focus of a selection) and `core/describe.py` (link values, connector family from the part); the pictures are drawn in `gui/glyphs.py` and keyed in `gui/legend.py` — show meaning with pictures, not letters or raw text; `tests/test_gui_readability.py` checks them on the flatsat example. Unit room (`edit.unit_footprints`) is the taller of the guided and expert heights, so units never overlap in either mode; `tools/build_examples.py` arranges the examples with it. Pictures for `docs/FLATSAT_EXAMPLE.md`: `python -m tools.flatsat_screenshots`.
- Keep edits under 100 ms at stress size: use the Delta, never rebuild the whole scene for a local change, and never call `update()`/`prepareGeometryChange()` on the lane (zone) items or the overview map for a local edit (they are as tall as the diagram; one such call repaints every item). `tests/test_gui_perf.py` guards this by counting dirty regions.

## Generation layout (M3)
`core/generate/` (`segmentation`, `wiring`, `pins`, `sizing`, `lengths`, `mass`, `naming`, `explain`, `engine`), `core/verify.py` (independent verifier), `core/model/generation.py` (record with provenance). `plan_generation(project)` is pure and returns ops + `RegenReport` + record; the GUI previews it (`GeneratePreviewDialog`), runs it in `PlanWorker` and applies it through `History`.
- Never put timestamps or history wording into provenance: a second plan must be empty and byte-identical.
- Verifier must stay independent of the generator: do not import wiring/pin logic into `core/verify.py`.
- Goldens: `tests/fixtures/projects/mini3` (written by `save_project(mini3())`, see the M1 section) and `sat15` (generated). Regenerate sat15 on purpose: `python -c "from harness_design_studio.core.samples import sat15; from harness_design_studio.core.generate.engine import generate_project; from harness_design_studio.core.io.saver import save_project; p=sat15(); generate_project(p); save_project(p,'tests/fixtures/projects/sat15')"` (delete the folder first) and review the diff.
- Text-replace patches fail silently after `ruff format`; grep to confirm they applied.

## Design rule check layout (M4)
`core/drc/` (`base` Rule/Hit, `rules` RULES registry, `report` Markdown report, `__init__` run/fix_ops/locate). Add a rule: write a check generator, register it in `RULES`, add a positive case to `POSITIVE` in `tests/test_drc.py` (a test fails if a rule has none) and make sure it stays quiet on the clean project. Rules needing numbers must stay silent while config is `null` and be listed in `_unchecked`.
- `checks.find` stays the fast synchronous logical layer; the controller merges it with background DRC results (`DrcWorker` waits for the helper process, 1.2 s after the last edit; waivers applied at display time).
- The check runs in a helper process (`gui/drc_process.py`, `core/drc/worker.py`, D-128; a thread held the GIL and stalled edits). Do not add synchronous DRC calls to edit paths. The packaged program must route `--drc-worker` first (`packaging/gui_entry.py`; `--selftest` checks it). Keep the pieces small: one pickle call holds the sender's GIL.
- Regenerate the sat15 DRC report golden on purpose: `python -m harness_design_studio.cli.main drc tests/fixtures/projects/sat15 > tests/fixtures/drc/sat15.md`.

## Outputs layout (M5)
`core/outputs/` (`canvas` SVG/PDF writers, `drawing`, `system` diagrams, `tables`, `exports` YAML/JSON/XLSX, `stamp`, `build` build/write/status, `verify` independent verifier). Format and limits: `docs/OUTPUTS.md`.
- `build_outputs` is pure and deterministic: no dates, sorted rows, uncompressed PDF, XLSX re-zipped with fixed timestamps. Keep it that way; goldens depend on it.
- `core` must not import modules that import network code at import time (`xml.sax.saxutils` does; use `canvas.escape`). The offline test catches this.
- `core/outputs/verify.py` must stay independent of `tables.py`/`drawing.py`: derive expectations from the project.
- Adding an output file: build it in `build_outputs`, add its check to `verify.py` with a mutation test, regenerate goldens, document it in `docs/OUTPUTS.md`.

## Change control layout (M6)
`core/vcs/` (`release` plans, `locks` enforced in `History.execute`, `diff`, `snapshot`, `hashing` content hash, `report` change log and revision report, `consistency` released-vs-baseline), `cli/changes.py`. Format: `docs/FILE_FORMAT.md`; decisions D-102 to D-109.
- Release, new revision and review are plans of ops run through `History`; never write baselines or the change log directly.
- Anything that may change a released harness must pass `check_locks`; `apply_ops` bypasses it on purpose (generation, loaders, tests), so keep new editing paths on `History`.
- Generation's input hash must not include release bookkeeping (status); the outputs gate uses `content_hash`.
- Add a diffable object kind in `vcs/diff.py` (`_flatten_*`) and its name in `KIND_NAMES`.

## KiCad import (M9+)
`core/kicad.py` (S-expression and XML netlist reader + import planner), `cli/data.py` `import-netlist`, `Pin.fixed` honoured in `generate/pins.py` and `engine.py`. Docs `docs/KICAD.md`, D-123/D-124. Fixtures are hand-made; one real KiCad 10.0.6 file was checked.

## Examples, templates and documentation
`core/templates.py` (`create_project`, `copy_import_templates`), `cli/start.py` (`harness new`, `harness templates`), `resources/examples/` (`projects/` built by `tools/build_examples.py`; `templates/` written by hand: CSV, netlist, CI scripts, review checklist, demo values), `resources.examples_path()` (also inside PyInstaller). Docs for newcomers: `docs/LEARNING_PATH.md`, `GETTING_STARTED.md`, `CONCEPTS.md`, `INSTALL.md`, `CHEATSHEET.md`, `FAQ.md`, `CLI.md`; map in `docs/README.md`. Examples: `blank`, `first-steps`, `minimal-satellite`, `small-satellite`, `flatsat` (generated, with EXAMPLE numbers; walkthrough `docs/FLATSAT_EXAMPLE.md`); the template `design-worksheet.md` is for planning on paper.
- A new CLI command needs an entry in `tools/gen_cli_docs.py` (group and examples) and in the user guide; a changed example needs `python -m tools.build_examples`.
- Demo values in the templates are for learning only, never engineering data, and stay `"placeholder": true` (D-129). Do not make the examples look reviewed.
- If you change what the tutorial prints (the example, the sizing, the drawings), update `docs/GETTING_STARTED.md` and `docs/img/` (a test checks the commands and the quoted model hash).

## Compliance audit (ECSS/ESCC)
`compliance/` (requirement lists, assessment, matrix, gap analysis, evidence, process documents), `core/standard_profiles.py` (optional value profiles, D-131), `core/drc/standard_rules.py` (rules that apply the supplied standards), `tools/extract_requirements.py`, `tools/build_compliance_matrix.py`, `tools/trace.py`, `tools/metrics.py`, `tools/gen_scf.py`.
- Never add a standard value as a default; profiles fill unset values only and cite a requirement ID that exists in `compliance/requirements` (a test checks it).
- A new rule that serves a requirement names it in `sources=`; a rule that needs a number stays silent without it and adds a line to `standard_rules.unchecked`.
- Rebuild after changing assessments: `python -m tools.build_compliance_matrix`, `python -m tools.trace`, and after adding or moving modules `python -m tools.gen_sdd_components` (every module needs a docstring); the outputs are checked for freshness by tests.

## Polish layout (M7)
User guide `docs/guide/USER_GUIDE.md` (HTML bundled in `src/harness_design_studio/resources/guide/`, F1), `docs/RULES.md` (generated), `docs/CONFIG.md`, `docs/usability/`, Ubuntu packaging in `packaging/ubuntu/` and `tools/build_deb.py`, `tools/release_check.py`, `tools/soak.py`.
- New UI controls need an accessible name (`tests/test_accessibility.py` fails otherwise) and strings go in `gui/strings.py`.
- New CLI commands or buttons mentioned in the guide must exist, and new commands must be documented in the guide (`tests/test_docs.py`).
- Keep the integrity cache correct: anything the checks depend on must be part of the token in `core/integrity.py`.
