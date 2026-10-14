# Milestone plan (proposal for owner review)

> **Historical.** This is the plan as it was proposed to the owner in October 2026, before the first release. Milestones M0 to M9 were done (a note for each is in [`demos/`](demos/README.md)) and 0.1.0 is released; this page was not kept up to date. For the current state read [`../CHANGELOG.md`](../CHANGELOG.md) and the [documentation index](README.md). Two items below were never built, and are marked *(not built)*: multi-drop interfaces and hierarchy, and a PDF user guide.

Each milestone: tests first, ends with working tested software, a demo note in `docs/demos/` (M0 to M7 have one), and a UX self-review where a GUI exists. A milestone is done only when all its acceptance criteria pass in CI.

## M0 Foundation
- Repo skeleton (`src/harness_design_studio/{core,cli,gui}`), `pyproject.toml` with pinned deps, `CLAUDE.md`, ruff + mypy strict + pytest in CI (planned for Windows + Linux; now Ubuntu 24.04 only, D-127).
- Vendored/mirrored wheel set script (`tools/vendor.py`) and a reproducible-build check.
- Offline tests: module-scan for network imports; socket-blocked smoke run of CLI and empty GUI (offscreen).
- Empty Qt app window + `harness --version`, packaged with PyInstaller; installer/portable zip built in CI.
- SBOM (CycloneDX) + licence report generated and checked against an allow-list (permissive/LGPL).
- Import-linter style test: `core` must not import `gui`/`cli`/network.
- `docs/REQUIREMENTS.md` seeded from SPEC with `REQ-` IDs (D-20).
**Acceptance:** CI green on both OSes; installer starts on a clean VM with network disabled; SBOM and licence report present; offline tests pass.

## M1 Model and files
- Pydantic model for logical and physical layers, ID rules, units/AWG helpers.
- Project folder I/O: canonical JSON writer, atomic save with backup, schema version + migration framework (with a v0 to v1 fixture), referential integrity checks, recovery mode, newer-version read-only, file-lock for double open.
- Parts library with approval status and starter library (marked unverified).
- Config loader with PLACEHOLDER-flagged defaults.
- Transactions + undo/redo command layer.
- CLI: `harness validate`, `harness check`.
- Reference project `mini3` (hand-written).
**Acceptance:** round trip load/save is byte-identical; fuzz tests on loader never crash; corrupt-file fixtures open in recovery mode with a precise report; coverage >= 90% for `core`.

## M2 Block diagram (DONE: see docs/demos/M2-gate.md and M2.md)
- Gate 1: `docs/UX.md` (personas, 10 journeys, IA, wireframes, design system) and a clickable prototype; **owner review before continuing**.
- Canvas editor (units, connectors, interfaces, zones, nominal/redundant styles, multi-drop *(not built: multi-drop interfaces are skipped with a warning, D-116)*, hierarchy *(not built: the model has none)*), palette, properties panel, status/to-do panel, table (ICD) view in sync, undo/redo, autosave and crash recovery, command palette, search.
- Interface-type library and compatibility highlighting with tooltips.
- CSV/XLSX import with column mapping, preview, per-row errors, single undo step.
- pytest-qt tests for journeys J1 to J4; screenshots via offscreen; UX issue list.
**Acceptance:** 5-unit diagram can be built from the sample project tour; no direct model mutation outside commands; UX high-severity issues fixed.

## M3 Generation (done; spare-pin fraction and a length-import screen are open)
- Segmentation (configurable), deterministic IDs and naming schemes.
- Pin allocator with rules, locks, spare pins, provenance.
- Wire sizing (config-driven derating, voltage drop), lengths from routing segments, mass with margin.
- Regeneration merge with `RegenReport`; "Explain" data.
- Reference project `sat15`; stress project generator.
- Independent verifier v1 (connectivity, pin uniqueness) runs after generation.
**Acceptance:** byte-identical regeneration (property test); verifier clean on `mini3` and `sat15`; stress project regenerates < 10 s on reference laptop or a profiling note explains the gap.

## M4 DRC (done; incremental per-rule caching is open, see demos/M4.md)
- All rules listed in spec, each with plain-language what/why/fix and positive and negative tests; waivers with justification; background and on-demand runs; problems panel with click-to-select and one-click fixes where feasible.
**Acceptance:** 100% rules have both tests; waivers persist and show in report; incremental DRC keeps edits < 100 ms on the stress project.

## M5 Outputs (done; geometric branch drawing and dates/authors are open, see demos/M5.md)
- Harness drawing (SVG + PDF, A4/A3 multi-sheet, title block), wire list, pinouts, BOM, mass/length, continuity and isolation tests, labels, DRC report; system diagrams and matrices; XLSX/CSV; WireViz YAML and documented JSON export.
- Every artefact stamped with generator version and model hash; stale detection in GUI and CLI.
- Verifier v2 covers all artefacts (BOM vs drawing, pinout vs wire list).
- Golden-file tests per output type on three reference projects; print-theme checks (greyscale legibility).
**Acceptance:** goldens stable on every supported platform (Ubuntu 24.04 and newer); verifier clean; PDFs use only bundled fonts.

## M6 Change control (done; see demos/M6.md for what is open)
- Revisions, status, release with mandatory comment (blocked by verifier errors, stale outputs, DRC errors), baselines, locks on released items, diff engine and visual diff, change log, `harness check` for post-merge consistency, on-disk change detection and safe reload.
**Acceptance:** diff of two baselines lists added/removed/changed objects exactly; released items cannot be edited without a new revision.

## M7 Polish (done except the items that need people; see demos/M7.md)
- Guided and expert modes, themes, scaling to 200%, accessibility audit, performance tuning, soak test, user guide (Markdown + offline HTML; the PDF was not built), developer docs (file format, rule config), release checklist, final installers, SBOM.
**Acceptance:** performance targets met on the stress project; soak test passes N thousand steps; release checklist completed; usability test results triaged.

## Items needing owner input (from DECISIONS.md)
D-10 harness boundary rule (before M3), D-11 real derating/EMC numbers (before M3 results can be trusted), D-15 title-block format (before M5), D-20 qualification requirement (not needed, decided by the owner), D-14/D-19 confirmations.
